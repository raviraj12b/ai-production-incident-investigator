"""Summarize a saved provider run (see run_provider.py) with explicit denominators.

Standard library only; reads saved files and never calls a provider:

    python evaluation/summarize_run.py evaluation/runs/<run_id>

It validates the run's accounting before reporting anything, reuses the 07.1
scorer unchanged for abstention, and publishes failures, NOT_CALLED cases and
validator rejections instead of dropping them. It does not compute accuracy or
any causal-quality figure.

Exit codes: 0 = summary produced, 2 = malformed, incomplete or inconsistent run.
"""

import argparse
import hashlib
import json
import statistics
import sys
from pathlib import Path

try:
    from score_abstention import load_corpus, load_outputs, score
except ImportError:  # imported as evaluation.summarize_run
    from evaluation.score_abstention import load_corpus, load_outputs, score


SUPPORTED_RUN_FORMAT = "07.2.1"
MAX_REPEATS = 10
OUTCOMES = {"OK", "NOT_CALLED", "UNAVAILABLE", "REFUSAL", "OUTPUT_INVALID"}
RECORD_KEYS = {"run_id", "case_id", "repeat", "outcome", "latency_ms", "abstained",
               "hypothesis_count", "citation_count", "validator", "error"}
ERROR_KEYS = {"type", "detail", "http_status", "timeout"}
DEFAULT_CORPUS = Path(__file__).with_name("corpus.json")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _read_records(path: Path) -> list[dict]:
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        _require(bool(line.strip()), f"Empty run record line {line_number}")
        row = json.loads(line)
        _require(isinstance(row, dict) and set(row) == RECORD_KEYS,
                 f"Malformed run record line {line_number}")
        records.append(row)
    return records


def _check_record(row: dict, run_id: str, repeats: int, case_ids: set[str]) -> None:
    where = f"{row.get('case_id')!r} repeat {row.get('repeat')!r}"
    _require(row["run_id"] == run_id, f"Record from another run: {where}")
    _require(row["case_id"] in case_ids, f"Unknown case in run records: {where}")
    _require(_is_int(row["repeat"]) and 1 <= row["repeat"] <= repeats, f"Bad repeat: {where}")
    outcome = row["outcome"]
    _require(outcome in OUTCOMES, f"Unknown outcome: {where}")
    if outcome == "NOT_CALLED":
        _require(all(row[key] is None for key in RECORD_KEYS - {"run_id", "case_id", "repeat", "outcome"}),
                 f"NOT_CALLED record carries provider data: {where}")
        return
    _require(_is_number(row["latency_ms"]), f"Missing latency: {where}")
    if outcome == "OK":
        validator = row["validator"]
        _require(isinstance(row["abstained"], bool) and _is_int(row["hypothesis_count"])
                 and row["hypothesis_count"] >= 0 and _is_int(row["citation_count"])
                 and row["citation_count"] >= 0 and row["error"] is None
                 and isinstance(validator, dict) and set(validator) == {"accepted", "reason"}
                 and isinstance(validator["accepted"], bool)
                 and (validator["reason"] is None) == validator["accepted"]
                 and (validator["accepted"] or isinstance(validator["reason"], str)),
                 f"Malformed OK record: {where}")
        return
    error = row["error"]
    _require(row["abstained"] is None and row["hypothesis_count"] is None
             and row["citation_count"] is None and row["validator"] is None
             and isinstance(error, dict) and set(error) == ERROR_KEYS
             and isinstance(error["timeout"], bool),
             f"Malformed failure record: {where}")


