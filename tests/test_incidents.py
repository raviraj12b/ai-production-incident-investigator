"""Incident intake invariants; SQLite is used only as an isolated API test DB."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_session
from backend.main import app
from backend.models import AuditEvent, Incident


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
