import contextlib
import io
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import check_publishable
import review_run
from test_review_run import GOOD, ISOLATED, MIXED, reviewable_run, review_row, write_reviews
from test_summarize_run import CORPUS, failed, ok, read_records, write_records

RUNS_DIR = Path(__file__).with_name("runs")
SECRET_LINES = {
    "bearer-text": "Authorization header sent with Bearer token",
    "groq-key-shape": "key gsk_AbCdEfGh1234567890 leaked",
    "private-key-block": "-----BEGIN RSA PRIVATE KEY-----",
}


def passed(result, name):
    return next(item for item in result["checks"] if item["check"] == name)["passed"]


def failures(result):
    return {item["check"] for item in result["checks"] if not item["passed"]}


def snapshot(run_dir: Path) -> dict:
    """Everything observable about a directory: names, bytes and modification times."""
    return {path.relative_to(run_dir).as_posix(): (path.read_bytes(), path.stat().st_mtime_ns)
            for path in sorted(run_dir.rglob("*")) if path.is_file()} | {
        "<listing>": (sorted(p.relative_to(run_dir).as_posix() for p in run_dir.rglob("*")), 0)}


def edit_run_json(run_dir: Path, **changes):
    path = run_dir / "run.json"
    metadata = json.loads(path.read_text(encoding="utf-8"))
    for key, value in changes.items():
        metadata[key] = value
    path.write_text(json.dumps(metadata), encoding="utf-8")


class CheckPublishableTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)

    def check(self, run_dir, **kwargs):
        return check_publishable.check_run(run_dir, CORPUS, **kwargs)

    def test_clean_run_passes_every_check_and_reports_review_as_pending(self):
        result = self.check(reviewable_run(self.root))

        self.assertTrue(result["publishable_artifact"])
        self.assertEqual(failures(result), set())
        self.assertEqual(result["human_review"]["status"], "PENDING")
        self.assertEqual(result["human_review"]["causal_quality"], "NOT_ASSESSED")
        self.assertTrue(any("not proof" in line for line in result["limits"]))

    def test_checking_never_changes_a_passing_or_failing_run(self):
        good = reviewable_run(self.root)
        before = snapshot(good)
        self.check(good)
        self.assertEqual(snapshot(good), before)

        bad_root = self.root / "bad"
        bad_root.mkdir()
        bad = reviewable_run(bad_root)
        edit_run_json(bad, status="RUNNING")
        (bad / "stray.txt").write_text("Bearer abc", encoding="utf-8")
        before = snapshot(bad)
        self.assertFalse(self.check(bad)["publishable_artifact"])
        self.assertEqual(snapshot(bad), before)
        self.assertEqual([p.name for p in bad.rglob("__pycache__")], [])

    def test_each_precondition_failure_is_reported_by_name(self):
        cases = {
            "status-complete": lambda d: edit_run_json(d, status="RUNNING"),
            "repository-clean": lambda d: edit_run_json(d, repo={"commit": "c", "dirty": True}),
            "corpus-hash": lambda d: edit_run_json(d, corpus={"file": "corpus.json", "version": "07.1.0",
                                                              "sha256": "0" * 64}),
            "layout": lambda d: (d / "notes.txt").write_text("extra", encoding="utf-8"),
        }
        for name, break_run in cases.items():
            with self.subTest(name):
                root = self.root / name
                root.mkdir()
                run_dir = reviewable_run(root)
                break_run(run_dir)
                result = self.check(run_dir)
                self.assertFalse(result["publishable_artifact"])
                self.assertIn(name, failures(result))
                item = next(item for item in result["checks"] if item["check"] == name)
                self.assertTrue(item["action"])

    def test_unknown_dirty_state_is_not_treated_as_clean(self):
        run_dir = reviewable_run(self.root)
        edit_run_json(run_dir, repo={"commit": "c", "dirty": None})
        self.assertIn("repository-clean", failures(self.check(run_dir)))

    def test_run_directory_must_be_named_by_run_id(self):
        run_dir = reviewable_run(self.root)
        renamed = run_dir.rename(self.root / "something-else")
        self.assertIn("run-id-matches-directory", failures(self.check(renamed)))

    def test_missing_output_file_and_inconsistent_records_are_rejected_without_repair(self):
        run_dir = reviewable_run(self.root)
        (run_dir / "outputs-r2.jsonl").unlink()
        result = self.check(run_dir)
        self.assertTrue({"layout", "artifact-consistency"} <= failures(result))
        self.assertFalse((run_dir / "outputs-r2.jsonl").exists())
        self.assertNotIn("review-item-count", {item["check"] for item in result["checks"]})

    def test_planted_secrets_are_detected_by_file_line_and_pattern_without_echoing_them(self):
        for pattern_name, line in SECRET_LINES.items():
            with self.subTest(pattern_name):
                root = self.root / pattern_name
                root.mkdir()
                run_dir = reviewable_run(root)
                path = run_dir / "outputs-r1.jsonl"
                path.write_text(path.read_text(encoding="utf-8").replace("A dependency may be failing.", line),
                                encoding="utf-8")
                result = self.check(run_dir)
                scan = next(item for item in result["checks"] if item["check"] == "secret-scan")

                self.assertFalse(scan["passed"])
                self.assertIn("outputs-r1.jsonl:", scan["detail"])
                self.assertIn(f"({pattern_name})", scan["detail"])
                self.assertNotIn("gsk_AbCdEfGh1234567890", json.dumps(result))
                self.assertNotIn("BEGIN RSA", json.dumps(result))

    def test_environment_secret_value_is_detected_but_never_printed_and_short_values_are_ignored(self):
        secret = "s3cr3t-value-abcdef"
        run_dir = reviewable_run(self.root)
        path = run_dir / "outputs-r1.jsonl"
        path.write_text(path.read_text(encoding="utf-8").replace("A dependency may be failing.", secret),
                        encoding="utf-8")

        with mock.patch.dict(os.environ, {"EVAL_TEST_SECRET": secret}):
            found = self.check(run_dir, env_secret_name="EVAL_TEST_SECRET")
        self.assertIn("secret-scan", failures(found))
        self.assertIn("environment-secret-value", json.dumps(found))
        self.assertNotIn(secret, json.dumps(found))

        with mock.patch.dict(os.environ, {"EVAL_TEST_SECRET": "short"}):
            ignored = self.check(run_dir, env_secret_name="EVAL_TEST_SECRET")
        self.assertNotIn("secret-scan", failures(ignored))
        self.assertTrue(ignored["notes"])

        without = self.check(run_dir)
        self.assertNotIn("secret-scan", failures(without))

    def test_non_utf8_file_is_reported_as_unscannable(self):
        run_dir = reviewable_run(self.root)
        (run_dir / "outputs-r1.jsonl").write_bytes(b"\xff\xfe\x00")
        scan = next(item for item in self.check(run_dir)["checks"] if item["check"] == "secret-scan")
        self.assertFalse(scan["passed"])
        self.assertIn("not valid UTF-8", scan["detail"])

    def test_review_item_count_comes_from_the_packet_and_excludes_rejected_and_not_called(self):
        plan = {(MIXED, 3): ok(False, accepted=False, reason="Evidence reference is outside this investigation"),
                (ISOLATED, 1): failed("UNAVAILABLE", status=429)}
        run_dir = reviewable_run(self.root, plan)
        result = self.check(run_dir)
        counts = result["review_items"]
        self.assertTrue(passed(result, "review-item-count"))

        packet = review_run.build_packet(run_dir, CORPUS)["items"]
        records = read_records(run_dir)
        independent = [(row["case_id"], row["repeat"]) for row in records
                       if row["outcome"] == "OK" and row["validator"]["accepted"] and row["hypothesis_count"]]
        self.assertEqual(counts["packet_items"], len(packet))
        self.assertEqual(counts["packet_items"], len(independent))
        self.assertEqual(counts["expected_from_records"], len(independent))
        self.assertEqual([(i["case_id"], i["repeat"]) for i in counts["items"]], independent)
        listed = {(item["case_id"], item["repeat"]) for item in counts["items"]}
        self.assertNotIn(("no-observations", 1), listed)  # NOT_CALLED
        self.assertNotIn((MIXED, 3), listed)               # production-rejected
        self.assertNotIn((ISOLATED, 1), listed)            # provider failure
        self.assertEqual(counts["excluded_attempts"]["not_called"], 1)
        self.assertEqual(counts["excluded_attempts"]["production_rejected"], 1)
        self.assertEqual(counts["excluded_attempts"]["provider_failure"], 1)

    def test_count_follows_the_run_rather_than_a_fixed_number(self):
        for name in ("a", "b"):
            (self.root / name).mkdir()
        plan = {(MIXED, 1): ok(False, accepted=False, reason="r"), (MIXED, 2): ok(True)}
        sizes = {self.check(reviewable_run(self.root / "a"))["review_items"]["packet_items"],
                 self.check(reviewable_run(self.root / "b", plan))["review_items"]["packet_items"]}
        self.assertEqual(sizes, {3, 1})

    def test_packet_and_record_counts_that_disagree_fail_the_check(self):
        agree = {"packet_items": 3, "expected_from_records": 3, "distinct_item_keys": 3}
        self.assertTrue(check_publishable.check_review_items(agree)["passed"])
        for broken in ({"expected_from_records": 2}, {"distinct_item_keys": 2}):
            result = check_publishable.check_review_items({**agree, **broken})
            self.assertFalse(result["passed"])
            self.assertTrue(result["action"])

    def test_pending_review_does_not_block_publication_and_review_readiness_stays_separate(self):
        run_dir = reviewable_run(self.root)
        review_run.write_template(run_dir, "reviewer_a", CORPUS)
        unfilled = self.check(run_dir)
        self.assertFalse(unfilled["publishable_artifact"])
        self.assertEqual(failures(unfilled), {"reviews-directory"})
        self.assertEqual(unfilled["human_review"]["status"], "INVALID")

        (run_dir / "reviews" / "reviewer_a.jsonl").unlink()
        write_reviews(run_dir, "reviewer_a", [review_row("reviewer_a", n) for n in (1, 2, 3)])
        one_reviewer = self.check(run_dir)
        self.assertTrue(one_reviewer["publishable_artifact"])
        self.assertEqual(one_reviewer["human_review"]["status"], "NOT_PUBLISHABLE")
        self.assertEqual(one_reviewer["human_review"]["causal_quality"], "NOT_ASSESSED")

    def test_cli_exit_codes_and_actionable_messages(self):
        good = reviewable_run(self.root)
        with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(check_publishable.main([str(good), "--corpus", str(CORPUS)]), 0)
        self.assertTrue(json.loads(out.getvalue())["publishable_artifact"])

        (self.root / "bad").mkdir()
        bad = reviewable_run(self.root / "bad")
        edit_run_json(bad, repo={"commit": "c", "dirty": True})
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            self.assertEqual(check_publishable.main([str(bad), "--corpus", str(CORPUS)]), 1)
        self.assertIn("FAILED repository-clean", err.getvalue())
        self.assertIn("->", err.getvalue())

        for argv in ([str(self.root / "missing")], [str(good), "--scan-env-secret", "not a name"]):
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(check_publishable.main(argv + ["--corpus", str(CORPUS)]), 2)

    def test_every_published_run_passes_except_for_an_explained_dirty_state(self):
        for run_dir in sorted(RUNS_DIR.glob("*/")) if RUNS_DIR.is_dir() else []:
            with self.subTest(run_dir.name):
                result = check_publishable.check_run(run_dir, CORPUS)
                self.assertLessEqual(failures(result), {"repository-clean"})


