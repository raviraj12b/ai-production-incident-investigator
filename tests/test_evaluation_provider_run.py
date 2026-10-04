"""Provider-run accounting, using only a mocked transport. No live provider call."""

import hashlib
import json
from pathlib import Path

import httpx
import pytest

from backend import analysis_pipeline, model_adapter
from backend.analysis_pipeline import (
    AnalysisDraft, AnalysisValidationError, EvidenceLinkDraft, HypothesisDraft,
)
from backend.model_adapter import DEFAULT_MODEL, EvidenceView, GroqAnalyzer
from evaluation import run_provider, summarize_run
from evaluation.run_provider import prompt_fingerprint, run_evaluation, validate_draft
from evaluation.score_abstention import load_corpus, load_outputs, score


CORPUS = Path(run_provider.__file__).with_name("corpus.json")
SECRET = "sk-test-secret-value"
CALLED = {"isolated-server-error", "mixed-status-and-trace"}


def completion(content=None, refusal=None):
    message = {"role": "assistant", "content": content}
    if refusal:
        message["refusal"] = refusal
    return httpx.Response(200, json={"object": "chat.completion", "choices": [
        {"finish_reason": "stop", "message": message},
    ]})


def request_input(request):
    return json.loads(json.loads(request.content)["messages"][1]["content"])


def reply(request, *, abstain_single=True, cited_id=None):
    payload = request_input(request)
    uncertainty = "Evidence limits: " + ", ".join(payload["gaps"]) + "."
    ids = [row["evidence_id"] for row in payload["evidence"]]
    if abstain_single and len(ids) == 1:
        hypotheses = []
    else:
        hypotheses = [{"explanation": "A downstream dependency may be failing.",
                       "confidence": "LOW",
                       "links": [{"evidence_id": cited_id or ids[0], "relation": "SUPPORTS"}]}]
    return completion(json.dumps({"summary": "Review required.", "uncertainty": uncertainty,
                                  "hypotheses": hypotheses}))


