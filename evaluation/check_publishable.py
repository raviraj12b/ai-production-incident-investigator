"""Read-only check of whether a saved provider run may be published.

Standard library only. It never calls a provider and never writes, copies,
rewrites or repairs anything: every file is opened for reading.

    python evaluation/check_publishable.py <run_dir>
    python evaluation/check_publishable.py <run_dir> --scan-env-secret GROQ_API_KEY

It checks the artifact-selection policy in docs/phase-07-2-provider-run.md:
run.json status COMPLETE, a clean repository, the committed corpus hash, saved
files that agree with each other (via summarize_run), only the expected files,
and a secret scan. It also reports how many review items the run yields, taken
from the review packet and cross-checked against runs.jsonl.

Artifact eligibility and human-review readiness are separate. A run may be
publishable while review is still pending and causal quality is NOT_ASSESSED;
this check never treats review status as a publication precondition. The one
exception is a reviews/ directory that holds invalid or unfilled files, which
the policy says are never published.

The secret scan is detection, not proof of absence: it looks for a fixed set of
patterns (and, optionally, the literal value of one named environment variable)
and says nothing about secrets in any other form. Matches are reported by file,
line and pattern name only; matched text is never printed.

Exit codes: 0 = every precondition holds, 1 = at least one precondition failed,
2 = the run directory could not be read at all.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

try:
    import review_run
    import summarize_run
except ImportError:  # imported as evaluation.check_publishable
    from evaluation import review_run, summarize_run


DEFAULT_CORPUS = summarize_run.DEFAULT_CORPUS
MIN_ENV_SECRET_LENGTH = 8
FILE_ATTRIBUTE_REPARSE_POINT = 0x400  # Windows symlinks, junctions and other reparse points
SECRET_PATTERNS = {
    "bearer-text": re.compile(r"bearer", re.IGNORECASE),
    "authorization-text": re.compile(r"authorization", re.IGNORECASE),
    "api-key-name": re.compile(r"api[_-]?key", re.IGNORECASE),
    "reviewer-key-name": re.compile(r"reviewer[_-]?api[_-]?key", re.IGNORECASE),
    "groq-key-shape": re.compile(r"gsk_[A-Za-z0-9]{8,}"),
    "sk-key-shape": re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    "private-key-block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
}
LIMITS = (
    "Secret scan is detection, not proof of absence.",
    "Artifact eligibility says nothing about quality; causal quality is NOT_ASSESSED.",
    "This check is read-only; it cannot confirm that the published copy is byte-identical "
    "to the original. Compare file hashes yourself.",
    "Links and special files are rejected using lstat before any file is opened, and the secret scan "
    "opens files without following links where the platform supports it, but summarize_run and "
    "review_run open files normally. Do not run this on a directory that something else can modify.",
)
ENV_NAME_RE = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")


def _check(name: str, passed: bool, detail: str, action: str | None = None) -> dict:
    return {"check": name, "passed": passed, "detail": detail,
            "action": None if passed else action}


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _expected_files(metadata: dict) -> set[str]:
    repeats = metadata.get("plan", {}).get("repeats")
    count = repeats if isinstance(repeats, int) and 1 <= repeats <= summarize_run.MAX_REPEATS else 0
    return {"run.json", "runs.jsonl", *(f"outputs-r{n}.jsonl" for n in range(1, count + 1))}


class Inventory:
    """What is in a run directory, found without following any link."""

    def __init__(self, root: Path):
        self.root = root
        self.files: list[Path] = []
        self.unsafe: list[tuple[str, str]] = []  # (relative path, kind)

    def relative_files(self) -> set[str]:
        return {path.relative_to(self.root).as_posix() for path in self.files}

    def describe_unsafe(self) -> str:
        return ", ".join(f"{name} ({kind})" for name, kind in sorted(self.unsafe))


def _link_kind(info: os.stat_result) -> str | None:
    if stat.S_ISLNK(info.st_mode):
        return "symlink"
    if getattr(info, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
        return "reparse point"
    return None


def inventory(run_dir: Path) -> Inventory:
    """List regular files using lstat only. Symlinks, Windows reparse points and special
    files (pipes, sockets, devices) are recorded as unsafe and never opened or entered.
    Raises OSError if run_dir cannot be listed."""
    found = Inventory(run_dir)
    top = run_dir.lstat()
    if _link_kind(top):
        found.unsafe.append(("the run directory itself", _link_kind(top)))
        return found
    pending = [run_dir]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            listed = sorted(entries, key=lambda entry: entry.name)
        for entry in listed:
            path = Path(entry.path)
            relative = path.relative_to(run_dir).as_posix()
            info = entry.stat(follow_symlinks=False)
            kind = _link_kind(info)
            if kind:
                found.unsafe.append((relative, kind))
            elif stat.S_ISDIR(info.st_mode):
                pending.append(path)
            elif stat.S_ISREG(info.st_mode):
                found.files.append(path)
            else:
                found.unsafe.append((relative, "special file"))
    found.files.sort()
    return found


def _read_regular_file(path: Path) -> bytes:
    """Read a file that inventory() listed, refusing to follow a link swapped in since."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) \
        | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags), "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise OSError("not a regular file")
        return handle.read()


