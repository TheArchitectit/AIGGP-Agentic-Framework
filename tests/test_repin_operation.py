# // spec: img-cycle-04, coh-id-04
"""The re-pin operation, tested by running it (img-cycle-04, design D7).

Design D7's claim is narrow and testable: moving the pinned identity is ONE
command that edits four literals and then re-runs the chain guard. The failure
modes it names are the ones this repository already suffered by hand:

* a digest recorded from a value no registry serves (the S4 identity was
  recorded unpullable this way), so the operation resolves the digest from the
  registry API — never from `podman image inspect`, which reports a
  local-storage value on both axes;
* a `DEVGATE_PIN` that predates the record, which lands every consumer's gate
  at SKIPPED rather than at a red — so the operation writes the pin as the
  FIRST of its two commits, the commit whose tree carries the moved record,
  and refuses to finish if that agreement does not hold;
* a partial move, which the guard catches.

Every test here runs the real script against a real (temporary) git repository
with stubbed `curl` and `podman` on PATH. A text assertion cannot tell a guard
from one mutated to `if false;`, so these execute.

The repository-building half of that harness lives in `tests/fixtures/repin.py`
(it is a fixture, and this file is at the size gate's ceiling). Its helpers are
imported here under the short private spellings the call sites below were
written with, so the extraction did not become a 60-site rename.

Dual-runnable: pytest collects test_*; `python3 <this file>` runs them too.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixtures.repin import (IMAGE, LOCAL, SERVED, SCRIPT,  # noqa: E402
                                 TEMPLATE_BODY, fixture as _fixture,
                                 git as _git, rec as _rec, record as _record,
                                 run as _run, stub_bin as _stub_bin,
                                 tmpl as _tmpl)


class TestRePinOperation(unittest.TestCase):

    def test_a_successful_re_pin_leaves_every_literal_in_agreement(self):
        """The four literals move together, and the pin names the record's tree.

        This is the only state that is not broken: a digest without the pin
        ships a record the pinned tree does not carry, and a pin without the
        digest lands every consumer at SKIPPED.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest="sha256:" + "c" * 64)
            binp = _stub_bin(tmp)
            r = _run(repo, binp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

            rec, env = _rec(repo), _tmpl(repo)
            prof = rec["profiles"][0]
            self.assertEqual(prof["image_manifest_digest"], SERVED)
            self.assertEqual(prof["built"], "2026-09-24")
            self.assertEqual(rec["image"], IMAGE)
            self.assertEqual(env["COHERENCE_IMAGE"], rec["image"])
            self.assertEqual(env["COHERENCE_IMAGE_MANIFEST_DIGEST"],
                             prof["image_manifest_digest"])

            pin = env["DEVGATE_PIN"]
            self.assertRegex(pin, r"^[0-9a-f]{40}$")
            shown = _git(repo, "show", f"{pin}:container/execution-profiles.json")
            self.assertEqual(shown.returncode, 0,
                             "the pin must name a commit carrying the record")
            self.assertEqual(json.loads(shown.stdout)["profiles"][0]
                             ["image_manifest_digest"], SERVED)

            head = _git(repo, "rev-parse", "HEAD").stdout.strip()
            self.assertNotEqual(pin, head,
                                "the pin is the record commit; HEAD carries the "
                                "template edit — pinning HEAD would be the very "
                                "ordering mistake this tests against")

    def test_the_operation_takes_its_digest_from_the_registry(self):
        """Not from `podman image inspect`, which answers on a local axis.

        The podman stub here reports a digest no registry serves. A green run
        that records THAT value is the historical defect — the S4 identity was
        recorded unpullable exactly this way (run 36050827753).
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp)
            binp = _stub_bin(tmp)
            r = _run(repo, binp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(_rec(repo)["profiles"][0]["image_manifest_digest"], SERVED)
            raw = (repo / "container" / "execution-profiles.json").read_text(encoding="utf-8")
            self.assertNotIn(LOCAL, raw,
                             "the local-storage digest reached the record")

    def test_the_operation_refuses_bytes_a_consumer_cannot_fetch(self):
        """The anonymous pull is the check — and it must happen before recording.

        Recording first and discovering unfetchability in CI is how the pin
        spent a day naming bytes nobody could pull.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest="sha256:" + "c" * 64)
            binp = _stub_bin(tmp)
            r = _run(repo, binp, STUB_PULL_RC="1")
            self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
            self.assertEqual(_rec(repo)["profiles"][0]["image_manifest_digest"],
                             "sha256:" + "c" * 64, "a refused identity was recorded anyway")
            self.assertEqual(_git(repo, "rev-list", "--count", "HEAD").stdout.strip(), "2",
                             "a refused identity was committed anyway")

    def test_a_registry_that_serves_no_digest_fails_closed(self):
        """No header, no identity — and nothing written."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest="sha256:" + "c" * 64)
            binp = _stub_bin(tmp, served="")
            r = _run(repo, binp)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertEqual(_rec(repo)["profiles"][0]["image_manifest_digest"],
                             "sha256:" + "c" * 64)

    def test_the_operation_refuses_a_dirty_tree(self):
        """It writes commits; it will not write them over someone's work."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest="sha256:" + "c" * 64)
            binp = _stub_bin(tmp)
            (repo / "wip.txt").write_text("uncommitted\n", encoding="utf-8")
            r = _run(repo, binp)
            self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
            self.assertEqual(_rec(repo)["profiles"][0]["image_manifest_digest"],
                             "sha256:" + "c" * 64)

    def test_a_partial_re_pin_fails_the_guard(self):
        """Digest moved, pin left behind — the state a hand re-pin produces."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, c1 = _fixture(tmp, digest="sha256:" + "c" * 64)
            binp = _stub_bin(tmp)
            # Move the template's digest literal only, as an incomplete hand
            # re-pin does, and leave DEVGATE_PIN pointing at the old tree.
            t = repo / "templates" / "github-workflows" / "spec-coherence.yml"
            t.write_text(re.sub(r"(COHERENCE_IMAGE_MANIFEST_DIGEST: )\S+",
                                rf"\g<1>{SERVED}", t.read_text(encoding="utf-8")), encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "digest only")
            r = _run(repo, binp, REPIN_CHECK_ONLY="1")
            self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
            self.assertIn("DEVGATE_PIN", r.stdout + r.stderr)

    def test_a_pin_predating_the_record_fails_the_guard(self):
        """A pin whose tree has no record at all — the round-18 state.

        Distinct from a partial re-pin: there the pinned tree carries an older
        record, here it carries none, because the pin names a commit from
        before the identity registry existed.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo = tmp / "repo"
            (repo / "templates" / "github-workflows").mkdir(parents=True)
            (repo / "templates" / "github-workflows" / "spec-coherence.yml").write_text(
                TEMPLATE_BODY.format(pin="0" * 40, image=IMAGE,
                                     profile="linux-amd64-v1", digest=SERVED), encoding="utf-8")
            _git(repo, "init", "-q", "-b", "main")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "template before the record existed")
            c1 = _git(repo, "rev-parse", "HEAD").stdout.strip()
            (repo / "container").mkdir()
            (repo / "container" / "execution-profiles.json").write_text(_record(SERVED), encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "add the record")
            t = repo / "templates" / "github-workflows" / "spec-coherence.yml"
            t.write_text(re.sub(r"DEVGATE_PIN: \S+", f"DEVGATE_PIN: {c1}", t.read_text(encoding="utf-8")), encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "pin at the pre-record commit")

            r = _run(repo, _stub_bin(tmp), REPIN_CHECK_ONLY="1")
            self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
            out = r.stdout + r.stderr
            self.assertIn("DEVGATE_PIN", out)
            # The diagnostic, not just the refusal: a guard catches this, and
            # the guard's job is to say which file is missing from the pin's
            # tree. Without this assertion the check can be dropped and the
            # failure still arrives — from a comparison further down, worded
            # as a digest mismatch, which does not tell anyone what to do.
            self.assertIn("does not carry", out)

    def test_the_guard_refuses_a_pin_absent_from_this_clone(self):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest=SERVED, pin="d" * 40)
            binp = _stub_bin(tmp)
            r = _run(repo, binp, REPIN_CHECK_ONLY="1")
            self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
            self.assertIn("DEVGATE_PIN", r.stdout + r.stderr)

    def test_the_guard_refuses_a_pinned_tree_without_the_templates_profile(self):
        """The pin's tree must resolve the profile the template names.

        Not the same as a digest mismatch: the profile is absent from the
        pinned tree entirely, so there is nothing to compare against, and the
        message has to say that rather than print two digests.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest=SERVED, profile="linux-arm64-v1")
            binp = _stub_bin(tmp)
            # The pin stays at the arm64-only commit; the template and the
            # working record move to amd64.
            (repo / "container" / "execution-profiles.json").write_text(
                _record(SERVED, profile="linux-amd64-v1"), encoding="utf-8")
            t = repo / "templates" / "github-workflows" / "spec-coherence.yml"
            t.write_text(re.sub(r"COHERENCE_PROFILE: \S+",
                                "COHERENCE_PROFILE: linux-amd64-v1", t.read_text(encoding="utf-8")), encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "move to the amd64 profile")

            r = _run(repo, binp, REPIN_CHECK_ONLY="1")
            self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
            self.assertIn("no profile", r.stdout + r.stderr)

    def test_the_guard_refuses_a_working_record_that_disagrees(self):
        """The fourth pair: the checked-out record, which the gate reads.

        The template and the pin's tree can agree with each other while the
        record in the working tree says something else — a repository
        disagreeing with itself, and the state a hand edit of one file leaves.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest=SERVED)
            binp = _stub_bin(tmp)
            (repo / "container" / "execution-profiles.json").write_text(
                _record("sha256:" + "e" * 64), encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "drift the record")

            r = _run(repo, binp, REPIN_CHECK_ONLY="1")
            self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
            self.assertIn("commit the record or re-pin", r.stdout + r.stderr)

    def test_the_guard_refuses_a_template_naming_a_different_image(self):
        """Agreement is over the image too, not just the digest.

        A record moved to a new path with the digest left alone would agree on
        the digest and name different bytes — the rename's own failure mode.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest=SERVED)
            binp = _stub_bin(tmp)
            t = repo / "templates" / "github-workflows" / "spec-coherence.yml"
            t.write_text(re.sub(r"(COHERENCE_IMAGE: )\S+",
                                r"\g<1>ghcr.io/someone-else/devgate-coherence",
                                t.read_text(encoding="utf-8")), encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "image only")
            r = _run(repo, binp, REPIN_CHECK_ONLY="1")
            self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
            self.assertIn("DEVGATE_PIN", r.stdout + r.stderr)

    def test_a_malformed_template_fails_before_anything_is_committed(self):
        """The record is not committed on the way to discovering a bad template.

        Discovered after commit 1, a missing literal would leave a half-moved
        repository behind — the partial state this operation exists to make
        impossible.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest="sha256:" + "c" * 64)
            binp = _stub_bin(tmp)
            t = repo / "templates" / "github-workflows" / "spec-coherence.yml"
            t.write_text(re.sub(r"^\s*COHERENCE_IMAGE_MANIFEST_DIGEST:.*\n", "",
                                t.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "drop a literal")
            before = _git(repo, "rev-parse", "HEAD").stdout.strip()

            r = _run(repo, binp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertEqual(_git(repo, "rev-parse", "HEAD").stdout.strip(), before,
                             "a commit was written for a template that cannot be moved")
            self.assertEqual(_rec(repo)["profiles"][0]["image_manifest_digest"],
                             "sha256:" + "c" * 64)

    def test_a_re_pin_on_a_detached_head_is_refused_before_anything_is_written(self):
        """Commits on a detached HEAD belong to no branch, so no consumer can
        fetch the pin. Refused up front rather than discovered at the guard."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest="sha256:" + "c" * 64)
            binp = _stub_bin(tmp)
            before = _git(repo, "rev-parse", "HEAD").stdout.strip()
            _git(repo, "checkout", "-q", "--detach", "HEAD")

            r = _run(repo, binp)
            self.assertEqual(r.returncode, 5, r.stdout + r.stderr)
            self.assertEqual(_git(repo, "rev-parse", "HEAD").stdout.strip(), before)
            self.assertEqual(_rec(repo)["profiles"][0]["image_manifest_digest"],
                             "sha256:" + "c" * 64, "a commit was written on a detached HEAD")

    def test_an_unreachable_pin_fails_the_guard(self):
        """Existence is not reachability — the property a consumer depends on.

        A commit on a branch nobody fetches is readable here (`git show` works)
        and resolves to nothing for every consumer: their gate lands at
        SKIPPED. Only an ancestor-of-HEAD check catches it.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest=SERVED)
            binp = _stub_bin(tmp)
            _git(repo, "checkout", "-q", "-b", "side")
            (repo / "side.txt").write_text("x\n", encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "side work")
            side = _git(repo, "rev-parse", "HEAD").stdout.strip()
            _git(repo, "checkout", "-q", "main")
            t = repo / "templates" / "github-workflows" / "spec-coherence.yml"
            t.write_text(re.sub(r"DEVGATE_PIN: \S+", f"DEVGATE_PIN: {side}", t.read_text(encoding="utf-8")), encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "pin at unreachable commit")

            r = _run(repo, binp, REPIN_CHECK_ONLY="1")
            self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
            self.assertIn("ancestor", r.stdout + r.stderr)

    def test_a_re_run_against_an_already_current_identity_is_idempotent(self):
        """Nothing to move is a success, not a crash.

        The record and the template already name the served digest: the record
        edit produces no diff, so there is no commit to make. Failing here
        would make the operation unusable the second time it is run — and it
        would fail after printing that it was about to move the pin.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest=SERVED, built="2026-09-24")
            binp = _stub_bin(tmp)
            before = _git(repo, "rev-parse", "HEAD").stdout.strip()
            pin_before = _tmpl(repo)["DEVGATE_PIN"]

            r = _run(repo, binp)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(_git(repo, "rev-parse", "HEAD").stdout.strip(), before,
                             "a commit was written for a no-op re-pin")
            self.assertEqual(_tmpl(repo)["DEVGATE_PIN"], pin_before)

    def test_the_operation_refuses_a_profile_the_record_does_not_carry(self):
        """COHERENCE_PROFILE is not a knob — it decides which digest is pinned.

        Moving a profile the record does not have would write bytes the
        template never references, leaving the pinned identity untouched. It
        is refused before any commit, not discovered by the guard after.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest="sha256:" + "c" * 64)
            binp = _stub_bin(tmp)
            t = repo / "templates" / "github-workflows" / "spec-coherence.yml"
            t.write_text(re.sub(r"COHERENCE_PROFILE: \S+",
                                "COHERENCE_PROFILE: linux-arm64-v1", t.read_text(encoding="utf-8")), encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "profile the record lacks")
            before = _git(repo, "rev-parse", "HEAD").stdout.strip()

            r = _run(repo, binp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertEqual(_git(repo, "rev-parse", "HEAD").stdout.strip(), before)
            self.assertEqual(_rec(repo)["profiles"][0]["image_manifest_digest"],
                             "sha256:" + "c" * 64)

    def test_the_post_write_guard_catches_a_template_rewritten_after_the_write(self):
        """The guard runs on the way out, not just under REPIN_CHECK_ONLY.

        Something between the write and the guard — here a hook that rewrites
        the file, which is what a formatting or lint hook does — leaves the
        literals disagreeing. The operation must fail and restore the tree
        rather than report a re-pin it did not achieve.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest="sha256:" + "c" * 64)
            binp = _stub_bin(tmp)
            before = _git(repo, "rev-parse", "HEAD").stdout.strip()
            hooks = repo / ".git" / "hooks"
            hooks.mkdir(exist_ok=True)
            hook = hooks / "pre-commit"
            hook.write_text(
                "#!/usr/bin/env bash\n"
                "sed -i 's/^      DEVGATE_PIN: .*/      DEVGATE_PIN: "
                + "e" * 40 + "/' templates/github-workflows/spec-coherence.yml\n", encoding="utf-8")
            hook.chmod(0o755)

            r = _run(repo, binp)
            self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
            self.assertEqual(_git(repo, "rev-parse", "HEAD").stdout.strip(), before,
                             "the tree was not restored after the guard failed")

    def test_a_failed_commit_restores_the_tree_and_exits_six(self):
        """A re-pin is all-or-nothing, and the message must not outrun it.

        The operation edits the record, commits it, edits the template, commits
        that — and a `git commit` can fail for reasons the operation does not
        control (a hook, an index lock, a missing identity). Failing in the
        middle leaves the record moved and the template not, which is exactly
        the partial state the guard exists to refuse; the operation must undo
        its own first commit rather than hand that state to whoever runs it
        next. Exit 6 is that promise, and the diagnostic states it in words —
        both are asserted here, because a rollback removed while the message
        survives is a message that lies.

        The commit failure is induced with a failing hook rather than a missing
        identity: an identity is now supplied by the environment, and a test
        depending on its ABSENCE would be the same ambient-config coupling in
        reverse — green only where git has no user configured.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, head = _fixture(tmp, digest="sha256:" + "c" * 64)
            binp = _stub_bin(tmp)
            hooks = repo / ".git" / "hooks"
            hooks.mkdir(exist_ok=True)
            hook = hooks / "pre-commit"
            hook.write_text("#!/usr/bin/env bash\nexit 1\n", encoding="utf-8")
            hook.chmod(0o755)

            r = _run(repo, binp)
            self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
            self.assertIn("nothing was left applied", r.stderr)
            self.assertEqual(_git(repo, "rev-parse", "HEAD").stdout.strip(), head,
                             "a commit that failed was left standing")
            self.assertEqual(_git(repo, "status", "--porcelain").stdout.strip(), "",
                             "the tree was left dirty after a failed commit")
            self.assertNotEqual(
                _rec(repo)["profiles"][0]["image_manifest_digest"], SERVED,
                "the record kept the moved digest despite the rollback")

    def test_a_duplicated_literal_is_refused_before_anything_is_committed(self):
        """A second COHERENCE_IMAGE line is a template that cannot be moved.

        Reading the first occurrence would move that one and leave the other
        naming the old image — and the second is the one a reader might be
        looking at. The pre-flight counts before the record commit, so the
        refusal arrives with nothing written.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest="sha256:" + "c" * 64)
            binp = _stub_bin(tmp)
            t = repo / "templates" / "github-workflows" / "spec-coherence.yml"
            t.write_text(t.read_text(encoding="utf-8") + f"      COHERENCE_IMAGE: {IMAGE}\n", encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "duplicate a literal")
            before = _git(repo, "rev-parse", "HEAD").stdout.strip()

            r = _run(repo, binp)
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertEqual(_git(repo, "rev-parse", "HEAD").stdout.strip(), before,
                             "a commit was written for a template that cannot be moved")

    def test_quoted_literals_are_read_as_their_values(self):
        """`COHERENCE_IMAGE: "path"` is the same value as the bare form.

        Comparing the raw token would refuse a correct tree, and print two
        strings the reader cannot tell apart while doing it.
        """
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest=SERVED)
            binp = _stub_bin(tmp)
            t = repo / "templates" / "github-workflows" / "spec-coherence.yml"
            text = t.read_text(encoding="utf-8")
            text = re.sub(r"(COHERENCE_IMAGE: )(\S+)", r'\1"\2"', text)
            text = re.sub(r"(COHERENCE_IMAGE_MANIFEST_DIGEST: )(\S+)", r'\1"\2"', text)
            t.write_text(text, encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "quote the literals")

            r = _run(repo, binp, REPIN_CHECK_ONLY="1")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_correct_state_passes_the_guard(self):
        """The guard's positive control: it is not refusing everything."""
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            repo, _ = _fixture(tmp, digest=SERVED)
            binp = _stub_bin(tmp)
            r = _run(repo, binp, REPIN_CHECK_ONLY="1")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
