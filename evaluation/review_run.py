"""Human review tooling for a saved provider run (rubric: docs/phase-07-2-review-rubric.md).

Standard library only; reads saved files and never calls a provider.

    python evaluation/review_run.py packet    <run_dir>
    python evaluation/review_run.py template  <run_dir> --reviewer <id>
    python evaluation/review_run.py summarize <run_dir>

Review files live in <run_dir>/reviews/: one <reviewer>.jsonl per reviewer and
an optional adjudication.jsonl. The summary validates them and states whether a
causal-quality result is publishable; it never computes accuracy and withholds
label counts until two reviewers cover every item and every disagreement is
adjudicated.

Exit codes: 0 = output produced, 2 = malformed, incomplete or inconsistent input.
"""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import summarize_run
except ImportError:  # imported as evaluation.review_run
    from evaluation import summarize_run


LABELS = {
    "evidence_support": ("SUPPORTED", "PARTIAL", "UNSUPPORTED"),
    "contradiction_handling": ("ACKNOWLEDGED", "IGNORED", "NOT_APPLICABLE"),
    "causal_calibration": ("CALIBRATED", "OVERSTATED"),
}
ITEM_KEYS = ("case_id", "repeat", "hypothesis_index")
REVIEW_KEYS = {"reviewer", *ITEM_KEYS, *LABELS, "notes"}
ADJUDICATION_KEYS = {"adjudicator", *ITEM_KEYS, *LABELS, "reason"}
REVIEWER_RE = re.compile(r"[a-z0-9][a-z0-9_-]{0,31}\Z")
TEXT_MAX = 500
RESERVED = "adjudication"
DEFAULT_CORPUS = summarize_run.DEFAULT_CORPUS
_require = summarize_run._require
_is_int = summarize_run._is_int


def collect_items(run_dir: Path, corpus_path: Path = DEFAULT_CORPUS) -> tuple[list[dict], dict, dict, dict]:
    """Return (items, exclusions, metadata, cases) for a validated run."""
    metadata, cases, records, outputs = summarize_run.load_run(run_dir, corpus_path)
    plan = metadata["plan"]
    attempts = {(row["case_id"], row["repeat"]): row for row in records}
    items = []
    exclusions = {"not_called": len(plan["not_called_cases"]), "provider_failure": 0,
                  "abstained": 0, "production_rejected": 0}
    for repeat in range(1, plan["repeats"] + 1):
        for case_id in plan["provider_called_cases"]:
            record = attempts[(case_id, repeat)]
            if record["outcome"] != "OK":
                exclusions["provider_failure"] += 1
                continue
            output = outputs[repeat][case_id]
            if not output["hypotheses"]:
                exclusions["abstained"] += 1
                continue
            if not record["validator"]["accepted"]:
                exclusions["production_rejected"] += 1
                continue
            known = {row["evidence_id"] for row in cases[case_id]["model_input"]["evidence"]}
            for index, hypothesis in enumerate(output["hypotheses"]):
                _require(isinstance(hypothesis.get("explanation"), str)
                         and isinstance(hypothesis.get("confidence"), str)
                         and all(isinstance(link, dict) and link.get("evidence_id") in known
                                 for link in hypothesis["links"]),
                         f"Cannot review {case_id} repeat {repeat}: malformed or unknown citation")
                items.append({"case_id": case_id, "repeat": repeat, "hypothesis_index": index,
                              "output": output, "hypothesis": hypothesis})
    return items, exclusions, metadata, cases


def item_key(row: dict) -> tuple:
    return (row["case_id"], row["repeat"], row["hypothesis_index"])


def _key_of(row: dict, valid: set[tuple], where: str) -> tuple:
    _require(isinstance(row["case_id"], str) and _is_int(row["repeat"])
             and _is_int(row["hypothesis_index"]), f"Malformed item key in {where}")
    key = item_key(row)
    _require(key in valid, f"Unknown review item in {where}")
    return key


def _check_labels(row: dict, where: str) -> None:
    for dimension, allowed in LABELS.items():
        _require(isinstance(row[dimension], str) and row[dimension] in allowed,
                 f"Invalid {dimension} label in {where}")


def _check_text(row: dict, field: str, where: str, required: bool) -> None:
    value = row[field]
    _require(isinstance(value, str) and len(value) <= TEXT_MAX and (value.strip() or not required),
             f"Invalid {field} in {where}")


