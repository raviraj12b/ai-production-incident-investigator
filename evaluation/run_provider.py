"""Run the frozen evaluation corpus through the real analyzer and save run records.

Run from the repository root (this module imports the backend package):

    python -m evaluation.run_provider --repeats 3

It reuses the production adapter (`GroqAnalyzer.analyze`) and the production
result validator (`analysis_pipeline._validate`); it does not reimplement
either. It never reads the corpus labels, never writes the API key, and makes
no quality or causal-accuracy claim. Scoring and review are separate steps.

Each run directory contains:
  run.json            declared before the first provider call, finalized after
  runs.jsonl          one record per attempt, every outcome including failures
  outputs-r<N>.jsonl  usable provider results for repeat N, in the format the
                      07.1 scorer reads (only attempts with outcome OK)
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from backend import analysis_pipeline, model_adapter
from backend.analysis_pipeline import AnalysisDraft
from backend.model_adapter import (
    EvidenceView, GroqAnalyzer, ModelOutputInvalid, ModelRefusal, ModelUnavailable,
)
from evaluation.score_abstention import load_corpus


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = Path(__file__).with_name("corpus.json")
DEFAULT_OUTPUT_ROOT = Path(__file__).with_name("scratch")
DEFAULT_REPEATS = 3
MAX_REPEATS = 10
RUN_FORMAT = "07.2.1"
RUN_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


def prompt_fingerprint() -> str:
    """Content hash of the model instructions and response schema in use.

    The adapter has no prompt version constant; this ties a run to the exact
    text and schema. It does not cover other request parameters.
    """
    canonical = json.dumps(
        {"system_instructions": model_adapter.SYSTEM_INSTRUCTIONS, "schema": model_adapter.SCHEMA},
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_draft(
    draft: AnalysisDraft, evidence: tuple[EvidenceView, ...], gaps: tuple[str, ...],
) -> dict:
    """Ask the production validator whether it would accept this draft.

    `_validate` only uses the evidence mapping for ID membership, so the
    corpus evidence IDs stand in for captured database rows.
    """
    try:
        analysis_pipeline._validate(draft, {item.id: item for item in evidence}, gaps)
    except analysis_pipeline.AnalysisValidationError as exc:
        return {"accepted": False, "reason": str(exc)}
    return {"accepted": True, "reason": None}


def output_row(draft: AnalysisDraft) -> dict:
    return {
        "summary": draft.summary,
        "uncertainty": draft.uncertainty,
        "hypotheses": [{
            "explanation": hypothesis.explanation,
            "confidence": hypothesis.confidence,
            "links": [{"evidence_id": link.evidence_id, "relation": link.relation}
                      for link in hypothesis.links],
        } for hypothesis in draft.hypotheses],
    }


def failure_record(exc: Exception) -> tuple[str, dict]:
    """Classify a provider failure using only fixed adapter messages."""
    if isinstance(exc, ModelUnavailable):
        cause = exc.__cause__
        return "UNAVAILABLE", {
            "type": type(exc).__name__, "detail": str(exc),
            "http_status": (cause.response.status_code
                            if isinstance(cause, httpx.HTTPStatusError) else None),
            "timeout": isinstance(cause, httpx.TimeoutException),
        }
    outcome = "REFUSAL" if isinstance(exc, ModelRefusal) else "OUTPUT_INVALID"
    return outcome, {"type": type(exc).__name__, "detail": str(exc),
                     "http_status": None, "timeout": False}


def _views(model_input: dict) -> tuple[tuple[EvidenceView, ...], tuple[str, ...]]:
    evidence = tuple(EvidenceView(
        id=row["evidence_id"], kind=row["kind"],
        observed_at=datetime.fromisoformat(row["observed_at"]),
        service=row["service"], summary=row["summary"], trace_id=row["trace_id"],
    ) for row in model_input["evidence"])
    return evidence, tuple(model_input["gaps"])


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, timeout=10,
                              cwd=REPO_ROOT, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _write_json(path: Path, document: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_evaluation(
    corpus_path: Path, analyzer: GroqAnalyzer, output_root: Path, *,
    repeats: int = DEFAULT_REPEATS, run_id: str | None = None,
) -> Path:
    """Execute the run and return its directory. Never overwrites an existing run."""
    if not isinstance(analyzer, GroqAnalyzer):
        raise ValueError("The run needs a GroqAnalyzer")
    if not isinstance(repeats, int) or not 1 <= repeats <= MAX_REPEATS:
        raise ValueError(f"repeats must be between 1 and {MAX_REPEATS}")
    run_id = run_id or f"run-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    if not RUN_ID_RE.fullmatch(run_id):
        raise ValueError("Invalid run ID")

    cases = load_corpus(corpus_path)
    raw_corpus = corpus_path.read_bytes()
    prepared = {case_id: _views(case["model_input"]) for case_id, case in cases.items()}
    called = [case_id for case_id, (evidence, _) in prepared.items() if evidence]
    not_called = [case_id for case_id in prepared if case_id not in called]

    porcelain = _git("status", "--porcelain")
    metadata = {
        "format": RUN_FORMAT, "run_id": run_id, "status": "DECLARED",
        "started_at": _now(), "finished_at": None,
        "corpus": {"file": corpus_path.name, "version": json.loads(raw_corpus)["version"],
                   "sha256": hashlib.sha256(raw_corpus).hexdigest()},
        "provider": {"name": "groq", "endpoint_host": urlsplit(model_adapter.API_URL).hostname,
                     "model": analyzer.model},
        "prompt": {"sha256": prompt_fingerprint(),
                   "covers": "system instructions and response schema only"},
        "plan": {"repeats": repeats, "provider_called_cases": called,
                 "not_called_cases": not_called,
                 "planned_provider_calls": repeats * len(called),
                 "note": "Small repeatability sample, not a statistically significant study."},
        "repo": {"commit": _git("rev-parse", "HEAD"),
                 "dirty": None if porcelain is None else bool(porcelain)},
    }

    run_dir = output_root / run_id
    run_dir.mkdir(parents=True)  # FileExistsError when the run already exists
    _write_json(run_dir / "run.json", metadata)  # declared before any provider call
    output_paths = {n: run_dir / f"outputs-r{n}.jsonl" for n in range(1, repeats + 1)}
    for path in output_paths.values():
        path.write_text("", encoding="utf-8")

    with (run_dir / "runs.jsonl").open("a", encoding="utf-8") as runs:
        def record(**fields):
            runs.write(json.dumps({"run_id": run_id, **fields}, sort_keys=True) + "\n")
            runs.flush()

        for repeat in range(1, repeats + 1):
            for case_id in cases:
                evidence, gaps = prepared[case_id]
                if not evidence:
                    # The adapter and worker return a fixed result with no provider call.
                    if repeat == 1:
                        record(case_id=case_id, repeat=1, outcome="NOT_CALLED", latency_ms=None,
                               abstained=None, hypothesis_count=None, citation_count=None,
                               validator=None, error=None)
                    continue
                started = time.perf_counter()
                try:
                    draft = analyzer.analyze(evidence, gaps)
                except (ModelUnavailable, ModelOutputInvalid) as exc:
                    outcome, error = failure_record(exc)
                    record(case_id=case_id, repeat=repeat, outcome=outcome,
                           latency_ms=round((time.perf_counter() - started) * 1000, 1),
                           abstained=None, hypothesis_count=None, citation_count=None,
                           validator=None, error=error)
                    continue
                latency_ms = round((time.perf_counter() - started) * 1000, 1)
                with output_paths[repeat].open("a", encoding="utf-8") as outputs:
                    outputs.write(json.dumps({"case_id": case_id, "output": output_row(draft)},
                                             sort_keys=True) + "\n")
                record(case_id=case_id, repeat=repeat, outcome="OK", latency_ms=latency_ms,
                       abstained=not draft.hypotheses, hypothesis_count=len(draft.hypotheses),
                       citation_count=sum(len(item.links) for item in draft.hypotheses),
                       validator=validate_draft(draft, evidence, gaps), error=None)

    _write_json(run_dir / "run.json", {**metadata, "status": "COMPLETE", "finished_at": _now()})
    return run_dir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT,
                        help="Parent directory for run directories (default is git-ignored)")
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    try:
        analyzer = GroqAnalyzer.from_environment()
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    try:
        with analyzer:
            run_dir = run_evaluation(args.corpus, analyzer, args.output_root,
                                     repeats=args.repeats, run_id=args.run_id)
    except (OSError, ValueError) as exc:
        print(f"Evaluation run error: {exc}", file=sys.stderr)
        return 2
    outcomes: dict[str, int] = {}
    for line in (run_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines():
        outcome = json.loads(line)["outcome"]
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    print(json.dumps({"run_dir": str(run_dir), "status": "COMPLETE", "attempts_by_outcome": outcomes},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
