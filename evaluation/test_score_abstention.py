"""Tests for complete-case accounting and distinguishing abstention failures."""

import json
import tempfile
import unittest
from pathlib import Path

from score_abstention import load_corpus, load_outputs, score


CORPUS = Path(__file__).with_name("corpus.json")


class AbstentionScorerTests(unittest.TestCase):
    def setUp(self):
        self.cases = load_corpus(CORPUS)

    def write_outputs(self, rows):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        path = Path(temporary.name) / "outputs.jsonl"
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        return path

    def outputs(self):
        return [
            {"case_id": case_id, "output": {
                "summary": "Root cause undetermined from available evidence.",
                "uncertainty": "Evidence is insufficient.", "hypotheses": [],
            }}
            for case_id in self.cases
        ]

    def test_complete_abstaining_run_is_counted_without_causal_claim(self):
        outputs = load_outputs(self.write_outputs(self.outputs()), set(self.cases))
        result = score(self.cases, outputs)
        self.assertEqual((result["evaluated"], result["matched"]), (3, 3))
        self.assertNotIn("accuracy", result)

    def test_unsupported_cause_is_reported_as_a_failed_abstention(self):
        rows = self.outputs()
        rows[-1]["output"]["hypotheses"] = [{"explanation": "It was a deployment."}]
        result = score(self.cases, load_outputs(self.write_outputs(rows), set(self.cases)))
        self.assertEqual((result["evaluated"], result["matched"]), (3, 2))
        self.assertFalse(result["results"][-1]["matched"])

    def test_missing_duplicate_and_unknown_cases_are_rejected(self):
        rows = self.outputs()
        for invalid in (rows[:-1], rows + [rows[0]], rows[:-1] + [
            {**rows[-1], "case_id": "unknown-case"},
        ]):
            with self.subTest(invalid=invalid[-1]["case_id"]):
                with self.assertRaises(ValueError):
                    load_outputs(self.write_outputs(invalid), set(self.cases))

    def test_malformed_result_cannot_be_counted_as_abstention(self):
        rows = self.outputs()
        del rows[0]["output"]["hypotheses"]
        with self.assertRaises(ValueError):
            load_outputs(self.write_outputs(rows), set(self.cases))


if __name__ == "__main__":
    unittest.main()