def _rows(path: Path, keys: set[str]) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        where = f"{path.name} line {line_number}"
        _require(bool(line.strip()), f"Empty line in {where}")
        row = json.loads(line)
        _require(isinstance(row, dict) and set(row) == keys, f"Malformed record in {where}")
        rows.append((where, row))
    return rows


def load_reviews(run_dir: Path, valid: set[tuple]) -> tuple[dict, dict]:
    """Validate <run_dir>/reviews and return (reviews[reviewer][key], adjudications[key])."""
    reviews, adjudications = {}, {}
    directory = run_dir / "reviews"
    if not directory.exists():
        return reviews, adjudications
    _require(directory.is_dir(), "reviews must be a directory")
    for path in sorted(directory.iterdir()):
        _require(path.is_file() and path.suffix == ".jsonl", f"Unexpected entry in reviews/: {path.name}")
        if path.stem == RESERVED:
            for where, row in _rows(path, ADJUDICATION_KEYS):
                _require(isinstance(row["adjudicator"], str) and REVIEWER_RE.fullmatch(row["adjudicator"]),
                         f"Invalid adjudicator in {where}")
                key = _key_of(row, valid, where)
                _require(key not in adjudications, f"Duplicate adjudication in {where}")
                _check_labels(row, where)
                _check_text(row, "reason", where, required=True)
                adjudications[key] = row
            continue
        _require(REVIEWER_RE.fullmatch(path.stem), f"Invalid reviewer file name: {path.name}")
        mine = {}
        for where, row in _rows(path, REVIEW_KEYS):
            _require(row["reviewer"] == path.stem, f"Reviewer does not match file name in {where}")
            key = _key_of(row, valid, where)
            _require(key not in mine, f"Duplicate review in {where}")
            _check_labels(row, where)
            _check_text(row, "notes", where, required=False)
            mine[key] = row
        reviews[path.stem] = mine
    return reviews, adjudications


def summarize_reviews(run_dir: Path, corpus_path: Path = DEFAULT_CORPUS) -> dict:
    items, exclusions, metadata, _ = collect_items(run_dir, corpus_path)
    keys = [item_key(item) for item in items]
    reviews, adjudications = load_reviews(run_dir, set(keys))

    agreement = {dimension: {"compared_items": 0, "agreed_items": 0} for dimension in LABELS}
    disagreements, agreed_labels = [], {}
    coverage = {"two_or_more": 0, "one": 0, "none": 0}
    disagreeing_items = set()
    for key in keys:
        labels = {reviewer: rows[key] for reviewer, rows in sorted(reviews.items()) if key in rows}
        coverage["two_or_more" if len(labels) >= 2 else "one" if labels else "none"] += 1
        if len(labels) < 2:
            continue
        for dimension in LABELS:
            values = {reviewer: row[dimension] for reviewer, row in labels.items()}
            agreement[dimension]["compared_items"] += 1
            if len(set(values.values())) == 1:
                agreement[dimension]["agreed_items"] += 1
                agreed_labels[(key, dimension)] = next(iter(values.values()))
            else:
                disagreeing_items.add(key)
                disagreements.append({
                    "case_id": key[0], "repeat": key[1], "hypothesis_index": key[2],
                    "dimension": dimension, "labels": values,
                    "adjudicated_label": adjudications[key][dimension] if key in adjudications else None})
    for key in adjudications:
        _require(key in disagreeing_items,
                 f"Adjudication for an item without a reviewer disagreement: {key[0]} repeat {key[1]}")
    unresolved = len(disagreeing_items - set(adjudications))

    blocking = []
    if not keys:
        status = "NOT_APPLICABLE"
    else:
        if coverage["one"] + coverage["none"]:
            blocking.append(f"{coverage['one'] + coverage['none']} of {len(keys)} items lack reviews "
                            "from two different reviewers")
        if unresolved:
            blocking.append(f"{unresolved} item(s) with reviewer disagreement have no adjudication record")
        status = "NOT_PUBLISHABLE" if blocking else "PUBLISHABLE"

    final_counts = None
    if status == "PUBLISHABLE":
        final_counts = {dimension: {label: 0 for label in allowed} for dimension, allowed in LABELS.items()}
        for key in keys:
            for dimension in LABELS:
                label = adjudications[key][dimension] if key in adjudications else agreed_labels[(key, dimension)]
                final_counts[dimension][label] += 1
    return {
        "run": {"run_id": metadata["run_id"], "corpus_version": metadata["corpus"]["version"]},
        "denominators": {
            "reviewable_items": len(keys),
            "excluded_attempts": {**exclusions,
                                  "note": "Counted per attempt; reviewable items are counted per hypothesis."},
        },
        "coverage": {
            "reviewers": [{"reviewer": reviewer, "reviewed": len(rows), "of": len(keys)}
                          for reviewer, rows in sorted(reviews.items())],
            "items_with_two_or_more_reviewers": coverage["two_or_more"],
            "items_with_one_reviewer": coverage["one"], "items_with_no_review": coverage["none"],
        },
        "agreement": agreement,
        "disagreements": disagreements,
        "adjudication": {"records": len(adjudications), "unresolved_items": unresolved},
        "publication": {"status": status, "blocking": blocking},
        "final_label_counts": final_counts,
        "causal_truth": {
            "status": "NOT_ASSESSED",
            "reason": "The labels measure support, contradiction handling and calibration. The 07.1 "
                      "corpus has no case with an identifiable cause."},
        "limits": ["Reviewer independence is a procedure and is not verified by this tool.",
                   "Review items are per hypothesis; repeats of a case are separate items."],
    }


