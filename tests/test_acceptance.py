"""Phase 05 acceptance workflows across API, worker, evidence, report, and review."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.analysis_pipeline import AnalysisDraft, EvidenceLinkDraft, HypothesisDraft
from backend.database import Base, get_session
from backend.evidence_pipeline import evidence_digest
from backend.main import app
from backend.models import (
    AuditEvent, Evidence, HypothesisEvidence, Incident, Investigation,
    InvestigationJob, Report, Review,
)
from backend.telemetry_gateway import TelemetryUnavailable
from backend.worker import run_once


START = datetime(2026, 9, 21, 10, tzinfo=timezone.utc)
END = START + timedelta(minutes=15)
REVIEWER_KEY = "reviewer-test-key-with-at-least-32-characters"


def _ns(value: datetime) -> str:
    return str(int(value.timestamp() * 1_000_000_000))


class AcceptanceGateway:
    def query_logs(self, query):
        return [{
            "source": "loki",
            "service": query.service,
            "timestamp_ns": _ns(START + timedelta(minutes=1)),
            "event": "request_failed",
            "status_code": 503,
            "message": "Authorization: Bearer must-never-be-persisted",
        }]

    def query_metrics(self, query, metric="request_rate"):
        return [{
            "source": "prometheus",
            "service": query.service,
            "metric": metric,
            "timestamp": (START + timedelta(minutes=2)).timestamp(),
            "value": 0.2 if metric == "request_rate" else 0.1,
        }]

    def query_traces(self, query):
        return []


class CitingAnalyzer:
    def __init__(self):
        self.received = None

    def analyze(self, evidence, gaps):
        self.received = evidence, gaps
        return AnalysisDraft(
            "A request failure may have affected inventory traffic.",
            "Evidence limits: " + ", ".join(gaps) + ".",
            (HypothesisDraft(
                "A downstream failure may explain the observed request error.",
                "LOW",
                gaps,
                (EvidenceLinkDraft(evidence[0].id, "SUPPORTS"),),
            ),),
        )


@pytest.fixture
def system(monkeypatch):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override_session():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    monkeypatch.setenv("REVIEWER_ID", "acceptance-reviewer")
    monkeypatch.setenv("REVIEWER_API_KEY", REVIEWER_KEY)
    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            yield client, factory, {
                "Authorization": f"Bearer {REVIEWER_KEY}",
            }
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _queue(client: TestClient, suffix: str) -> tuple[str, str]:
    incident = client.post(
        "/api/v1/incidents",
        json={
            "title": "Inventory failure",
            "description": "Customer details must not reach evidence or the model.",
            "service": "incident-demo-api",
            "severity": "HIGH",
            "window_start": START.isoformat(),
            "window_end": END.isoformat(),
        },
        headers={"Idempotency-Key": f"acceptance-incident-{suffix}"},
    )
    assert incident.status_code == 201, incident.text
    incident_id = incident.json()["id"]
    investigation = client.post(
        f"/api/v1/incidents/{incident_id}/investigations",
        json={"focus": "Inventory request failures"},
        headers={"Idempotency-Key": f"acceptance-investigation-{suffix}"},
    )
    assert investigation.status_code == 202, investigation.text
    return incident_id, investigation.json()["id"]


def test_complete_workflow_preserves_provenance_and_authenticated_review(system):
    client, factory, auth = system
    incident_id, investigation_id = _queue(client, "complete")
    analyzer = CitingAnalyzer()

    assert run_once(
        factory, AcceptanceGateway(), analyzer, "acceptance-worker",
        investigation_id=investigation_id,
    ) == "DONE"

    evidence_response = client.get(
        f"/api/v1/investigations/{investigation_id}/evidence",
    )
    report_response = client.get(
        f"/api/v1/investigations/{investigation_id}/report",
    )
    assert evidence_response.status_code == report_response.status_code == 200
    evidence_rows = evidence_response.json()
    evidence_ids = {row["id"] for row in evidence_rows}
    cited_ids = {
        link["evidence_id"]
        for hypothesis in report_response.json()["hypotheses"]
        for link in hypothesis["evidence"]
    }
    assert cited_ids and cited_ids <= evidence_ids
    assert "must-never-be-persisted" not in evidence_response.text
    assert "Customer details" not in repr(analyzer.received)

    reviewed = client.put(
        f"/api/v1/investigations/{investigation_id}/review",
        json={"decision": "ACCEPTED", "comment": "Evidence links reviewed."},
        headers=auth,
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["reviewer"] == "acceptance-reviewer"
    final = client.get(f"/api/v1/investigations/{investigation_id}").json()
    assert final["status"] == "COMPLETED"
    assert final["job"] == {"status": "DONE", "attempts": 1}
    assert client.get(f"/api/v1/incidents/{incident_id}").json()["status"] == "OPEN"

    with factory() as session:
        evidence = session.scalars(select(Evidence).where(
            Evidence.investigation_id == investigation_id,
        )).all()
        capture = session.scalar(select(AuditEvent).where(
            AuditEvent.investigation_id == investigation_id,
            AuditEvent.action == "EVIDENCE_CAPTURED",
        ))
        assert capture.detail["record_count"] == len(evidence)
        assert capture.detail["evidence_digest"] == evidence_digest(evidence)
        assert session.scalar(select(HypothesisEvidence.evidence_id)) in {
            row.id for row in evidence
        }
        actions = session.scalars(select(AuditEvent).where(
            AuditEvent.investigation_id == investigation_id,
        )).all()
        assert {row.action for row in actions} == {
            "INVESTIGATION_QUEUED",
            "INVESTIGATION_STARTED",
            "EVIDENCE_CAPTURED",
            "INVESTIGATION_AWAITING_REVIEW",
            "INVESTIGATION_REVIEWED",
        }
        review_audit = next(row for row in actions if row.action == "INVESTIGATION_REVIEWED")
        assert review_audit.actor == "acceptance-reviewer"
        assert session.scalar(select(Report.id)) is not None
        assert session.scalar(select(Review.id)) == reviewed.json()["id"]


def test_telemetry_outage_retries_without_evidence_report_or_review(system):
    client, factory, auth = system
    _, investigation_id = _queue(client, "telemetry-outage")

    class Down(AcceptanceGateway):
        def query_logs(self, query):
            raise TelemetryUnavailable("Loki unavailable")

    class MustNotRun:
        def analyze(self, evidence, gaps):
            raise AssertionError("Model must not run after telemetry outage")

    assert run_once(
        factory, Down(), MustNotRun(), "outage-worker",
        investigation_id=investigation_id,
    ) == "HANDLED_FAILURE"
    status = client.get(f"/api/v1/investigations/{investigation_id}").json()
    assert status["status"] == "QUEUED"
    assert status["job"] == {"status": "QUEUED", "attempts": 1}
    assert status["error"] == "TELEMETRY_UNAVAILABLE"
    assert client.get(f"/api/v1/investigations/{investigation_id}/evidence").json() == []
    assert client.get(f"/api/v1/investigations/{investigation_id}/report").status_code == 404
    review = client.put(
        f"/api/v1/investigations/{investigation_id}/review",
        json={"decision": "ACCEPTED"}, headers=auth,
    )
    assert review.status_code == 409
    with factory() as session:
        actions = {row.action for row in session.scalars(select(AuditEvent).where(
            AuditEvent.investigation_id == investigation_id,
        )).all()}
        assert "INVESTIGATION_RETRY_SCHEDULED" in actions
        assert "EVIDENCE_CAPTURED" not in actions


def test_invalid_model_citation_cannot_create_report_but_keeps_evidence(system):
    client, factory, auth = system
    _, investigation_id = _queue(client, "invalid-citation")

    class InvalidCitation:
        def analyze(self, evidence, gaps):
            return AnalysisDraft(
                "Unsupported report.",
                "Evidence limits: " + ", ".join(gaps) + ".",
                (HypothesisDraft(
                    "An unsupported cause.", "LOW", gaps,
                    (EvidenceLinkDraft("outside-this-investigation", "SUPPORTS"),),
                ),),
            )

    assert run_once(
        factory, AcceptanceGateway(), InvalidCitation(), "invalid-model-worker",
        investigation_id=investigation_id,
    ) == "HANDLED_FAILURE"
    status = client.get(f"/api/v1/investigations/{investigation_id}").json()
    assert status["status"] == "QUEUED"
    assert status["job"] == {"status": "QUEUED", "attempts": 1}
    assert status["error"] == "RESULT_INVALID"
    assert len(client.get(
        f"/api/v1/investigations/{investigation_id}/evidence",
    ).json()) == 3
    assert client.get(f"/api/v1/investigations/{investigation_id}/report").status_code == 404
    assert client.put(
        f"/api/v1/investigations/{investigation_id}/review",
        json={"decision": "REJECTED"}, headers=auth,
    ).status_code == 409
    with factory() as session:
        assert session.scalar(select(Report.id)) is None
        assert session.scalar(select(Review.id)) is None
        assert session.scalars(select(HypothesisEvidence)).all() == []
        job = session.get(InvestigationJob, investigation_id)
        investigation = session.get(Investigation, investigation_id)
        assert job.status == investigation.status == "QUEUED"