def check_layout(found: Inventory, metadata: dict) -> dict:
    if found.unsafe:
        return _check("layout", False,
                      f"not plain files or directories, so nothing was followed or read: {found.describe_unsafe()}",
                      "Remove every symlink, junction and special file from the run directory. A "
                      "published run must be ordinary files that the runner wrote. This tool will not "
                      "change them, and no other check was run.")
    expected = _expected_files(metadata)
    present = found.relative_files()
    reviews = {name for name in present if name.startswith("reviews/")}
    unexpected = sorted(present - expected - reviews)
    missing = sorted(expected - present)
    stray_reviews = sorted(name for name in reviews if not name.endswith(".jsonl"))
    problems = ([f"missing: {', '.join(missing)}"] if missing else []) \
        + ([f"unexpected: {', '.join(unexpected + stray_reviews)}"] if unexpected or stray_reviews else [])
    return _check("layout", not problems,
                  "; ".join(problems) or f"{len(expected)} expected files present, nothing else",
                  "Publish only files the runner wrote (and valid reviews/*.jsonl). Do not add or "
                  "hand-edit files in the run directory.")


def check_status(metadata: dict) -> dict:
    status = metadata.get("status")
    return _check("status-complete", status == "COMPLETE" and isinstance(metadata.get("finished_at"), str),
                  f"run.json status is {status!r}",
                  "A run that is not COMPLETE was interrupted. Do not publish it; rerun deliberately.")


def check_clean_repository(metadata: dict) -> dict:
    repo = metadata.get("repo")
    dirty = repo.get("dirty") if isinstance(repo, dict) else None
    detail = {False: "repo.dirty is false", True: "repo.dirty is true"}.get(
        dirty, f"repo.dirty is {dirty!r} (unknown)")
    return _check("repository-clean", dirty is False, detail,
                  "The run was made from a working tree with uncommitted changes (or the state is "
                  "unknown). Do not publish it. If you believe the changes were irrelevant, write "
                  "that explanation yourself and publish by an explicit decision, not through this check.")


def check_run_id(run_dir: Path, metadata: dict) -> dict:
    run_id = metadata.get("run_id")
    return _check("run-id-matches-directory", run_id == run_dir.name,
                  f"run.json run_id {run_id!r}, directory {run_dir.name!r}",
                  "Publish under evaluation/runs/<run_id>/ with the directory named exactly as run_id.")


def check_corpus_hash(metadata: dict, corpus_path: Path) -> dict:
    corpus = metadata.get("corpus")
    recorded = corpus.get("sha256") if isinstance(corpus, dict) else None
    actual = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    return _check("corpus-hash", recorded == actual,
                  f"recorded {recorded}, committed corpus {actual}",
                  "The run used a different corpus than the committed one. Do not publish it; the "
                  "corpus is frozen, so the run is not comparable.")