def run(tmp_path, handler, **kwargs):
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        analyzer = GroqAnalyzer(SECRET, DEFAULT_MODEL, client)
        run_dir = run_evaluation(CORPUS, analyzer, tmp_path, run_id="run-test", **kwargs)
    rows = [json.loads(line) for line in
            (run_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    return run_dir, rows


def test_repeats_are_declared_before_the_first_call_and_empty_evidence_is_not_called(tmp_path):
    calls = []

    def handler(request):
        declared = json.loads((tmp_path / "run-test" / "run.json").read_text(encoding="utf-8"))
        assert declared["status"] == "DECLARED" and declared["plan"]["repeats"] == 3
        calls.append(request_input(request)["evidence"][0]["evidence_id"])
        return reply(request)

    run_dir, rows = run(tmp_path, handler)

    assert len(calls) == 6  # 2 provider-called cases x 3 repeats; never the empty case
    metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "COMPLETE" and metadata["finished_at"]
    assert metadata["plan"] == {
        "repeats": 3,
        "provider_called_cases": ["isolated-server-error", "mixed-status-and-trace"],
        "not_called_cases": ["no-observations"], "planned_provider_calls": 6,
        "note": metadata["plan"]["note"],
    }
    assert metadata["corpus"]["sha256"] == hashlib.sha256(CORPUS.read_bytes()).hexdigest()
    assert metadata["corpus"]["version"] == "07.1.0"
    assert metadata["provider"]["model"] == DEFAULT_MODEL
    assert metadata["prompt"]["sha256"] == prompt_fingerprint()

    assert [row["outcome"] for row in rows].count("NOT_CALLED") == 1
    assert [row["outcome"] for row in rows].count("OK") == 6
    assert all(row["validator"] == {"accepted": True, "reason": None}
               for row in rows if row["outcome"] == "OK")

    # Each repeat's outputs file is a valid input for the unchanged 07.1 scorer.
    cases = {case_id: case for case_id, case in load_corpus(CORPUS).items() if case_id in CALLED}
    for repeat in (1, 2, 3):
        result = score(cases, load_outputs(run_dir / f"outputs-r{repeat}.jsonl", set(CALLED)))
        assert (result["evaluated"], result["matched"]) == (2, 1)


@pytest.mark.parametrize("mode, outcome, status, timeout", [
    ("rate_limit", "UNAVAILABLE", 429, False),
    ("timeout", "UNAVAILABLE", None, True),
    ("refusal", "REFUSAL", None, False),
    ("invalid", "OUTPUT_INVALID", None, False),
])
def test_provider_failures_are_recorded_and_produce_no_output(tmp_path, mode, outcome, status, timeout):
    def handler(request):
        if mode == "rate_limit":
            return httpx.Response(429, json={"error": "rate limit"})
        if mode == "timeout":
            raise httpx.ReadTimeout("slow", request=request)
        if mode == "refusal":
            return completion(None, "Cannot answer")
        return completion("not json")

    run_dir, rows = run(tmp_path, handler, repeats=1)

    failed = [row for row in rows if row["case_id"] in CALLED]
    assert len(failed) == 2 and {row["outcome"] for row in failed} == {outcome}
    for row in failed:
        assert row["error"]["http_status"] == status and row["error"]["timeout"] is timeout
        assert row["validator"] is None and row["abstained"] is None
        assert isinstance(row["latency_ms"], float)
    assert (run_dir / "outputs-r1.jsonl").read_text(encoding="utf-8") == ""
    assert [row["outcome"] for row in rows if row["case_id"] == "no-observations"] == ["NOT_CALLED"]


def test_unknown_citation_is_a_provider_output_rejected_by_the_production_validator(tmp_path):
    bad_id = "ffffffff-0000-4000-8000-000000000009"
    run_dir, rows = run(tmp_path, lambda request: reply(request, abstain_single=False,
                                                        cited_id=bad_id), repeats=1)

    called = [row for row in rows if row["case_id"] in CALLED]
    assert {row["outcome"] for row in called} == {"OK"}
    assert all(row["validator"] == {"accepted": False,
                                    "reason": "Evidence reference is outside this investigation"}
               for row in called)
    assert len((run_dir / "outputs-r1.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def evidence_view():
    return EvidenceView("a" * 36, "LOG", model_adapter.datetime.fromisoformat(
        "2026-09-18T10:01:00+00:00"), "incident-demo-api", "request_failed (HTTP 503)")


def draft(confidence="LOW", gaps=("NO_TRACES",)):
    return AnalysisDraft("Review required.", "Evidence limits: NO_TRACES.", (HypothesisDraft(
        "A dependency may be failing.", confidence, gaps,
        (EvidenceLinkDraft("a" * 36, "SUPPORTS"),)),))


def test_validation_uses_the_production_validator(monkeypatch):
    evidence, gaps = (evidence_view(),), ("NO_TRACES",)
    assert validate_draft(draft(), evidence, gaps) == {"accepted": True, "reason": None}
    assert validate_draft(draft("HIGH"), evidence, gaps) == {
        "accepted": False, "reason": "Confidence exceeds available evidence"}

    def sentinel(*_):
        raise AnalysisValidationError("sentinel from the production module")

    monkeypatch.setattr(analysis_pipeline, "_validate", sentinel)
    assert validate_draft(draft(), evidence, gaps) == {
        "accepted": False, "reason": "sentinel from the production module"}


def test_secret_never_reaches_artifacts(tmp_path):
    run_dir, _ = run(tmp_path, reply)
    for path in run_dir.iterdir():
        text = path.read_text(encoding="utf-8")
        assert SECRET not in text and "Bearer" not in text and "Authorization" not in text


def test_run_is_never_overwritten_and_inputs_are_checked(tmp_path):
    run(tmp_path, reply)
    with pytest.raises(FileExistsError):
        run(tmp_path, reply)
    with httpx.Client(transport=httpx.MockTransport(reply)) as client:
        analyzer = GroqAnalyzer(SECRET, DEFAULT_MODEL, client)
        for kwargs in ({"repeats": 0}, {"repeats": 11}, {"run_id": "../escape"}):
            with pytest.raises(ValueError):
                run_evaluation(CORPUS, analyzer, tmp_path / "other", **kwargs)
        assert not (tmp_path / "other").exists()


def test_prompt_fingerprint_follows_the_instructions(monkeypatch):
    before = prompt_fingerprint()
    monkeypatch.setattr(model_adapter, "SYSTEM_INSTRUCTIONS", "changed")
    assert prompt_fingerprint() != before


def test_missing_credentials_fail_before_any_file_is_written(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert run_provider.main(["--output-root", str(tmp_path / "runs")]) == 2
    assert not (tmp_path / "runs").exists()
    assert "GROQ_API_KEY" in capsys.readouterr().err


def test_summarizer_accepts_what_the_runner_writes(tmp_path):
    bad_id = "ffffffff-0000-4000-8000-000000000009"

    def handler(request):
        if len(request_input(request)["evidence"]) == 1:
            return httpx.Response(429, json={"error": "rate limit"})
        return reply(request, abstain_single=False, cited_id=bad_id)

    run_dir, _ = run(tmp_path, handler)
    summary = summarize_run.summarize(run_dir, CORPUS)

    assert summary["denominators"]["planned_provider_calls"] == 6
    assert summary["denominators"]["attempts_by_outcome"] == {
        "NOT_CALLED": 1, "OK": 3, "OUTPUT_INVALID": 0, "REFUSAL": 0, "UNAVAILABLE": 3}
    assert [f["http_status"] for f in summary["provider_failures"]] == [429, 429, 429]
    assert summary["validator"]["rejected"] == 3
    assert (summary["abstention"]["scored_attempts"], summary["abstention"]["matched_attempts"]) == (3, 0)
    assert summary["causal_quality"]["status"] == "NOT_ASSESSED"
