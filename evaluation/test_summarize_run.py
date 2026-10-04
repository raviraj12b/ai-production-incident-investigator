import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import summarize_run


CORPUS = Path(__file__).with_name("corpus.json")
CALLED = ["isolated-server-error", "mixed-status-and-trace"]
HYPOTHESIS = {"explanation": "A dependency may be failing.", "confidence": "LOW",
              "links": [{"evidence_id": "e1", "relation": "SUPPORTS"}]}


def ok(abstain, accepted=True, reason=None):
    return {"outcome": "OK", "abstain": abstain, "accepted": accepted, "reason": reason, "latency": 120.0}


def failed(outcome, status=None, timeout=False):
    return {"outcome": outcome, "status": status, "timeout": timeout, "latency": 50.0}


def make_run(root: Path, plan=None, repeats=3) -> Path:
    """Write a run directory by hand, independent of run_provider.

    Default: the isolated case abstains and the mixed case gives one hypothesis.
    """
    plan = plan or {}
    run_dir = root / "run-x"
    run_dir.mkdir()
    corpus_bytes = CORPUS.read_bytes()
    (run_dir / "run.json").write_text(json.dumps({
        "format": "07.2.1", "run_id": "run-x", "status": "COMPLETE",
        "started_at": "2026-10-03T00:00:00+00:00", "finished_at": "2026-10-03T00:01:00+00:00",
        "corpus": {"file": "corpus.json", "version": json.loads(corpus_bytes)["version"],
                   "sha256": hashlib.sha256(corpus_bytes).hexdigest()},
        "provider": {"name": "groq", "endpoint_host": "api.groq.com", "model": "m"},
        "prompt": {"sha256": "p", "covers": "x"}, "repo": {"commit": "c", "dirty": False},
        "plan": {"repeats": repeats, "provider_called_cases": CALLED,
                 "not_called_cases": ["no-observations"], "planned_provider_calls": repeats * 2,
                 "note": "n"},
    }), encoding="utf-8")
    records = [{"run_id": "run-x", "case_id": "no-observations", "repeat": 1, "outcome": "NOT_CALLED",
                "latency_ms": None, "abstained": None, "hypothesis_count": None,
                "citation_count": None, "validator": None, "error": None}]
    outputs = {n: [] for n in range(1, repeats + 1)}
    for repeat in range(1, repeats + 1):
        for case_id in CALLED:
            spec = plan.get((case_id, repeat), ok(case_id == CALLED[0]))
            record = {"run_id": "run-x", "case_id": case_id, "repeat": repeat,
                      "outcome": spec["outcome"], "latency_ms": spec["latency"], "abstained": None,
                      "hypothesis_count": None, "citation_count": None, "validator": None, "error": None}
            if spec["outcome"] == "OK":
                hypotheses = [] if spec["abstain"] else [HYPOTHESIS]
                record.update(abstained=spec["abstain"], hypothesis_count=len(hypotheses),
                              citation_count=len(hypotheses),
                              validator={"accepted": spec["accepted"], "reason": spec["reason"]})
                outputs[repeat].append({"case_id": case_id, "output": {
                    "summary": "s", "uncertainty": "u", "hypotheses": hypotheses}})
            else:
                record["error"] = {"type": "T", "detail": "d", "http_status": spec["status"],
                                   "timeout": spec["timeout"]}
            records.append(record)
    write_records(run_dir, records)
    for repeat, rows in outputs.items():
        write_jsonl(run_dir / f"outputs-r{repeat}.jsonl", rows)
    return run_dir


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def write_records(run_dir, records):
    write_jsonl(run_dir / "runs.jsonl", records)


def read_records(run_dir):
    return [json.loads(line) for line in (run_dir / "runs.jsonl").read_text(encoding="utf-8").splitlines()]


def all_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from all_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from all_keys(item)


class SummarizeRunTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)

    def test_complete_run_reports_denominators_without_a_quality_claim(self):
        summary = summarize_run.summarize(make_run(self.root), CORPUS)

        self.assertEqual(summary["denominators"], {
            "corpus_cases": 3, "provider_called_cases": 2, "not_called_cases": 1,
            "planned_provider_calls": 6,
            "attempts_by_outcome": {"NOT_CALLED": 1, "OK": 6, "OUTPUT_INVALID": 0,
                                    "REFUSAL": 0, "UNAVAILABLE": 0}})
        self.assertEqual([item["case_id"] for item in summary["not_called"]], ["no-observations"])
        self.assertEqual((summary["abstention"]["scored_attempts"],
                          summary["abstention"]["matched_attempts"]), (6, 3))
        self.assertTrue(all(item["evaluated"] == 2 and item["matched"] == 1
                            and item["mismatches"] == ["mixed-status-and-trace"]
                            for item in summary["abstention"]["per_repeat"]))
        self.assertEqual(summary["validator"]["accepted"], 6)
        self.assertEqual(summary["causal_quality"]["status"], "NOT_ASSESSED")
        self.assertEqual(summary["latency_ms"]["ok_attempts"],
                         {"n": 6, "min": 120.0, "median": 120.0, "max": 120.0})
        self.assertFalse([key for key in all_keys(summary) if "accuracy" in key.lower()])
        self.assertTrue(all(case["abstention_decision_across_repeats"] == "CONSISTENT"
                            for case in summary["abstention"]["per_case"].values()))

    def test_failures_rejections_and_inconsistency_are_published_not_dropped(self):
        reason = "Evidence reference is outside this investigation"
        plan = {
            (CALLED[0], 1): failed("UNAVAILABLE", status=429),
            (CALLED[1], 2): failed("REFUSAL"),
            (CALLED[1], 3): ok(False, accepted=False, reason=reason),
            (CALLED[0], 3): ok(False),  # abstains in repeat 2, not in repeat 3
        }
        summary = summarize_run.summarize(make_run(self.root, plan), CORPUS)

        self.assertEqual(summary["denominators"]["attempts_by_outcome"]["UNAVAILABLE"], 1)
        self.assertEqual(summary["denominators"]["attempts_by_outcome"]["REFUSAL"], 1)
        self.assertEqual([(f["case_id"], f["repeat"], f["outcome"], f["http_status"])
                          for f in summary["provider_failures"]],
                         [(CALLED[0], 1, "UNAVAILABLE", 429), (CALLED[1], 2, "REFUSAL", None)])
        self.assertEqual(summary["validator"]["rejections"],
                         [{"case_id": CALLED[1], "repeat": 3, "reason": reason}])
        repeat_one = summary["abstention"]["per_repeat"][0]
        self.assertEqual((repeat_one["evaluated"], repeat_one["not_scored"]), (1, [CALLED[0]]))
        self.assertEqual(summary["abstention"]["scored_attempts"], 4)
        isolated = summary["abstention"]["per_case"][CALLED[0]]
        self.assertEqual((isolated["attempts"], isolated["ok"], isolated["abstained"]), (3, 2, 1))
        self.assertEqual(isolated["abstention_decision_across_repeats"], "INCONSISTENT")

    def test_case_with_fewer_than_two_ok_attempts_has_insufficient_repeat_data(self):
        plan = {(CALLED[0], n): failed("UNAVAILABLE", timeout=True) for n in (1, 2)}
        summary = summarize_run.summarize(make_run(self.root, plan), CORPUS)
        self.assertEqual(summary["abstention"]["per_case"][CALLED[0]]
                         ["abstention_decision_across_repeats"], "INSUFFICIENT_OK_ATTEMPTS")

    def test_inconsistent_or_incomplete_runs_are_rejected(self):
        def tamper_metadata(run_dir, change):
            path = run_dir / "run.json"
            metadata = json.loads(path.read_text(encoding="utf-8"))
            change(metadata)
            path.write_text(json.dumps(metadata), encoding="utf-8")

        def tamper_records(run_dir, change):
            records = read_records(run_dir)
            change(records)
            write_records(run_dir, records)

        def tamper_outputs(run_dir, change):
            path = run_dir / "outputs-r1.jsonl"
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
            change(rows)
            write_jsonl(path, rows)

        cases = {
            "interrupted run": lambda d: tamper_metadata(d, lambda m: m.update(status="DECLARED")),
            "corpus changed": lambda d: tamper_metadata(d, lambda m: m["corpus"].update(sha256="0" * 64)),
            "plan disagrees with corpus": lambda d: tamper_metadata(
                d, lambda m: m["plan"].update(provider_called_cases=CALLED[:1])),
            "missing attempt": lambda d: tamper_records(d, lambda r: r.pop()),
            "duplicate attempt": lambda d: tamper_records(d, lambda r: r.append(dict(r[-1]))),
            "unknown case": lambda d: tamper_records(d, lambda r: r[1].update(case_id="nope")),
            "unknown outcome": lambda d: tamper_records(d, lambda r: r[1].update(outcome="WORKED")),
            "NOT_CALLED on a provider case": lambda d: tamper_records(
                d, lambda r: r[1].update(outcome="NOT_CALLED")),
            "record of another run": lambda d: tamper_records(d, lambda r: r[1].update(run_id="other")),
            "record disagrees with output": lambda d: tamper_records(
                d, lambda r: r[1].update(abstained=False)),
            "OK record without output": lambda d: tamper_outputs(d, lambda rows: rows.pop()),
            "output for a failed attempt": lambda d: (
                tamper_records(d, lambda r: r[1].update(
                    outcome="UNAVAILABLE", abstained=None, hypothesis_count=None, citation_count=None,
                    validator=None, error={"type": "T", "detail": "d", "http_status": 429,
                                           "timeout": False}))),
            "missing outputs file": lambda d: (d / "outputs-r2.jsonl").unlink(),
            "blank record line": lambda d: (d / "runs.jsonl").write_text(
                (d / "runs.jsonl").read_text(encoding="utf-8") + "\n", encoding="utf-8"),
            "malformed json": lambda d: (d / "runs.jsonl").write_text("{", encoding="utf-8"),
        }
        for name, damage in cases.items():
            with self.subTest(name):
                directory = Path(tempfile.mkdtemp(dir=self.root))
                run_dir = make_run(directory)
                damage(run_dir)
                with self.assertRaises((ValueError, OSError)):
                    summarize_run.summarize(run_dir, CORPUS)

    def test_cli_exit_codes(self):
        run_dir = make_run(self.root)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(summarize_run.main([str(run_dir)]), 0)
        self.assertEqual(json.loads(out.getvalue())["run"]["run_id"], "run-x")

        (run_dir / "run.json").unlink()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(summarize_run.main([str(run_dir)]), 2)
        self.assertIn("Run summary error", err.getvalue())


if __name__ == "__main__":
    unittest.main()