def load_run(run_dir: Path, corpus_path: Path) -> tuple[dict, dict, list[dict], dict]:
    """Validate the run against the corpus and return its parts."""
    cases = load_corpus(corpus_path)
    raw_corpus = corpus_path.read_bytes()
    metadata = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    _require(isinstance(metadata, dict) and metadata.get("format") == SUPPORTED_RUN_FORMAT,
             "Unsupported run format")
    _require(metadata.get("status") == "COMPLETE" and isinstance(metadata.get("finished_at"), str),
             "Run is not COMPLETE (interrupted or still running)")
    corpus_meta, plan = metadata.get("corpus"), metadata.get("plan")
    _require(isinstance(corpus_meta, dict) and isinstance(plan, dict), "Run metadata is incomplete")
    _require(corpus_meta.get("sha256") == hashlib.sha256(raw_corpus).hexdigest()
             and corpus_meta.get("version") == json.loads(raw_corpus)["version"],
             "Corpus differs from the one this run used")
    repeats = plan.get("repeats")
    _require(_is_int(repeats) and 1 <= repeats <= MAX_REPEATS, "Bad repeat count in run metadata")

    called = [case_id for case_id, case in cases.items() if case["model_input"]["evidence"]]
    not_called = [case_id for case_id in cases if case_id not in called]
    _require(plan.get("provider_called_cases") == called and plan.get("not_called_cases") == not_called
             and plan.get("planned_provider_calls") == repeats * len(called),
             "Run plan disagrees with the corpus")

    records = _read_records(run_dir / "runs.jsonl")
    for row in records:
        _check_record(row, metadata.get("run_id"), repeats, set(cases))
    expected = ({(case_id, repeat) for case_id in called for repeat in range(1, repeats + 1)}
                | {(case_id, 1) for case_id in not_called})
    seen = [(row["case_id"], row["repeat"]) for row in records]
    _require(len(seen) == len(set(seen)), "Duplicate attempt record")
    _require(set(seen) == expected, "Attempt records do not match the declared plan")
    for row in records:
        _require((row["outcome"] == "NOT_CALLED") == (row["case_id"] in not_called),
                 f"NOT_CALLED does not match the corpus for {row['case_id']}")

    outputs = {}
    for repeat in range(1, repeats + 1):
        ok_ids = {row["case_id"] for row in records
                  if row["repeat"] == repeat and row["outcome"] == "OK"}
        outputs[repeat] = load_outputs(run_dir / f"outputs-r{repeat}.jsonl", ok_ids)
        for row in records:
            if row["repeat"] != repeat or row["outcome"] != "OK":
                continue
            hypotheses = outputs[repeat][row["case_id"]]["hypotheses"]
            _require(all(isinstance(item, dict) and isinstance(item.get("links"), list)
                         for item in hypotheses), f"Malformed hypothesis for {row['case_id']}")
            _require(row["abstained"] == (not hypotheses) and row["hypothesis_count"] == len(hypotheses)
                     and row["citation_count"] == sum(len(item["links"]) for item in hypotheses),
                     f"Run record disagrees with saved output for {row['case_id']} repeat {repeat}")
    return metadata, cases, records, outputs


