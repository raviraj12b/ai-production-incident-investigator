"""Worker handoffs, safe model input, and bounded failure transitions."""

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.analysis_pipeline import AnalysisDraft, EvidenceLinkDraft, HypothesisDraft
from backend.database import Base
from backend.model_adapter import (
    DEFAULT_MODEL, EvidenceView, GroqAnalyzer, ModelOutputInvalid, ModelUnavailable,
)
from backend.models import Evidence, Incident, Investigation, InvestigationJob, Report
from backend.telemetry_gateway import TelemetryUnavailable
from backend.worker import main, run_once


START = datetime(2026, 9, 18, 10, tzinfo=timezone.utc)
END = START + timedelta(minutes=15)


@pytest.fixture
def queued():
    engine = create_engine("sqlite+pysqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory.begin() as session:
        incident = Incident(title="Private incident user@example.com",
                            description="Never send this detail to model",
                            service="incident-demo-api", severity="HIGH",
                            window_start=START, window_end=END)
        session.add(incident)
        session.flush()
        investigation = Investigation(incident_id=incident.id,
                                      window_start=START, window_end=END)
        session.add(investigation)
        session.flush()
        session.add(InvestigationJob(investigation_id=investigation.id))
        investigation_id = investigation.id
    try:
        yield factory, investigation_id
    finally:
        engine.dispose()


class FakeGateway:
    def query_logs(self, query):
        return [{"source": "loki", "service": query.service,
                 "timestamp_ns": str(int((START + timedelta(minutes=1)).timestamp() * 1_000_000_000)),
                 "event": "request_failed", "status_code": 503,
                 "message": "private-token user@example.com"}]

    def query_metrics(self, query, metric="request_rate"):
        return [{"source": "prometheus", "service": query.service, "metric": metric,
                 "timestamp": (START + timedelta(minutes=2)).timestamp(), "value": 0.1}]

    def query_traces(self, query):
        return []


class FakeAnalyzer:
    def __init__(self):
        self.received = None

    def analyze(self, evidence, gaps):
        self.received = evidence, gaps
        return AnalysisDraft("Possible dependency failure; review required.",
                             "Evidence limits: " + ", ".join(gaps) + ".",
                             (HypothesisDraft("A dependency may be failing.", "LOW", gaps,
                                              (EvidenceLinkDraft(evidence[0].id, "SUPPORTS"),)),))


def test_worker_completes_with_only_redacted_evidence_sent_to_model(queued):
    factory, investigation_id = queued
    analyzer = FakeAnalyzer()
    assert run_once(factory, FakeGateway(), analyzer, "worker-1") == "DONE"
    assert run_once(factory, FakeGateway(), analyzer, "worker-1") == "IDLE"
    payload, gaps = analyzer.received
    assert len(payload) == 3 and "NO_TRACES" in gaps
    assert "private-token" not in repr(payload)
    assert "user@example.com" not in repr(payload)
    assert "Never send this detail" not in repr(payload)
    with factory() as session:
        assert session.get(Investigation, investigation_id).status == "AWAITING_REVIEW"
        assert session.get(InvestigationJob, investigation_id).status == "DONE"
        assert session.scalar(select(Report.id)) is not None


def test_backend_outage_retries_without_report_or_empty_capture(queued):
    factory, investigation_id = queued

    class Down(FakeGateway):
        def query_traces(self, query):
            raise TelemetryUnavailable("Jaeger unavailable")

    assert run_once(factory, Down(), FakeAnalyzer(), "worker-1") == "HANDLED_FAILURE"
    with factory() as session:
        job = session.get(InvestigationJob, investigation_id)
        assert job.status == "QUEUED" and job.attempts == 1
        assert session.get(Investigation, investigation_id).error == "TELEMETRY_UNAVAILABLE"
        assert session.scalar(select(Report.id)) is None
        assert session.scalars(select(Evidence)).all() == []


def test_model_failure_keeps_evidence_and_schedules_retry(queued):
    factory, investigation_id = queued

    class DownAnalyzer:
        def analyze(self, evidence, gaps):
            raise ModelUnavailable("Backend was unavailable")

    assert run_once(factory, FakeGateway(), DownAnalyzer(), "worker-1") == "HANDLED_FAILURE"
    with factory() as session:
        job = session.get(InvestigationJob, investigation_id)
        assert job.status == "QUEUED" and job.attempts == 1
        assert session.get(Investigation, investigation_id).error == "MODEL_UNAVAILABLE"
        assert session.scalar(select(Report.id)) is None
        assert len(session.scalars(select(Evidence)).all()) == 3


def test_unsupported_analysis_cannot_finish_the_claim(queued):
    factory, investigation_id = queued

    class InventedEvidence:
        def analyze(self, evidence, gaps):
            return AnalysisDraft("False cause", "Evidence limits: " + ", ".join(gaps),
                                 (HypothesisDraft("Invented cause", "LOW", gaps,
                                                  (EvidenceLinkDraft("not-an-evidence-id", "SUPPORTS"),)),))

    assert run_once(factory, FakeGateway(), InventedEvidence(), "worker-1") == "HANDLED_FAILURE"
    with factory() as session:
        assert session.get(Investigation, investigation_id).error == "RESULT_INVALID"
        assert session.scalar(select(Report.id)) is None
        assert len(session.scalars(select(Evidence)).all()) == 3


def test_empty_successful_capture_is_inconclusive_without_model_call(queued):
    factory, investigation_id = queued

    class Empty(FakeGateway):
        def query_logs(self, query):
            return []

        def query_metrics(self, query, metric="request_rate"):
            return []

    class MustNotBeCalled:
        def analyze(self, evidence, gaps):
            raise AssertionError("No model call should be made")

    assert run_once(factory, Empty(), MustNotBeCalled(), "worker-1") == "DONE"
    with factory() as session:
        assert session.get(Investigation, investigation_id).status == "AWAITING_REVIEW"
        assert session.scalar(select(Report.summary)) == "Root cause undetermined from available evidence."


def test_once_can_target_a_new_job_without_consuming_older_queued_jobs(queued):
    factory, investigation_id = queued
    with factory.begin() as session:
        older_incident = Incident(title="Earlier incident", service="incident-demo-api",
                                  severity="LOW", window_start=START, window_end=END)
        session.add(older_incident)
        session.flush()
        older = Investigation(incident_id=older_incident.id, window_start=START, window_end=END)
        session.add(older)
        session.flush()
        older_id = older.id
        session.add(InvestigationJob(investigation_id=older_id,
                                     available_at=START))
    assert run_once(factory, FakeGateway(), FakeAnalyzer(), "worker-target",
                    investigation_id=investigation_id) == "DONE"
    with factory() as session:
        assert session.get(InvestigationJob, older_id).status == "QUEUED"
        assert session.get(InvestigationJob, investigation_id).status == "DONE"


def test_cli_requires_explicit_model_config_before_claim(queued, monkeypatch):
    factory, investigation_id = queued
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    with pytest.raises(SystemExit) as error:
        main(["--once"])
    assert error.value.code == 2
    with factory() as session:
        assert session.get(InvestigationJob, investigation_id).status == "QUEUED"


def test_groq_default_model_needs_only_a_groq_key(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "fake-key")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    with GroqAnalyzer.from_environment() as analyzer:
        assert analyzer.model == DEFAULT_MODEL == "openai/gpt-oss-20b"


def test_groq_adapter_sends_only_bounded_normalized_data_and_handles_refusal():
    calls = []

    def handler(request):
        assert str(request.url) == "https://api.groq.com/openai/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer fake-key"
        calls.append(json.loads(request.content))
        model_text = json.dumps({
            "summary": "Potential failure, review required.",
            "uncertainty": "Missing: NO_TRACES, CHANGE_FEED_NOT_CONFIGURED.",
            "hypotheses": [{"explanation": "May be a downstream error", "confidence": "LOW",
                            "links": [{"evidence_id": "a" * 36, "relation": "SUPPORTS"}]}],
        })
        return httpx.Response(200, json={"object": "chat.completion", "choices": [
            {"finish_reason": "stop", "message": {"role": "assistant", "content": model_text}},
        ]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        analyzer = GroqAnalyzer("fake-key", DEFAULT_MODEL, client)
        evidence = (EvidenceView("a" * 36, "LOG", START, "incident-demo-api",
                                 "request_failed (HTTP 503)"),)
        gaps = ("NO_TRACES", "CHANGE_FEED_NOT_CONFIGURED")
        result = analyzer.analyze(evidence, gaps)
        assert result.hypotheses[0].missing_evidence == gaps
        assert result.hypotheses[0].links[0].evidence_id == evidence[0].id
        assert "store" not in calls[0] and calls[0]["max_completion_tokens"] == 2048
        assert "private-token" not in json.dumps(calls[0])
        assert calls[0]["response_format"]["json_schema"]["strict"] is True
        with pytest.raises(ModelOutputInvalid):
            analyzer.analyze((EvidenceView(evidence[0].id, "LOG", START,
                                           "incident-demo-api", "private-token"),), gaps)
        assert len(calls) == 1

        def refusal(request):
            return httpx.Response(200, json={"object": "chat.completion", "choices": [
                {"finish_reason": "stop", "message": {"role": "assistant",
                                                     "content": None, "refusal": "Cannot answer"}},
            ]})

    with httpx.Client(transport=httpx.MockTransport(refusal)) as client:
        with pytest.raises(ModelOutputInvalid):
            GroqAnalyzer("fake-key", DEFAULT_MODEL, client).analyze(evidence, gaps)

    with httpx.Client(transport=httpx.MockTransport(
        lambda request: httpx.Response(429, json={"error": "rate limit"}),
    )) as client:
        with pytest.raises(ModelUnavailable):
            GroqAnalyzer("fake-key", DEFAULT_MODEL, client).analyze(evidence, gaps)
