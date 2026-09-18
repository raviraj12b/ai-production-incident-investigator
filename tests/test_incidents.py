"""API and state-machine checks; PostgreSQL locking needs an integration test."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_session
from backend.jobs import claim_next_job, fail_claim, renew_lease
from backend.main import app
from backend.models import AuditEvent, Incident, Investigation, InvestigationJob


@pytest.fixture
def api():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    def override_session():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            yield client, engine
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


PAYLOAD = {
    "title": "Inventory errors",
    "service": "incident-demo-api",
    "severity": "HIGH",
    "window_start": "2026-09-17T10:00:00Z",
    "window_end": "2026-09-17T10:15:00Z",
}


def test_create_replay_conflict_and_audit(api):
    client, engine = api
    headers = {"Idempotency-Key": "alert-42"}
    first = client.post("/api/v1/incidents", json=PAYLOAD, headers=headers)
    assert first.status_code == 201, first.text
    incident_id = first.json()["id"]
    assert first.headers["location"] == f"/api/v1/incidents/{incident_id}"

    replay = client.post("/api/v1/incidents", json=PAYLOAD, headers=headers)
    assert replay.status_code == 201
    assert replay.json()["id"] == incident_id
    other = client.post("/api/v1/incidents", json={**PAYLOAD, "title": "Changed"}, headers=headers)
    assert other.status_code == 409
    assert other.json()["error"]["code"] == "CONFLICT"

    assert client.get(f"/api/v1/incidents/{incident_id}").json()["title"] == "Inventory errors"
    assert len(client.get("/api/v1/incidents").json()) == 1
    with Session(engine) as session:
        assert len(session.scalars(select(Incident)).all()) == 1
        assert [a.action for a in session.scalars(select(AuditEvent)).all()] == ["INCIDENT_CREATED"]


def test_validation_and_update(api):
    client, engine = api
    bad = client.post(
        "/api/v1/incidents", json={**PAYLOAD, "window_end": PAYLOAD["window_start"]},
        headers={"Idempotency-Key": "invalid"},
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "VALIDATION_ERROR"
    naive = client.post(
        "/api/v1/incidents", json={**PAYLOAD, "window_start": "2026-09-17T10:00:00"},
        headers={"Idempotency-Key": "naive"},
    )
    assert naive.status_code == 422

    created = client.post("/api/v1/incidents", json=PAYLOAD, headers={"Idempotency-Key": "valid"})
    incident_id = created.json()["id"]
    result = client.patch(f"/api/v1/incidents/{incident_id}", json={"severity": "CRITICAL"})
    assert result.status_code == 200
    assert result.json()["severity"] == "CRITICAL"
    assert client.patch(f"/api/v1/incidents/{incident_id}", json={"status": "CLOSED"}).status_code == 422
    assert client.get("/api/v1/incidents/unknown").status_code == 404
    with Session(engine) as session:
        assert sorted(a.action for a in session.scalars(select(AuditEvent)).all()) == [
            "INCIDENT_CREATED", "INCIDENT_UPDATED",
        ]


def test_investigation_request_is_atomic_and_idempotent(api):
    client, engine = api
    incident_id = client.post(
        "/api/v1/incidents", json=PAYLOAD,
        headers={"Idempotency-Key": "incident-for-investigation"},
    ).json()["id"]
    url = f"/api/v1/incidents/{incident_id}/investigations"
    headers = {"Idempotency-Key": "first-run"}
    first = client.post(url, json={"focus": "Inventory latency"}, headers=headers)
    assert first.status_code == 202, first.text
    investigation_id = first.json()["id"]
    assert first.json()["status"] == "QUEUED"
    assert first.json()["job"] == {"status": "QUEUED", "attempts": 0}
    assert first.headers["location"] == f"/api/v1/investigations/{investigation_id}"

    replay = client.post(url, json={"focus": "Inventory latency"}, headers=headers)
    assert replay.status_code == 202
    assert replay.json()["id"] == investigation_id
    conflict = client.post(url, json={"focus": "Different"}, headers=headers)
    assert conflict.status_code == 409
    another_run = client.post(url, json={}, headers={"Idempotency-Key": "another-run"})
    assert another_run.status_code == 409
    assert client.get(f"/api/v1/investigations/{investigation_id}").status_code == 200
    assert len(client.get(url).json()) == 1
    assert client.post(url, json={}, headers={}).status_code == 422
    assert client.post("/api/v1/incidents/unknown/investigations", json={}, headers=headers).status_code == 404

    with Session(engine) as session:
        assert len(session.scalars(select(Investigation)).all()) == 1
        assert len(session.scalars(select(InvestigationJob)).all()) == 1
        actions = [a.action for a in session.scalars(select(AuditEvent)).all()]
        assert actions.count("INVESTIGATION_QUEUED") == 1


def test_worker_lease_fences_stale_claim_and_limits_retries(api):
    client, engine = api
    incident_id = client.post(
        "/api/v1/incidents", json=PAYLOAD,
        headers={"Idempotency-Key": "worker-incident"},
    ).json()["id"]
    url = f"/api/v1/incidents/{incident_id}/investigations"
    investigation_id = client.post(
        url, json={}, headers={"Idempotency-Key": "worker-run"},
    ).json()["id"]
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    start = datetime.now(timezone.utc) + timedelta(seconds=1)

    claim1 = claim_next_job(factory, "worker-a", now=start)
    assert claim1.investigation_id == investigation_id
    assert claim1.attempt == 1
    assert claim_next_job(factory, "worker-b", now=start) is None

    reclaimed_at = start + timedelta(seconds=301)
    claim2 = claim_next_job(factory, "worker-b", now=reclaimed_at)
    assert claim2.attempt == 2
    assert renew_lease(factory, claim1, now=reclaimed_at) is False
    assert fail_claim(factory, claim1, now=reclaimed_at) is False
    assert renew_lease(factory, claim2, now=reclaimed_at) is True
    assert fail_claim(factory, claim2, now=reclaimed_at) is True

    assert claim_next_job(factory, "worker-c", now=reclaimed_at) is None
    claim3 = claim_next_job(factory, "worker-c", now=reclaimed_at + timedelta(seconds=31))
    assert claim3.attempt == 3
    assert fail_claim(factory, claim3, now=reclaimed_at + timedelta(seconds=31)) is True
    assert claim_next_job(factory, "worker-d", now=reclaimed_at + timedelta(seconds=400)) is None
    result = client.get(f"/api/v1/investigations/{investigation_id}").json()
    assert result["status"] == "FAILED"
    assert result["job"] == {"status": "FAILED", "attempts": 3}