def _spread(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {"n": len(values), "min": round(min(values), 1),
            "median": round(statistics.median(values), 1), "max": round(max(values), 1)}


def summarize(run_dir: Path, corpus_path: Path = DEFAULT_CORPUS) -> dict:
    metadata, cases, records, outputs = load_run(run_dir, corpus_path)
    plan = metadata["plan"]
    repeats, called, not_called = plan["repeats"], plan["provider_called_cases"], plan["not_called_cases"]
    provider_attempts = [row for row in records if row["outcome"] != "NOT_CALLED"]
    by_outcome = {name: sum(row["outcome"] == name for row in records) for name in sorted(OUTCOMES)}
    ok_rows = [row for row in provider_attempts if row["outcome"] == "OK"]

    per_repeat, scored_total, matched_total = [], 0, 0
    per_case = {case_id: {"expected_abstain": cases[case_id]["expected_abstain"], "attempts": 0,
                          "ok": 0, "abstained": 0, "matched": 0, "outcomes": {}} for case_id in called}
    for repeat in range(1, repeats + 1):
        ok_ids = [case_id for case_id in called
                  if any(row["case_id"] == case_id and row["repeat"] == repeat and row["outcome"] == "OK"
                         for row in records)]
        result = score({case_id: cases[case_id] for case_id in ok_ids}, outputs[repeat])
        scored_total += result["evaluated"]
        matched_total += result["matched"]
        per_repeat.append({
            "repeat": repeat, "evaluated": result["evaluated"], "matched": result["matched"],
            "mismatches": [item["case_id"] for item in result["results"] if not item["matched"]],
            "not_scored": [case_id for case_id in called if case_id not in ok_ids],
        })
        for item in result["results"]:
            entry = per_case[item["case_id"]]
            entry["abstained"] += item["abstained"]
            entry["matched"] += item["matched"]
    for row in provider_attempts:
        entry = per_case[row["case_id"]]
        entry["attempts"] += 1
        entry["ok"] += row["outcome"] == "OK"
        entry["outcomes"][row["outcome"]] = entry["outcomes"].get(row["outcome"], 0) + 1
    for entry in per_case.values():
        if entry["ok"] < 2:
            entry["abstention_decision_across_repeats"] = "INSUFFICIENT_OK_ATTEMPTS"
        elif entry["abstained"] in (0, entry["ok"]):
            entry["abstention_decision_across_repeats"] = "CONSISTENT"
        else:
            entry["abstention_decision_across_repeats"] = "INCONSISTENT"

    rejected = [row for row in ok_rows if not row["validator"]["accepted"]]
    return {
        "run": {
            "run_id": metadata["run_id"], "status": metadata["status"],
            "corpus_version": metadata["corpus"]["version"], "corpus_sha256": metadata["corpus"]["sha256"],
            "provider": metadata.get("provider"), "prompt": metadata.get("prompt"),
            "repo": metadata.get("repo"), "repeats": repeats,
        },
        "denominators": {
            "corpus_cases": len(cases), "provider_called_cases": len(called),
            "not_called_cases": len(not_called), "planned_provider_calls": plan["planned_provider_calls"],
            "attempts_by_outcome": by_outcome,
        },
        "not_called": [{"case_id": case_id,
                        "note": "Fixed inconclusive result without a provider call; not a provider "
                                "result and excluded from every provider count below."}
                       for case_id in not_called],
        "provider_failures": [{
            "case_id": row["case_id"], "repeat": row["repeat"], "outcome": row["outcome"],
            "http_status": row["error"]["http_status"], "timeout": row["error"]["timeout"],
            "latency_ms": row["latency_ms"],
        } for row in provider_attempts if row["outcome"] != "OK"],
        "validator": {
            "ok_attempts": len(ok_rows), "accepted": len(ok_rows) - len(rejected),
            "rejected": len(rejected),
            "rejections": [{"case_id": row["case_id"], "repeat": row["repeat"],
                            "reason": row["validator"]["reason"]} for row in rejected],
            "note": "Production validator: cited IDs belong to the evidence and structural rules hold. "
                    "It does not show that a citation supports the explanation.",
        },
        "abstention": {
            "scope": "Provider OK attempts only, scored by the unchanged 07.1 scorer.",
            "scored_attempts": scored_total, "matched_attempts": matched_total,
            "of_planned_provider_calls": plan["planned_provider_calls"],
            "per_repeat": per_repeat, "per_case": per_case,
        },
        "latency_ms": {
            "scope": "Provider-called attempts as measured by the runner, failures included; "
                     "not a performance baseline.",
            "all_provider_attempts": _spread([row["latency_ms"] for row in provider_attempts]),
            "ok_attempts": _spread([row["latency_ms"] for row in ok_rows]),
        },
        "causal_quality": {
            "status": "NOT_ASSESSED",
            "reason": "Needs labeled cases with an identifiable cause and two human reviewers or an "
                      "adjudication record; the 07.1 corpus has only abstention-expected cases.",
        },
        "limits": ["Abstention and accounting only; no semantic citation support, causal truth or "
                   "root-cause accuracy is measured.",
                   "The repeats are a small repeatability sample, not a statistically significant study."],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path, help="Directory produced by run_provider")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(summarize(args.run_dir, args.corpus), indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(f"Run summary error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
