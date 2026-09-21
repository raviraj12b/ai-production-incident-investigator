"""Report validation, evidence citations, and atomic job completion."""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.analysis_pipeline import (
    AnalysisDraft, AnalysisValidationError, EvidenceLinkDraft, HypothesisDraft,
    complete_claim, inconclusive,
)
from backend.database import Base, get_session
from backend.evidence_pipeline import collect_evidence, save_evidence
from backend.jobs import claim_next_job
from backend.main import app
from backend.models import (
    AuditEvent, Evidence, Hypothesis, HypothesisEvidence, Incident, Investigation,
    InvestigationJob, Report,
)


START = datetime(2026, 9, 18, 10, tzinfo=timezone.utc)
END = START + timedelta(minutes=15)


class MetricsOnly:
    def query_logs(self, query):
        return []

    def query_traces(self, query):
        return []

    def query_metrics(self, query, metric="request_rate"):
        return [{"source": "prometheus", "service": query.service, "metric": metric,
                 "timestamp": (START + timedelta(minutes=3)).timestamp(), "value": 0.2}]


class Empty(MetricsOnly):
    def query_metrics(self, query, metric="request_rate"):
        return []


@pytest.fixture
def claimed():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        incident = Incident(title="Inventory error", service="incident-demo-api",
                            severity="HIGH", window_start=START, window_end=END)
        session.add(incident)
        session.flush()
        investigation = Investigation(incident_id=incident.id, window_start=START, window_end=END)
        session.add(investigation)
        session.flush()
        session.add(InvestigationJob(investigation_id=investigation.id))
        investigation_id = investigation.id
    claim = claim_next_job(factory, "analysis-worker")
    assert claim is not None and claim.investigation_id == investigation_id
    try:
        yield factory, engine, claim
    finally:
        engine.dispose()


def low_draft(evidence_id, gaps):
    return AnalysisDraft(
        "A possible request failure requires review.",
        "Evidence limits: " + ", ".join(gaps) + ". Causality is unverified.",
        (HypothesisDraft("A dependency might be unavailable.", "LOW", gaps,
                         (EvidenceLinkDraft(evidence_id, "SUPPORTS"),)),),
    )


def test_cited_completion_is_atomic_and_exposed_by_read_api(claimed):
    factory, engine, claim = claimed
    batch = collect_evidence(MetricsOnly(), "incident-demo-api", START, END)
    assert save_evidence(factory, claim, batch) is True
    with factory() as session:
        evidence_id = session.scalar(select(Evidence.id))
    draft = low_draft(evidence_id, batch.gaps)
    assert complete_claim(factory, claim, draft) is True
    assert complete_claim(factory, claim, draft) is False
    with factory() as session:
        job = session.get(InvestigationJob, claim.investigation_id)
        investigation = session.get(Investigation, claim.investigation_id)
        assert (job.status, job.worker_id, job.lease_until) == ("DONE", None, None)
        assert investigation.status == "AWAITING_REVIEW" and investigation.finished_at
        assert len(session.scalars(select(Report)).all()) == 1
        assert len(session.scalars(select(Hypothesis)).all()) == 1
        assert session.scalar(select(HypothesisEvidence.evidence_id)) == evidence_id
        assert len(session.scalars(select(AuditEvent).where(
            AuditEvent.action == "INVESTIGATION_AWAITING_REVIEW",
        )).all()) == 1

    def override_session():
        with Session(engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    try:
        with TestClient(app) as client:
            response = client.get(f"/api/v1/investigations/{claim.investigation_id}/report")
            assert response.status_code == 200, response.text
            assert response.json()["hypotheses"][0]["evidence"] == [
                {"evidence_id": evidence_id, "relation": "SUPPORTS"},
            ]
            assert client.get("/api/v1/investigations/missing/report").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_invalid_result_does_not_finish_or_leave_partial_rows(claimed):
    factory, _, claim = claimed
    batch = collect_evidence(MetricsOnly(), "incident-demo-api", START, END)
    assert save_evidence(factory, claim, batch)
    with factory() as session:
        own_id = session.scalar(select(Evidence.id))
    for bad in (
        low_draft("not-from-this-investigation", batch.gaps),
        AnalysisDraft("Unsupported", "Evidence limits: " + ", ".join(batch.gaps), (
            HypothesisDraft("Cause", "HIGH", batch.gaps,
                            (EvidenceLinkDraft(own_id, "SUPPORTS"),)),)),
        AnalysisDraft("Unsupported", "Evidence limits: " + ", ".join(batch.gaps), (
            HypothesisDraft("Cause", "LOW", batch.gaps,
                            (EvidenceLinkDraft(own_id, "CONTRADICTS"),)),)),
    ):
        with pytest.raises(AnalysisValidationError):
            complete_claim(factory, claim, bad)
    with factory() as session:
        assert session.get(InvestigationJob, claim.investigation_id).status == "RUNNING"
        assert session.scalars(select(Report)).all() == []
        assert session.scalars(select(Hypothesis)).all() == []


def test_capture_is_required_and_empty_capture_can_be_inconclusive(claimed):
    factory, engine, claim = claimed
    batch = collect_evidence(Empty(), "incident-demo-api", START, END)
    with pytest.raises(AnalysisValidationError, match="Capture evidence"):
        complete_claim(factory, claim, inconclusive(batch.gaps))
    assert save_evidence(factory, claim, batch)
    assert complete_claim(factory, claim, inconclusive(batch.gaps))
    with factory() as session:
        assert session.scalar(select(Report.summary)) == inconclusive(batch.gaps).summary
        assert session.scalars(select(Hypothesis)).all() == []


def test_reclaim_requires_new_attempt_capture_and_rejects_old_worker(claimed):
    factory, _, claim = claimed
    batch = collect_evidence(MetricsOnly(), "incident-demo-api", START, END)
    assert save_evidence(factory, claim, batch)
    with factory() as session:
        evidence_id = session.scalar(select(Evidence.id))
    reclaimed_at = datetime.now(timezone.utc) + timedelta(seconds=301)
    next_claim = claim_next_job(factory, "replacement-worker", now=reclaimed_at)
    assert next_claim is not None and next_claim.attempt == 2
    draft = low_draft(evidence_id, batch.gaps)
    assert complete_claim(factory, claim, draft, now=reclaimed_at) is False
    with pytest.raises(AnalysisValidationError, match="Capture evidence"):
        complete_claim(factory, next_claim, draft, now=reclaimed_at)
    assert save_evidence(factory, next_claim, batch, now=reclaimed_at)
    assert complete_claim(factory, next_claim, draft, now=reclaimed_at)


def test_completion_rejects_evidence_changed_after_capture(claimed):
    factory, _, claim = claimed
    batch = collect_evidence(MetricsOnly(), "incident-demo-api", START, END)
    assert save_evidence(factory, claim, batch)
    with factory.begin() as session:
        row = session.scalars(select(Evidence).order_by(Evidence.id)).first()
        evidence_id = row.id
        row.summary = "error_rate=0.9000/s"
    with pytest.raises(AnalysisValidationError, match="changed"):
        complete_claim(factory, claim, low_draft(evidence_id, batch.gaps))
    with factory() as session:
        assert session.scalar(select(Report.id)) is None
        assert session.get(InvestigationJob, claim.investigation_id).status == "RUNNING"
