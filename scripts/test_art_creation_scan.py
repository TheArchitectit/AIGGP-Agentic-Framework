#!/usr/bin/env python3
"""Fixture suite for art_creation_scan.py - the negatives that pin each rule.

Every case runs through the real `run_checks` against a real temp tree
(AGENTS.md: build fixtures by calling the real function; a case that only
exercises a stub proves nothing about the scanner). Each case carries the
EXACT requirement set it must trip - not just "there was a finding". A
fixture that regressed to trip a second requirement, or the wrong one, fails
here; asserting only pass/fail is how a negative silently stops pinning the
requirement it was written for.

Run either way:
    python3 scripts/art_creation_scan.py --selftest
    python3 scripts/test_art_creation_scan.py
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from art_creation_scan import DIGEST_STAGES, main, report, run_checks  # noqa: E402

BRIEF_TEXT = (
    "# Art brief\n## Readability brief\n## Art direction pillars\n"
    "## Palette and value structure\n## Shape language\n## Footprint grid\n"
    "## Material families\n## Camera\n"
)

BASE = {
    "brief": "brief.md", "brief_version": "3",
    "shape_rules": {"furniture": "orthogonal"},
    "stages": [{"name": "packed", "consumer": "src/loader.zig",
                "input": "raw mesh", "output": "packed mesh",
                "determinism": "seeded-rng"}],
    "ledger": "ledger.json",
    "targets": ["native"],
    "captures": {"native": {"renderer": "title-own",
                            "contains_game_geometry": True,
                            "frame_sha256": "sha256:aa"}},
    "replication": {"present": True, "restore_exercised_at": "2026-01-01T00:00:00Z"},
    "artifact_dirs": [],
    "published_counts": {},
}

# A stage that satisfies all four declarations required by art-stage-01, for
# cases that need to change only one of them.
STAGE = {"name": "packed", "consumer": "src/loader.zig",
         "input": "raw mesh", "output": "packed mesh",
         "determinism": "seeded-rng"}

GOOD_ROW = {
    "id": "bed", "class": "furniture", "stage": "packed", "brief_ref": "art-brief@3",
    "prompt": "p", "seed": 1,
    "digests": {s: "sha256:x" for s in DIGEST_STAGES},
    "prep_stages": {"normal_repair": True},
    "fidelity": {"verdict": "accept", "rule": "orthogonal"},
    "measurement": {"name": "retained", "value": 1.0, "threshold": None},
    "rights": "unknown",
}

# (name, mutate(cfg, rows) -> (cfg, rows), want_exit, want_reqs[, want_checks])
# The optional 5th item pins what the exit code and the requirement-ID set
# cannot see: `findings` is the exact number of findings, and `msgs` are
# substrings that must appear across their messages. A deleted branch can leave
# the ID set unchanged when another branch still trips the same id, so the
# quantity and stage rules assert their own words as well.
CASES = [
    ("pass", lambda c, r: (c, r), 0, set()),
    ("no-capture", lambda c, r: (dict(c, captures={}), r), 1, {"art-draw-01"}),
    ("dcc-preview", lambda c, r: (
        dict(c, captures={"native": {"renderer": "dcc-preview",
                                     "contains_game_geometry": True,
                                     "frame_sha256": "s"}}), r), 1, {"art-draw-01"}),
    ("renderer-absent", lambda c, r: (
        dict(c, captures={"native": {"contains_game_geometry": True,
                                     "frame_sha256": "s"}}), r), 1, {"art-draw-01"}),
    ("renderer-blender-preview", lambda c, r: (
        dict(c, captures={"native": {"renderer": "blender-preview",
                                     "contains_game_geometry": True,
                                     "frame_sha256": "s"}}), r), 1, {"art-draw-01"}),
    ("clears-buffer-only", lambda c, r: (
        dict(c, captures={"native": {"renderer": "title-own",
                                     "contains_game_geometry": False,
                                     "frame_sha256": "s"}}), r), 1, {"art-draw-01"}),
    ("blank-rights", lambda c, r: (c, [dict(r[0], rights="")]), 1, {"art-rights-01"}),
    ("verdict-no-rule", lambda c, r: (
        c, [dict(r[0], fidelity={"verdict": "accept"})]), 1, {"art-accept-01"}),
    ("wrong-rule-for-class", lambda c, r: (
        c, [dict(r[0], fidelity={"verdict": "accept", "rule": "organic"})]),
        1, {"art-accept-01"}),
    ("meas-no-threshold", lambda c, r: (
        c, [dict(r[0], measurement={"name": "m", "value": 1.0})]), 1, {"art-accept-02"}),
    ("stage-empty", lambda c, r: (c, [dict(r[0], stage="")]),
        1, {"art-ledger-01", "art-done-01"}),
    ("stage-no-consumer", lambda c, r: (
        dict(c, stages=[dict(STAGE, consumer="none")]), r), 1, {"art-stage-01"}),
    ("consumer-path-missing", lambda c, r: (
        dict(c, stages=[dict(STAGE, consumer="src/nowhere.zig")]), r),
        1, {"art-stage-01"}),
    # art-stage-01 requires input, output, reader and determinism. Each missing
    # declaration is its own negative; the pass case and the stage-* positives
    # carry all four, so a rule that rejects everything fails here too.
    ("stage-no-input", lambda c, r: (
        dict(c, stages=[dict(STAGE, input="")]), r), 1, {"art-stage-01"},
        {"msgs": ["does not state: input"]}),
    ("stage-no-output", lambda c, r: (
        dict(c, stages=[dict(STAGE, output=None)]), r), 1, {"art-stage-01"},
        {"msgs": ["does not state: output"]}),
    ("stage-no-determinism", lambda c, r: (
        dict(c, stages=[dict(STAGE, determinism=" ")]), r), 1, {"art-stage-01"},
        {"msgs": ["does not state: determinism"]}),
    ("stage-complete", lambda c, r: (c, r), 0, set(), {"findings": 0}),
    ("no-replication", lambda c, r: (
        dict(c, replication={"present": False}), r), 1, {"art-bytes-01"}),
    ("restore-never-run", lambda c, r: (
        dict(c, replication={"present": True}), r), 1, {"art-bytes-01"}),
    ("unversioned-brief", lambda c, r: (
        dict(c, brief_version=None), r), 1, {"art-brief-01"}),
    # Whitespace is not a version and whitespace is not a reference. The two
    # blanks compared equal, so the scan passed with no version anywhere.
    ("brief-version-whitespace", lambda c, r: (
        dict(c, brief_version="   "), [dict(r[0], brief_ref="   ")]),
        1, {"art-brief-01"},
        {"findings": 1, "msgs": ["brief is unversioned"]}),
    ("brief-version-substring", lambda c, r: (
        dict(c, brief_version="3"), [dict(r[0], brief_ref="art-brief@13")]),
        1, {"art-brief-01"}),
    # A missing or blank rule now fails the acceptance compare too: an accept
    # verdict can never be checked against nothing. Covering the class rule in
    # the brief is not enough for art-accept-01 to go green.
    ("no-shape-rule", lambda c, r: (
        dict(c, shape_rules={}), r), 1, {"art-brief-02", "art-accept-01"},
        {"findings": 2,
         "msgs": ["no geometric rule declared", "is not the declared rule"]}),
    ("count-disagrees", lambda c, r: (
        dict(c, published_counts={"library": 99}), r), 1, {"art-ledger-01"}),
    ("count-unknown-label", lambda c, r: (
        dict(c, published_counts={"pieces": 4}), r), 1, {"art-ledger-01"}),
    # bool is a subclass of int and True == 1; 1.0 == 1 is also true. Both
    # look like the derived count and neither was ever derived as an integer.
    # These two are the false-pass the published-count check exists to close.
    # Each asserts the type-guard message, so deleting the guard fails here
    # even though the value would still disagree with the derived count.
    ("count-bool", lambda c, r: (
        dict(c, published_counts={"library": True}), r), 1, {"art-ledger-01"},
        {"msgs": ["is not an integer"]}),
    ("count-float", lambda c, r: (
        dict(c, published_counts={"library": 1.0}), r), 1, {"art-ledger-01"},
        {"msgs": ["is not an integer"]}),
    ("count-string", lambda c, r: (
        dict(c, published_counts={"library": "1"}), r), 1, {"art-ledger-01"},
        {"msgs": ["is not an integer"]}),
    # artifact_dirs is empty in BASE, so the artifact scan is inert until a case
    # points it at a real directory. Both halves are pinned on purpose: a case
    # that only asserts the stray fails would still pass if the rule were
    # inverted to flag every artifact, so the tracked one must also be green.
    ("artifact-tracked", lambda c, r: (
        dict(c, artifact_dirs=["artifacts"]), r), 0, set()),
    ("artifact-outside-ledger", lambda c, r: (
        dict(c, artifact_dirs=["artifacts"]), [dict(r[0], id="chair")]),
        1, {"art-ledger-01"}),
    # art-qty-01 is two independent failures, so it needs two independent
    # negatives. Each branch is asserted by finding count and message text:
    # deleting the shortfall branch leaves `floor-shortfall-only` green, and
    # deleting the fidelity branch leaves `floor-fidelity-only` green. The
    # "both" case pins that the two quantities are not collapsed into one line.
    ("floor-shortfall-only", lambda c, r: (
        c, [dict(r[0], library_floor=5)]), 1, {"art-qty-01"},
        {"findings": 1,
         "msgs": ["floor=5", "counted=1", "shortfall=4"]}),
    ("floor-fidelity-only", lambda c, r: (
        c, [dict(r[0], library_floor=1),
            dict(r[0], id="chair",
                 fidelity={"verdict": "reject", "rule": "orthogonal"})]),
        1, {"art-qty-01"},
        {"findings": 1, "msgs": ["floor=1", "counted=2", "fidelity-fail=1"]}),
    ("floor-shortfall-and-fidelity", lambda c, r: (
        c, [dict(r[0], library_floor=5),
            dict(r[0], id="chair",
                 fidelity={"verdict": "reject", "rule": "orthogonal"})]),
        1, {"art-qty-01"},
        {"findings": 2, "msgs": ["shortfall=3", "fidelity-fail=1"]}),
    ("floor-met-all-accept", lambda c, r: (
        c, [dict(r[0], library_floor=1)]), 0, set(), {"findings": 0}),
    # A floor that is not a real integer is its own finding. True is an int
    # subclass in Python; a string is not an integer either.
    ("floor-bool", lambda c, r: (
        c, [dict(r[0], library_floor=True)]), 1, {"art-qty-01"},
        {"findings": 1, "msgs": ["is not an integer"]}),
    ("floor-string", lambda c, r: (
        c, [dict(r[0], library_floor="5")]), 1, {"art-qty-01"},
        {"findings": 1, "msgs": ["is not an integer"]}),
    ("accepted-not-terminal", lambda c, r: (
        dict(c, stages=[dict(STAGE, name="prepared"),
                        dict(STAGE, name="packed")]),
        [dict(r[0], stage="prepared")]), 1, {"art-done-01"}),
    # --- second audit round: falsy short-circuits and shape errors ---------
    # Blank-after-strip, presence-only fields, {} / null falsiness, non-dicts.
    ("blank-rights-ws", lambda c, r: (c, [dict(r[0], rights="   ")]),
        1, {"art-rights-01"}, {"msgs": ["rights is blank"]}),
    # A blank class is a ledger finding and also cannot be accepted against a
    # class rule, so art-accept-01 fails closed beside it.
    ("blank-class", lambda c, r: (c, [dict(r[0], **{"class": ""})]),
        1, {"art-ledger-01", "art-accept-01"},
        {"msgs": ["class is blank"]}),
    ("class-whitespace", lambda c, r: (c, [dict(r[0], **{"class": "  "})]),
        1, {"art-ledger-01", "art-accept-01"},
        {"msgs": ["class is blank"]}),
    ("blank-prompt", lambda c, r: (c, [dict(r[0], prompt="")]),
        1, {"art-ledger-01"}, {"msgs": ["prompt is blank"]}),
    ("null-seed", lambda c, r: (c, [dict(r[0], seed=None)]),
        1, {"art-ledger-01"}, {"msgs": ["seed is not an integer"]}),
    ("seed-string", lambda c, r: (c, [dict(r[0], seed="1")]),
        1, {"art-ledger-01"}, {"msgs": ["seed is not an integer"]}),
    ("meas-empty", lambda c, r: (c, [dict(r[0], measurement={})]),
        1, {"art-accept-02"}, {"findings": 1, "msgs": ["no measurement recorded"]}),
    ("meas-null", lambda c, r: (c, [dict(r[0], measurement=None)]),
        1, {"art-accept-02"}, {"findings": 1, "msgs": ["no measurement recorded"]}),
    ("meas-threshold-only", lambda c, r: (
        c, [dict(r[0], measurement={"threshold": 0.9})]), 1, {"art-accept-02"},
        {"msgs": ["carries no name", "carries no value"]}),
    ("fidelity-string", lambda c, r: (c, [dict(r[0], fidelity="accept")]),
        1, {"art-accept-01", "art-qty-01"}, {"msgs": ["no fidelity verdict"]}),
    ("floor-negative", lambda c, r: (c, [dict(r[0], library_floor=-3)]),
        1, {"art-qty-01"}, {"msgs": ["negative"]}),
    ("consumer-is-directory", lambda c, r: (
        dict(c, stages=[dict(STAGE, consumer="src")]), r), 1, {"art-stage-01"},
        {"msgs": ["not a file"]}),
    ("fidelity-only-no-floor", lambda c, r: (
        c, [dict(r[0], fidelity={"verdict": "reject", "rule": "orthogonal"})]),
        1, {"art-qty-01"}, {"msgs": ["floor=none", "fidelity-fail=1"]}),
    # --- third audit round: an absent rule or digest is not a declared one --
    # `{"furniture": ""}` and `{"furniture": null}` declared a key with no rule
    # in it; the old key-presence test plus the `want and` guard let both go
    # green. Fail closed: the brief names the class and acceptance refuses to
    # compare against nothing. Both also pin the exact finding count.
    ("shape-rule-blank", lambda c, r: (
        dict(c, shape_rules={"furniture": ""}), r), 1,
        {"art-brief-02", "art-accept-01"},
        {"findings": 2,
         "msgs": ["has no geometric rule", "is not the declared rule"]}),
    ("shape-rule-null", lambda c, r: (
        dict(c, shape_rules={"furniture": None}), r), 1,
        {"art-brief-02", "art-accept-01"},
        {"findings": 2,
         "msgs": ["has no geometric rule", "is not the declared rule"]}),
    # One meaning of "class": a padded class is the class it names. With a
    # wrong verdict rule it fails; with the declared rule it passes. The pair
    # pins both halves - no strip leaves the right-rule case red, and the old
    # `want and` guard leaves the wrong-rule case green.
    ("class-padded-wrong-rule", lambda c, r: (
        c, [dict(r[0], **{"class": "furniture "},
                 fidelity={"verdict": "accept", "rule": "anything"})]),
        1, {"art-accept-01"},
        {"msgs": ["is not the declared rule for class 'furniture'"]}),
    ("class-padded-right-rule", lambda c, r: (
        c, [dict(r[0], **{"class": "furniture "})]), 0, set(),
        {"findings": 0}),
    # The declared boolean is trusted only when it is `True`. A truthy string
    # and the integer 1 both used to read as game geometry; `true` stays green
    # in the `pass` case above.
    ("geometry-string", lambda c, r: (
        dict(c, captures={"native": {"renderer": "title-own",
                                     "contains_game_geometry": "false",
                                     "frame_sha256": "s"}}), r),
        1, {"art-draw-01"}, {"msgs": ["contains no game geometry"]}),
    ("geometry-int", lambda c, r: (
        dict(c, captures={"native": {"renderer": "title-own",
                                     "contains_game_geometry": 1,
                                     "frame_sha256": "s"}}), r),
        1, {"art-draw-01"}, {"msgs": ["contains no game geometry"]}),
    ("capture-sha-whitespace", lambda c, r: (
        dict(c, captures={"native": {"renderer": "title-own",
                                     "contains_game_geometry": True,
                                     "frame_sha256": "   "}}), r),
        1, {"art-draw-01"}, {"msgs": ["capture is not digested"]}),
    # The same non-blank rule for replication and for a deletion reason: a
    # non-boolean `present`, a whitespace-only restore timestamp and a
    # whitespace-only reason are each not a record.
    ("replication-present-string", lambda c, r: (
        dict(c, replication={"present": "false",
                             "restore_exercised_at": "2026-01-01T00:00:00Z"}), r),
        1, {"art-bytes-01"}, {"msgs": ["no second copy"]}),
    ("restore-whitespace", lambda c, r: (
        dict(c, replication={"present": True,
                             "restore_exercised_at": "   "}), r),
        1, {"art-bytes-01"}, {"msgs": ["restore path has never been exercised"]}),
    ("deletion-reason-whitespace", lambda c, r: (
        c, [dict(r[0], deleted=True, deletion_reason="   ")]),
        1, {"art-bytes-01"}, {"msgs": ["no recorded reason"]}),
]


def selftest() -> int:
    failed = 0
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "brief.md").write_text(BRIEF_TEXT, encoding="utf-8")
        (root / "src").mkdir()
        (root / "src" / "loader.zig").write_text("// loader\n", encoding="utf-8")
        # One tracked artifact, matching GOOD_ROW's id. Inert while BASE's
        # artifact_dirs is empty; the two artifact-* cases point the scan at it.
        (root / "artifacts").mkdir()
        (root / "artifacts" / "bed.glb").write_text("glb\n", encoding="utf-8")
        for name, mutate, want, want_reqs, *checks in CASES:
            extra = checks[0] if checks else {}
            want_count = extra.get("findings")
            want_msgs = extra.get("msgs", [])
            cfg, rows = mutate(dict(BASE), [dict(GOOD_ROW)])
            (root / "ledger.json").write_text(
                json.dumps({"assets": rows}), encoding="utf-8")
            findings = run_checks(cfg, root)
            got_fail = 1 if findings else 0
            got_reqs = {f.req for f in findings}
            haystack = "\n".join(f"{f.msg} {f.detail}" for f in findings)
            missing_msgs = [s for s in want_msgs if s not in haystack]
            count_bad = want_count is not None and len(findings) != want_count
            if (got_fail != want or got_reqs != want_reqs
                    or missing_msgs or count_bad):
                failed += 1
                print(f"selftest FAIL {name}: expected exit {want} reqs "
                      f"{sorted(want_reqs) or '-'} findings "
                      f"{want_count if want_count is not None else 'any'} "
                      f"msgs {want_msgs or '-'}, got exit {got_fail} reqs "
                      f"{sorted(got_reqs) or '-'} findings {len(findings)}, "
                      f"missing msgs {missing_msgs or '-'}")
                for f in findings:
                    print("   ", f.line())
            else:
                print(f"selftest ok {name}  [{', '.join(sorted(got_reqs)) or '-'}]")

        # --- exit contracts for malformed input ---------------------------
        # Both cases drive real main() and assert the exit code. run_checks
        # alone can show the finding but not that the process exits 1, so the
        # earlier ledger-row check never pinned the exit contract it claimed.
        # A non-object manifest is exit 2; a non-object ledger row is exit 1.
        (root / "bad-manifest.json").write_text("[1, 2]", encoding="utf-8")
        err_buf = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(err_buf):
            code = main(["--root", str(root), "--config", "bad-manifest.json"])
        if code != 2 or "not a JSON object" not in err_buf.getvalue():
            failed += 1
            print(f"selftest FAIL manifest-not-object: exit {code}, "
                  f"stderr {err_buf.getvalue()!r}")
        else:
            print("selftest ok manifest-not-object  [exit 2]")
        # A valid manifest pointing at a ledger whose row is a string. The
        # row is a named art-ledger-01 finding, never a traceback, and the
        # CLI reports it as a contract failure (1), not a usage error (2).
        (root / "art-creation.json").write_text(json.dumps(BASE), encoding="utf-8")
        (root / "ledger.json").write_text(json.dumps({"assets": ["oops"]}), encoding="utf-8")
        out_buf = io.StringIO()
        with contextlib.redirect_stdout(out_buf), \
                contextlib.redirect_stderr(io.StringIO()):
            code = main(["--root", str(root), "--config", "art-creation.json"])
        printed = out_buf.getvalue()
        if (code != 1 or "art-ledger-01" not in printed
                or "not a JSON object" not in printed):
            failed += 1
            print(f"selftest FAIL ledger-row-not-object: exit {code}, "
                  f"stdout {printed!r}")
        else:
            print("selftest ok ledger-row-not-object  [exit 1]")
    # NOT_APPLICABLE must be exit 3, never 0.
    if report([], declared=False, counted=0) != 3:
        failed += 1
        print("selftest FAIL not-applicable exit code")

    print(f"selftest {'ok' if failed == 0 else 'FAIL'}: {len(CASES)} cases, "
          "2 exit-contract checks")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(selftest())