def check_consistency(run_dir: Path, corpus_path: Path) -> tuple[dict, dict | None]:
    try:
        summary = summarize_run.summarize(run_dir, corpus_path)
    except (OSError, ValueError, KeyError) as exc:
        return _check("artifact-consistency", False, f"summarize_run rejected the run: {exc}",
                      "The saved files disagree with each other or the plan. Report this; do not "
                      "repair the evidence."), None
    return _check("artifact-consistency", True,
                  "summarize_run accepts the run (status, corpus, plan, one record per planned "
                  "attempt, outputs agree with records)"), summary


def _line_findings(name: str, text: str, env_secret: str | None) -> list[tuple[str, int]]:
    findings = []
    for number, line in enumerate(text.splitlines(), start=1):
        for pattern_name, pattern in SECRET_PATTERNS.items():
            if pattern.search(line):
                findings.append((pattern_name, number))
        if env_secret and env_secret in line:
            findings.append(("environment-secret-value", number))
    return findings


def scan_secrets(run_dir: Path, env_secret: str | None = None, found: Inventory | None = None) -> dict:
    """Detection only. Reports file, line and pattern name, never the matched text.
    Links are never followed: a run directory that contains any is not scanned."""
    found = found or inventory(run_dir)
    if found.unsafe:
        return _check("secret-scan", False,
                      f"not scanned, because following links could read files outside the run: {found.describe_unsafe()}",
                      "Remove every symlink, junction and special file, then rerun. This tool will not "
                      "change the run.")
    hits, unreadable = [], []
    for path in found.files:
        relative = path.relative_to(run_dir).as_posix()
        try:
            data = _read_regular_file(path)
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            unreadable.append(relative)
            continue
        except OSError:
            unreadable.append(f"{relative} (changed or unreadable during the scan)")
            continue
        hits += [f"{relative}:{number} ({name})" for name, number in _line_findings(relative, text, env_secret)]
    scope = "documented patterns" + (" plus the value of one environment variable" if env_secret else "")
    problems = ([f"matches: {', '.join(hits)}"] if hits else []) \
        + ([f"not valid UTF-8 or not readable, so not scanned: {', '.join(unreadable)}"] if unreadable else [])
    return _check("secret-scan", not problems,
                  "; ".join(problems) or f"no matches for the {scope} in {len(found.files)} files "
                  "(detection only, not proof that no secret is present)",
                  "Inspect each reported line yourself. Do not publish until every match is explained "
                  "or the run is regenerated. This tool will not edit the files.")


def review_items(run_dir: Path, corpus_path: Path) -> dict:
    """Count reviewable items from the generated packet and cross-check against runs.jsonl."""
    packet_items = review_run.build_packet(run_dir, corpus_path)["items"]
    _, exclusions, metadata, _ = review_run.collect_items(run_dir, corpus_path)
    records = summarize_run._read_records(run_dir / "runs.jsonl")
    expected = sum(row["hypothesis_count"] for row in records
                   if row["outcome"] == "OK" and row["validator"]["accepted"] and row["hypothesis_count"] > 0)
    keys = [(item["case_id"], item["repeat"], item["hypothesis_index"]) for item in packet_items]
    return {"packet_items": len(packet_items), "expected_from_records": expected,
            "distinct_item_keys": len(set(keys)),
            "items": [{"case_id": c, "repeat": r, "hypothesis_index": h} for c, r, h in keys],
            "excluded_attempts": exclusions}


def check_review_items(counts: dict) -> dict:
    agrees = counts["packet_items"] == counts["expected_from_records"] == counts["distinct_item_keys"]
    return _check("review-item-count", agrees,
                  f"packet has {counts['packet_items']} items; runs.jsonl implies "
                  f"{counts['expected_from_records']}; {counts['distinct_item_keys']} distinct keys",
                  "The review packet and the run records disagree about what is reviewable. Report this; "
                  "do not adjust either.")