def _can_symlink() -> bool:
    with tempfile.TemporaryDirectory() as directory:
        try:
            os.symlink(Path(directory) / "target", Path(directory) / "link")
        except (OSError, NotImplementedError):
            return False
    return True


def tree_state(root: Path) -> dict:
    """Everything under root without following links: bytes, modes, mtimes and link targets."""
    state = {}
    for current, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(current) / name
            info = path.lstat()
            key = path.relative_to(root).as_posix()
            if stat.S_ISLNK(info.st_mode):
                state[key] = ("link", os.readlink(path))
            elif stat.S_ISREG(info.st_mode):
                state[key] = ("file", path.read_bytes(), info.st_mtime_ns, stat.S_IMODE(info.st_mode))
            else:
                state[key] = ("other", stat.S_IFMT(info.st_mode))
    return state


@unittest.skipUnless(_can_symlink(), "symlinks cannot be created in this environment")
class SymlinkRejectionTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.addCleanup(self._directory.cleanup)
        self.root = Path(self._directory.name)
        self.outside = self.root / "outside"
        self.outside.mkdir()
        (self.root / "inside").mkdir()
        self.run_dir = reviewable_run(self.root / "inside")

    def link(self, name: str, target: Path, directory: bool = False) -> Path:
        path = self.run_dir / name
        os.symlink(target, path, target_is_directory=directory)
        return path

    def move_out(self, name: str) -> Path:
        """Replace an artifact with a symlink to an identical file outside the run directory."""
        target = self.outside / name
        target.write_bytes((self.run_dir / name).read_bytes())
        (self.run_dir / name).unlink()
        return self.link(name, target)

    def assert_rejected_untouched(self, run_dir: Path, *expected_in_detail: str) -> dict:
        before = tree_state(self.root)
        result = check_publishable.check_run(run_dir, CORPUS)
        self.assertEqual(tree_state(self.root), before)
        self.assertFalse(result["publishable_artifact"])
        self.assertEqual(failures(result), {"layout"})
        self.assertEqual([item["check"] for item in result["checks"]], ["layout"])
        self.assertTrue(result["notes"])
        detail = result["checks"][0]["detail"]
        for text in expected_in_detail:
            self.assertIn(text, detail)
        return result

    def test_symlinked_expected_artifacts_cannot_pass_even_when_the_target_is_identical(self):
        for name in ("run.json", "runs.jsonl", "outputs-r1.jsonl"):
            with self.subTest(name):
                (self.root / name).mkdir(exist_ok=True)
                run_dir = reviewable_run(self.root / name)
                before_ok = check_publishable.check_run(run_dir, CORPUS)
                self.assertTrue(before_ok["publishable_artifact"])
                target = self.outside / f"{name}.copy"
                target.write_bytes((run_dir / name).read_bytes())
                (run_dir / name).unlink()
                os.symlink(target, run_dir / name)
                self.assert_rejected_untouched(run_dir, name, "symlink")

    def test_symlinked_extra_file_is_rejected_and_its_target_is_never_read(self):
        leak = self.outside / "leak.txt"
        leak.write_text("Authorization: Bearer abc123", encoding="utf-8")
        self.link("extra.txt", leak)
        result = self.assert_rejected_untouched(self.run_dir, "extra.txt", "symlink")
        self.assertNotIn("abc123", json.dumps(result))
        self.assertNotIn("secret-scan", {item["check"] for item in result["checks"]})

    def test_symlink_to_a_file_inside_the_run_directory_is_still_rejected(self):
        self.link("alias.jsonl", Path("runs.jsonl"))
        self.assert_rejected_untouched(self.run_dir, "alias.jsonl", "symlink")

    def test_symlinked_directories_are_rejected_and_not_followed(self):
        hidden = self.outside / "hidden"
        hidden.mkdir()
        (hidden / "note.txt").write_text("gsk_AbCdEfGh1234567890", encoding="utf-8")
        self.link("extra", hidden, directory=True)
        self.link("reviews", hidden, directory=True)
        result = self.assert_rejected_untouched(self.run_dir, "extra", "reviews", "symlink")
        self.assertNotIn("note.txt", json.dumps(result))
        self.assertNotIn("gsk_AbCdEfGh1234567890", json.dumps(result))

    def test_dangling_symlink_is_rejected(self):
        self.link("missing.txt", self.outside / "does-not-exist")
        self.assert_rejected_untouched(self.run_dir, "missing.txt", "symlink")

    def test_the_run_directory_itself_may_not_be_a_symlink(self):
        alias = self.root / "alias-run"
        os.symlink(self.run_dir, alias, target_is_directory=True)
        before = tree_state(self.root)
        result = check_publishable.check_run(alias, CORPUS)
        self.assertEqual(tree_state(self.root), before)
        self.assertFalse(result["publishable_artifact"])
        self.assertEqual(failures(result), {"layout"})
        self.assertIn("run directory", result["checks"][0]["detail"])
        self.assertIn("symlink", result["checks"][0]["detail"])

    def test_secret_scan_refuses_to_follow_links_when_called_directly(self):
        leak = self.outside / "leak.txt"
        leak.write_text("Bearer abc123", encoding="utf-8")
        self.link("extra.txt", leak)
        result = check_publishable.scan_secrets(self.run_dir)
        self.assertFalse(result["passed"])
        self.assertIn("extra.txt", result["detail"])
        self.assertNotIn("abc123", result["detail"])
        self.assertNotIn("(bearer-text)", result["detail"])

    @unittest.skipUnless(hasattr(os, "mkfifo"), "named pipes are not available here")
    def test_special_files_are_rejected_without_being_opened(self):
        os.mkfifo(self.run_dir / "pipe")
        self.assert_rejected_untouched(self.run_dir, "pipe", "special file")

    def test_cli_exits_1_with_an_actionable_message_for_a_symlink(self):
        self.move_out("runs.jsonl")
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = check_publishable.main([str(self.run_dir), "--corpus", str(CORPUS)])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(out.getvalue())["publishable_artifact"])
        self.assertIn("FAILED layout", err.getvalue())
        self.assertIn("symlink", err.getvalue())
        self.assertIn("->", err.getvalue())

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "O_NOFOLLOW is not available on this platform")
    def test_safe_reader_refuses_a_link_swapped_in_after_the_inventory(self):
        target = self.outside / "secret.txt"
        target.write_text("Bearer abc123", encoding="utf-8")
        link = self.link("late.txt", target)
        with self.assertRaises(OSError):
            check_publishable._read_regular_file(link)
        self.assertEqual(check_publishable._read_regular_file(self.run_dir / "runs.jsonl"),
                         (self.run_dir / "runs.jsonl").read_bytes())

    def test_a_clean_run_next_to_the_links_still_passes(self):
        self.assertTrue(check_publishable.check_run(self.run_dir, CORPUS)["publishable_artifact"])


if __name__ == "__main__":
    unittest.main()
