import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import review_run
from test_summarize_run import CORPUS, failed, make_run, ok, write_jsonl


ISOLATED, MIXED = "isolated-server-error", "mixed-status-and-trace"
GOOD = {"evidence_support": "SUPPORTED", "contradiction_handling": "ACKNOWLEDGED",
        "causal_calibration": "CALIBRATED"}


def corpus_case(case_id):
    return next(case for case in json.loads(CORPUS.read_text(encoding="utf-8"))["cases"]
                if case["id"] == case_id)


def reviewable_run(root: Path, plan=None) -> Path:
    """The hand-built run, with the mixed case citing real corpus evidence."""
    run_dir = make_run(root, plan)
    real_id = corpus_case(MIXED)["model_input"]["evidence"][1]["evidence_id"]
    for path in run_dir.glob("outputs-r*.jsonl"):
        path.write_text(path.read_text(encoding="utf-8").replace('"e1"', json.dumps(real_id)),
                        encoding="utf-8")
    return run_dir


def review_row(reviewer, repeat, **labels):
    return {"reviewer": reviewer, "case_id": MIXED, "repeat": repeat, "hypothesis_index": 0,
            **GOOD, **labels, "notes": ""}


def adjudication_row(repeat, **labels):
    return {"adjudicator": "adj", "case_id": MIXED, "repeat": repeat, "hypothesis_index": 0,
            **GOOD, **labels, "reason": "Resolved after discussion."}


def write_reviews(run_dir, reviewer, rows):
    (run_dir / "reviews").mkdir(exist_ok=True)
    write_jsonl(run_dir / "reviews" / f"{reviewer}.jsonl", rows)


def all_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from all_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from all_keys(item)


class ReviewRunTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)

    def test_only_validated_non_abstaining_hypotheses_are_reviewable(self):
        plan = {(MIXED, 3): ok(False, accepted=False, reason="Evidence reference is outside this investigation"),
                (ISOLATED, 1): failed("UNAVAILABLE", status=429)}
        summary = review_run.summarize_reviews(reviewable_run(self.root, plan), CORPUS)

        self.assertEqual(summary["denominators"]["reviewable_items"], 2)
        excluded = summary["denominators"]["excluded_attempts"]
        self.assertEqual((excluded["not_called"], excluded["provider_failure"], excluded["abstained"],
                          excluded["production_rejected"]), (1, 1, 2, 1))

    def test_no_reviews_and_one_reviewer_are_not_publishable_and_withhold_counts(self):
        run_dir = reviewable_run(self.root)
        none = review_run.summarize_reviews(run_dir, CORPUS)
        self.assertEqual(none["publication"]["status"], "NOT_PUBLISHABLE")
        self.assertEqual(none["coverage"]["items_with_no_review"], 3)
        self.assertEqual(none["coverage"]["reviewers"], [])
        self.assertIsNone(none["final_label_counts"])

        write_reviews(run_dir, "rev-a", [review_row("rev-a", n) for n in (1, 2, 3)])
        one = review_run.summarize_reviews(run_dir, CORPUS)
        self.assertEqual(one["publication"]["status"], "NOT_PUBLISHABLE")
        self.assertEqual(one["coverage"]["items_with_one_reviewer"], 3)
        self.assertEqual(one["coverage"]["reviewers"], [{"reviewer": "rev-a", "reviewed": 3, "of": 3}])
        self.assertIn("3 of 3 items lack reviews from two different reviewers",
                      one["publication"]["blocking"])
        self.assertIsNone(one["final_label_counts"])

    def test_two_agreeing_reviewers_make_the_result_publishable_with_denominators(self):
        run_dir = reviewable_run(self.root)
        rows = lambda who: [review_row(who, 1), review_row(who, 2, evidence_support="PARTIAL"),
                            review_row(who, 3, causal_calibration="OVERSTATED")]
        write_reviews(run_dir, "rev-a", rows("rev-a"))
        write_reviews(run_dir, "rev-b", rows("rev-b"))

        summary = review_run.summarize_reviews(run_dir, CORPUS)

        self.assertEqual(summary["publication"], {"status": "PUBLISHABLE", "blocking": []})
        self.assertEqual(summary["final_label_counts"]["evidence_support"],
                         {"SUPPORTED": 2, "PARTIAL": 1, "UNSUPPORTED": 0})
        self.assertEqual(summary["final_label_counts"]["causal_calibration"],
                         {"CALIBRATED": 2, "OVERSTATED": 1})
        self.assertEqual(summary["agreement"]["evidence_support"], {"compared_items": 3, "agreed_items": 3})
        self.assertEqual(summary["denominators"]["reviewable_items"], 3)
        self.assertEqual(summary["causal_truth"]["status"], "NOT_ASSESSED")
        self.assertFalse([key for key in all_keys(summary) if "accuracy" in key.lower()])

    def test_disagreement_blocks_publication_until_adjudicated(self):
        run_dir = reviewable_run(self.root)
        write_reviews(run_dir, "rev-a", [review_row("rev-a", n) for n in (1, 2, 3)])
        write_reviews(run_dir, "rev-b", [review_row("rev-b", 1),
                                         review_row("rev-b", 2, contradiction_handling="IGNORED"),
                                         review_row("rev-b", 3)])

        before = review_run.summarize_reviews(run_dir, CORPUS)
        self.assertEqual(before["publication"]["status"], "NOT_PUBLISHABLE")
        self.assertEqual(before["publication"]["blocking"],
                         ["1 item(s) with reviewer disagreement have no adjudication record"])
        self.assertEqual(before["disagreements"], [{
            "case_id": MIXED, "repeat": 2, "hypothesis_index": 0, "dimension": "contradiction_handling",
            "labels": {"rev-a": "ACKNOWLEDGED", "rev-b": "IGNORED"}, "adjudicated_label": None}])
        self.assertEqual(before["agreement"]["contradiction_handling"],
                         {"compared_items": 3, "agreed_items": 2})
        self.assertIsNone(before["final_label_counts"])

        write_jsonl(run_dir / "reviews" / "adjudication.jsonl",
                    [adjudication_row(2, contradiction_handling="IGNORED")])
        after = review_run.summarize_reviews(run_dir, CORPUS)
        self.assertEqual(after["publication"]["status"], "PUBLISHABLE")
        self.assertEqual(after["final_label_counts"]["contradiction_handling"],
                         {"ACKNOWLEDGED": 2, "IGNORED": 1, "NOT_APPLICABLE": 0})
        self.assertEqual(after["disagreements"][0]["adjudicated_label"], "IGNORED")
        self.assertEqual(after["adjudication"], {"records": 1, "unresolved_items": 0})

    def test_a_run_with_nothing_to_review_is_not_applicable(self):
        run_dir = reviewable_run(self.root, {(MIXED, n): ok(True) for n in (1, 2, 3)})
        summary = review_run.summarize_reviews(run_dir, CORPUS)
        self.assertEqual(summary["publication"]["status"], "NOT_APPLICABLE")
        self.assertEqual(summary["denominators"]["reviewable_items"], 0)
        with self.assertRaises(ValueError):
            review_run.write_template(run_dir, "rev-a", CORPUS)

    def test_invalid_review_files_are_rejected(self):
        def reviewer_file(change, name="rev-a"):
            def damage(run_dir):
                rows = [review_row(name, n) for n in (1, 2, 3)]
                change(rows)
                write_reviews(run_dir, name, rows)
            return damage

        def adjudication(rows):
            def damage(run_dir):
                for who in ("rev-a", "rev-b"):
                    write_reviews(run_dir, who, [review_row(who, 1), review_row(who, 2), review_row(who, 3)])
                write_jsonl(run_dir / "reviews" / "adjudication.jsonl", rows)
            return damage

        cases = {
            "label outside the vocabulary": reviewer_file(lambda r: r[0].update(evidence_support="GOOD")),
            "unfilled template label": reviewer_file(lambda r: r[0].update(causal_calibration=None)),
            "unknown item": reviewer_file(lambda r: r[0].update(repeat=9)),
            "duplicate item": reviewer_file(lambda r: r.append(dict(r[0]))),
            "extra key": reviewer_file(lambda r: r[0].update(score=5)),
            "missing key": reviewer_file(lambda r: r[0].pop("notes")),
            "reviewer differs from file name": reviewer_file(lambda r: r[0].update(reviewer="rev-b")),
            "notes too long": reviewer_file(lambda r: r[0].update(notes="x" * 501)),
            "invalid reviewer file name": reviewer_file(lambda r: None, name="Rev A"),
            "boolean repeat": reviewer_file(lambda r: r[0].update(repeat=True)),
            "unexpected file": lambda d: ((d / "reviews").mkdir(), (d / "reviews" / "notes.txt").write_text("x")),
            "blank line": lambda d: ((d / "reviews").mkdir(),
                                     (d / "reviews" / "rev-a.jsonl").write_text("\n", encoding="utf-8")),
            "adjudication without a disagreement": adjudication([adjudication_row(1)]),
            "duplicate adjudication": adjudication([adjudication_row(1), adjudication_row(1)]),
            "adjudication with empty reason": adjudication([{**adjudication_row(1), "reason": " "}]),
            "adjudication for an unknown item": adjudication([{**adjudication_row(1), "repeat": 9}]),
        }
        for name, damage in cases.items():
            with self.subTest(name):
                run_dir = reviewable_run(Path(tempfile.mkdtemp(dir=self.root)))
                damage(run_dir)
                with self.assertRaises((ValueError, OSError)):
                    review_run.summarize_reviews(run_dir, CORPUS)

    def test_packet_gives_context_without_corpus_labels(self):
        packet = review_run.build_packet(reviewable_run(self.root), CORPUS)
        text = json.dumps(packet)

        self.assertEqual(len(packet["items"]), 3)
        self.assertEqual(list(packet["cases"]), [MIXED])
        self.assertEqual(packet["items"][0]["cited_evidence"][0]["evidence_summary"],
                         "request_failed (HTTP 503)")
        self.assertEqual(len(packet["cases"][MIXED]["evidence"]), 5)
        self.assertNotIn("expected_abstain", text)
        self.assertNotIn(corpus_case(MIXED)["rationale"], text)

    def test_template_has_null_labels_is_rejected_until_filled_and_never_overwrites(self):
        run_dir = reviewable_run(self.root)
        path = review_run.write_template(run_dir, "rev-a", CORPUS)
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["evidence_support"] is None and row["notes"] == "" for row in rows))
        with self.assertRaises(ValueError):
            review_run.summarize_reviews(run_dir, CORPUS)
        with self.assertRaises(FileExistsError):
            review_run.write_template(run_dir, "rev-a", CORPUS)
        for bad in ("adjudication", "Rev A", ""):
            with self.assertRaises(ValueError):
                review_run.write_template(run_dir, bad, CORPUS)

    def test_cli_exit_codes(self):
        run_dir = reviewable_run(self.root)

        def call(*argv):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = review_run.main(list(argv))
            return code, out.getvalue(), err.getvalue()

        self.assertEqual(call("packet", str(run_dir))[0], 0)
        code, out, _ = call("summarize", str(run_dir))
        self.assertEqual((code, json.loads(out)["publication"]["status"]), (0, "NOT_PUBLISHABLE"))
        self.assertEqual(call("template", str(run_dir), "--reviewer", "rev-a")[0], 0)
        code, _, err = call("summarize", str(run_dir))  # template labels are still null
        self.assertEqual(code, 2)
        self.assertIn("Review error", err)
        self.assertEqual(call("template", str(run_dir), "--reviewer", "rev-a")[0], 2)


if __name__ == "__main__":
    unittest.main()