def build_packet(run_dir: Path, corpus_path: Path = DEFAULT_CORPUS) -> dict:
    """Reviewer-facing context. Never includes corpus labels or other reviewers' labels."""
    items, exclusions, metadata, cases = collect_items(run_dir, corpus_path)
    case_ids = list(dict.fromkeys(item["case_id"] for item in items))
    summaries = {case_id: {row["evidence_id"]: row["summary"]
                           for row in cases[case_id]["model_input"]["evidence"]} for case_id in case_ids}
    return {
        "run_id": metadata["run_id"], "rubric": "docs/phase-07-2-review-rubric.md",
        "cases": {case_id: {"evidence": cases[case_id]["model_input"]["evidence"],
                            "gaps": cases[case_id]["model_input"]["gaps"]} for case_id in case_ids},
        "items": [{
            "case_id": item["case_id"], "repeat": item["repeat"],
            "hypothesis_index": item["hypothesis_index"],
            "summary": item["output"]["summary"], "uncertainty": item["output"]["uncertainty"],
            "explanation": item["hypothesis"]["explanation"], "confidence": item["hypothesis"]["confidence"],
            "cited_evidence": [{"evidence_id": link["evidence_id"], "relation": link.get("relation"),
                                "evidence_summary": summaries[item["case_id"]][link["evidence_id"]]}
                               for link in item["hypothesis"]["links"]],
        } for item in items],
    }


def write_template(run_dir: Path, reviewer: str, corpus_path: Path = DEFAULT_CORPUS) -> Path:
    _require(REVIEWER_RE.fullmatch(reviewer) and reviewer != RESERVED, "Invalid reviewer ID")
    items, *_ = collect_items(run_dir, corpus_path)
    _require(bool(items), "Nothing to review in this run")
    directory = run_dir / "reviews"
    directory.mkdir(exist_ok=True)
    path = directory / f"{reviewer}.jsonl"
    with path.open("x", encoding="utf-8") as handle:  # FileExistsError rather than overwrite
        for item in items:
            handle.write(json.dumps({
                "reviewer": reviewer, "case_id": item["case_id"], "repeat": item["repeat"],
                "hypothesis_index": item["hypothesis_index"],
                **{dimension: None for dimension in LABELS}, "notes": ""}) + "\n")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("packet", "template", "summarize"):
        command = commands.add_parser(name)
        command.add_argument("run_dir", type=Path)
        command.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
        if name == "template":
            command.add_argument("--reviewer", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "packet":
            print(json.dumps(build_packet(args.run_dir, args.corpus), indent=2))
        elif args.command == "summarize":
            print(json.dumps(summarize_reviews(args.run_dir, args.corpus), indent=2))
        else:
            print(f"Wrote {write_template(args.run_dir, args.reviewer, args.corpus)}")
        return 0
    except (OSError, ValueError) as exc:
        print(f"Review error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
