"""Offline abstention evaluation over synthetic, normalized evidence only.

This intentionally does not reimplement the production result validator. A
passing abstention check is one narrow quality signal, not a safety or RCA
accuracy certification.
"""

import argparse
import json
import sys
from pathlib import Path


def load_corpus(path: Path) -> dict[str, dict]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("version"), str):
        raise ValueError("Corpus needs a version")
    cases = document.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Corpus needs at least one case")
    indexed = {}
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get("id"), str)
                or not case["id"] or not isinstance(case.get("expected_abstain"), bool)
                or not isinstance(case.get("rationale"), str) or not case["rationale"]
                or not isinstance(case.get("model_input"), dict)
                or not isinstance(case["model_input"].get("gaps"), list)
                or not isinstance(case["model_input"].get("evidence"), list)):
            raise ValueError("Malformed corpus case")
        if case["id"] in indexed:
            raise ValueError(f"Duplicate corpus ID: {case['id']}")
        indexed[case["id"]] = case
    return indexed


def load_outputs(path: Path, case_ids: set[str]) -> dict[str, dict]:
    outputs = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            raise ValueError(f"Empty output line {line_number}")
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) != {"case_id", "output"}:
            raise ValueError(f"Malformed output line {line_number}")
        case_id, output = row["case_id"], row["output"]
        if not isinstance(case_id, str) or case_id not in case_ids:
            raise ValueError(f"Unknown case ID on line {line_number}")
        if case_id in outputs:
            raise ValueError(f"Duplicate output for {case_id}")
        if (not isinstance(output, dict)
                or set(output) != {"summary", "uncertainty", "hypotheses"}
                or not isinstance(output["summary"], str)
                or not isinstance(output["uncertainty"], str)
                or not isinstance(output["hypotheses"], list)):
            raise ValueError(f"Malformed model output for {case_id}")
        outputs[case_id] = output
    missing = case_ids - outputs.keys()
    if missing:
        raise ValueError("Missing outputs: " + ", ".join(sorted(missing)))
    return outputs


def score(cases: dict[str, dict], outputs: dict[str, dict]) -> dict:
    results = []
    for case_id, case in cases.items():
        abstained = len(outputs[case_id]["hypotheses"]) == 0
        results.append({
            "case_id": case_id,
            "expected_abstain": case["expected_abstain"],
            "abstained": abstained,
            "matched": abstained == case["expected_abstain"],
        })
    return {
        "evaluated": len(results),
        "matched": sum(item["matched"] for item in results),
        "results": results,
        "limits": "Abstention only; no citation validation, causal truth, or root-cause accuracy measured.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path(__file__).with_name("corpus.json"))
    parser.add_argument("--outputs", type=Path, help="JSONL file with one model result per corpus case")
    args = parser.parse_args(argv)
    try:
        cases = load_corpus(args.corpus)
        if args.outputs is None:
            print(json.dumps({
                "corpus_cases": len(cases),
                "evaluated": 0,
                "message": "No provider outputs supplied; no model result claimed.",
            }, indent=2))
            return 0
        outputs = load_outputs(args.outputs, set(cases))
        result = score(cases, outputs)
        print(json.dumps(result, indent=2))
        return 0 if result["matched"] == result["evaluated"] else 1
    except (OSError, ValueError) as exc:
        print(f"Evaluation input error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