def check_reviews_directory(run_dir: Path, corpus_path: Path) -> tuple[dict, dict]:
    """Invalid or unfilled review files must not be published. Review readiness is reported apart."""
    pending = {"status": "PENDING", "detail": "No reviews/ directory; no human review has been recorded.",
               "causal_quality": "NOT_ASSESSED"}
    if not (run_dir / "reviews").is_dir():
        return _check("reviews-directory", True, "no reviews/ directory"), pending
    try:
        summary = review_run.summarize_reviews(run_dir, corpus_path)
    except (OSError, ValueError, KeyError) as exc:
        return (_check("reviews-directory", False, f"reviews/ is invalid or unfilled: {exc}",
                       "Unfilled templates and invalid review files are never published. Remove them "
                       "from the copy being published, or finish the reviews."),
                {"status": "INVALID", "detail": str(exc), "causal_quality": "NOT_ASSESSED"})
    status = summary["publication"]["status"]
    return (_check("reviews-directory", True, f"reviews/ validates; review publication status {status}"),
            {"status": status, "detail": "Reported by review_run summarize; not a publication precondition.",
             "causal_quality": "NOT_ASSESSED"})


def check_run(run_dir: Path, corpus_path: Path = DEFAULT_CORPUS, env_secret_name: str | None = None) -> dict:
    """Evaluate every precondition. Raises OSError/ValueError only if the directory or run.json
    cannot be read at all. The directory is inventoried with lstat before any file is opened;
    if it holds a link or special file, only the layout check is reported and nothing is read."""
    found = inventory(run_dir)
    if found.unsafe:
        return {
            "run_id": None,
            "publishable_artifact": False,
            "checks": [check_layout(found, {})],
            "review_items": None,
            "human_review": {"status": "NOT_EVALUATED", "detail": "run directory contains links or special files",
                             "causal_quality": "NOT_ASSESSED"},
            "notes": ["Every other check was skipped: following a link could read files outside the "
                      "run directory, so the run was not opened."],
            "limits": list(LIMITS),
        }
    metadata = _read_json(run_dir / "run.json")
    if not isinstance(metadata, dict):
        raise ValueError("run.json is not an object")
    env_secret = None
    if env_secret_name:
        value = os.environ.get(env_secret_name, "")
        env_secret = value if len(value) >= MIN_ENV_SECRET_LENGTH else None
    consistency, summary = check_consistency(run_dir, corpus_path)
    checks = [check_layout(found, metadata), check_status(metadata), check_clean_repository(metadata),
              check_run_id(run_dir, metadata), check_corpus_hash(metadata, corpus_path), consistency,
              scan_secrets(run_dir, env_secret, found)]
    counts = None
    if summary is not None:
        counts = review_items(run_dir, corpus_path)
        checks.append(check_review_items(counts))
    reviews_check, review_state = check_reviews_directory(run_dir, corpus_path) if summary is not None \
        else (_check("reviews-directory", False, "not evaluated: the run is inconsistent", "Fix the run first."),
              {"status": "NOT_EVALUATED", "detail": "run is inconsistent", "causal_quality": "NOT_ASSESSED"})
    checks.append(reviews_check)
    note = None
    if env_secret_name and env_secret is None:
        note = f"{env_secret_name} is unset or shorter than {MIN_ENV_SECRET_LENGTH} characters, so its value was not scanned for."
    return {
        "run_id": metadata.get("run_id"),
        "publishable_artifact": all(item["passed"] for item in checks),
        "checks": checks,
        "review_items": counts,
        "human_review": review_state,
        "notes": [note] if note else [],
        "limits": list(LIMITS),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run_dir", type=Path, help="Run directory to check (read-only)")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--scan-env-secret", metavar="NAME", default=None,
                        help="Also look for the literal value of this environment variable "
                             "(for example GROQ_API_KEY). The value is never printed.")
    args = parser.parse_args(argv)
    if args.scan_env_secret and not ENV_NAME_RE.fullmatch(args.scan_env_secret):
        print("Check error: --scan-env-secret needs an environment variable name", file=sys.stderr)
        return 2
    try:
        result = check_run(args.run_dir, args.corpus, args.scan_env_secret)
    except (OSError, ValueError) as exc:
        print(f"Check error: cannot read the run: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2))
    failed = [item for item in result["checks"] if not item["passed"]]
    for item in failed:
        print(f"FAILED {item['check']}: {item['detail']}\n  -> {item['action']}", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
