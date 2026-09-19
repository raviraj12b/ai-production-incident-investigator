"""Evidence redaction, provenance, and stale-claim DB fencing."""

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.database import Base, get_session
from backend.evidence_pipeline import (
    EvidenceBatch, EvidenceValidationError, collect_evidence, collect_for_claim, save_evidence,
)
from backend.jobs import claim_next_job
from backend.main import app
from backend.models import AuditEvent, Evidence
from backend.telemetry_gateway import TelemetryUnavailable


START = datetime(2026, 9, 18, 10, tzinfo=timezone.utc)
END = START + timedelta(minutes=15)
TRACE = "a" * 32
SPAN = "b" * 16


def ns(value):
    return str(int(value.timestamp() * 1_000_000_000))


class FakeGateway:
    def query_logs(self, query):
        assert query.service == "incident-demo-api" and query.start == START
        return [{"source": "loki", "service": query.service, "timestamp_ns": ns(START + timedelta(minutes=1)),
                 "message": "Authorization: Bearer private-token user@example.com",
                 "event": "request_failed", "status_code": 503, "trace_id": TRACE,
                 "request_id": "sensitive-request-id"}]

    def query_metrics(self, query, metric="request_rate"):
        return [{"source": "prometheus", "service": query.service, "metric": metric,
                 "timestamp": (START + timedelta(minutes=3)).timestamp(),
                 "value": 0.2 if metric == "request_rate" else 0.1}]

    def query_traces(self, query):
        return [{"source": "jaeger", "service": "dependency-service", "trace_id": TRACE,
                 "span_id": SPAN, "name": "GET /secret?id=abc",
                 "start_time_unix_nano": ns(START + timedelta(minutes=2))},
                {"source": "jaeger", "service": "incident-demo-api", "trace_id": TRACE,
                 "span_id": "c" * 16, "name": "older span",
                 "start_time_unix_nano": ns(START - timedelta(seconds=1))}]


def test_evidence_is_bounded_redacted_and_correlated():
    batch = collect_evidence(FakeGateway(), "incident-demo-api", START, END)
    assert [r.kind for r in batch.records] == ["LOG", "TRACE", "METRIC", "METRIC"]
    assert len(batch.records) == 4
    assert batch.correlations[0].trace_id == TRACE
    assert (batch.correlations[0].log_count, batch.correlations[0].span_count) == (1, 1)
    assert "CHANGE_FEED_NOT_CONFIGURED" in batch.gaps
    visible = repr(batch.records)
    assert "private-token" not in visible and "user@example.com" not in visible
    assert "secret?id" not in visible and "sensitive-request-id" not in visible
    log = next(r for r in batch.records if r.kind == "LOG")
    assert log.summary == "request_failed (HTTP 503)"
    assert log.source_ref.startswith("loki:")


def test_missing_signals_are_gaps_instead_of_positive_evidence():
    class Empty:
        def query_logs(self, query):
            return []

        def query_metrics(self, query, metric="request_rate"):
            return []

        def query_traces(self, query):
            return []

    batch = collect_evidence(Empty(), "incident-demo-api", START, END)
    assert batch.records == ()
    assert batch.correlations == ()
    assert batch.gaps == ("NO_LOGS", "NO_REQUEST_RATE", "NO_TRACES", "CHANGE_FEED_NOT_CONFIGURED")


def test_backend_outage_and_oversized_result_never_become_missing_signal_gaps():
    class Outage(FakeGateway):
        def query_traces(self, query):
            raise TelemetryUnavailable("Jaeger is offline")

    class Oversized(FakeGateway):
        def query_logs(self, query):
            return super().query_logs(query) * 26

    with pytest.raises(TelemetryUnavailable):
        collect_evidence(Outage(), "incident-demo-api", START, END)
    with pytest.raises(EvidenceValidationError):
        collect_evidence(Oversized(), "incident-demo-api", START, END)


def test_db_capture_is_fenced_and_read_api_exposes_only_safe_snapshots():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            incident = client.post("/api/v1/incidents", json={
                "title": "Dependency error", "service": "incident-demo-api", "severity": "HIGH",
                "window_start": START.isoformat(), "window_end": END.isoformat(),
            }, headers={"Idempotency-Key": "evidence-incident"})
            assert incident.status_code == 201, incident.text
            created = client.post(f"/api/v1/incidents/{incident.json()['id']}/investigations",
                                  json={}, headers={"Idempotency-Key": "evidence-run"})
            assert created.status_code == 202, created.text
            investigation_id = created.json()["id"]
            assert client.get(f"/api/v1/investigations/{investigation_id}/evidence").json() == []
            claim = claim_next_job(factory, "worker-evidence")
            assert claim.investigation_id == investigation_id
            batch = collect_for_claim(factory, claim, FakeGateway())
            assert batch is not None
            assert save_evidence(factory, claim, batch) is True  # same capture is idempotent
            response = client.get(f"/api/v1/investigations/{investigation_id}/evidence")
            assert response.status_code == 200
            assert len(response.json()) == 4
            assert "private-token" not in response.text
            assert "secret?id" not in response.text
            assert response.json()[0]["source_backend"] == "loki"
            assert client.get("/api/v1/investigations/missing/evidence").status_code == 404
            assert client.get(f"/api/v1/investigations/{investigation_id}/evidence?limit=101").status_code == 422

            later = datetime.now(timezone.utc) + timedelta(seconds=301)
            next_claim = claim_next_job(factory, "replacement-worker", now=later)
            assert next_claim.attempt == 2
            assert save_evidence(factory, claim, batch, now=later) is False
            unsafe = replace(batch.records[0], summary="Authorization: Bearer private-token")
            with pytest.raises(EvidenceValidationError):
                save_evidence(factory, next_claim,
                              EvidenceBatch((unsafe, *batch.records[1:]), batch.gaps, batch.correlations),
                              now=later)
            with pytest.raises(EvidenceValidationError):
                save_evidence(factory, next_claim, EvidenceBatch((), (), ()), now=later)
            with Session(engine) as session:
                assert len(session.scalars(select(Evidence)).all()) == 4
                captured = session.scalars(select(AuditEvent).where(AuditEvent.action == "EVIDENCE_CAPTURED")).all()
                assert len(captured) == 1
                assert captured[0].detail["record_count"] == 4
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
