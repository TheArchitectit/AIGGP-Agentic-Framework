#!/usr/bin/env python3
"""Mutation battery for the file-size gate's SCOPE (FAIL-8f9249ca).

The gate sized sixteen languages and not the one this repository's fleet-side
scripts are written in, so `scripts/runner-enroll.sh` reached 589 lines against
a 500-line limit with the FILE-SIZE CHECK reporting nothing. That is the same
shape as FAIL-f6228dda: a SCOPE declaration drifting from its intent, green
because it never looked.

The subject here is therefore scope, not arithmetic. Every mutation removes one
declaration and asks whether a named test notices:
  * the extension list,
  * the test-file prefix convention,
  * the directory list the walk enters.

Two properties this battery asserts about itself, inherited from the sibling
batteries:

  * A mutation that merely BREAKS THE PARSER kills every test at once, which
    looks identical to a clean behavioural kill. Each mutated artifact is
    checked for well-formedness first and reported INVALID rather than killed.
  * The count of the anchor text is asserted before the edit, and a mutation
    whose anchor has drifted is reported rather than silently skipped.

Run it from the repository root: it rewrites files in place and restores them.
It lives in the repository (rather than in /tmp) so that "no survivors" can be
re-checked by whoever reads the ledger next.

The two properties above were this file's own text when it carried its own copy
of the harness. They are now `tests/mutation_harness.py`'s to enforce and
`tests/test_mutation_harness.py`'s to pin — kept here as what this battery
relies on, because a reader checking whether INVALID is really handled should
not have to go find out.

Negative controls: this battery has ONE, and it is a different kind from the
image batteries'. Those mutate shipped code together with the fixture that
models it, so the two agree with each other and the suite cannot see the
defect — proving a fixture property is load-bearing. There is no such pair
here: every mutation below removes a literal that the named test reads
directly, and the fixture is arithmetic (a line count) with no second half to
co-mutate. What this battery CAN be wrong about is its own kill detection — a
harness that reported every mutation as killed would make the whole file
decoration, and no mutation below would notice. The control pins exactly that.
"""
import sys

import mutation_harness  # noqa: E402  (sibling module, tests/ is sys.path[0])


SIZES = "scripts/regression_sizes.py"
CHECK = "scripts/regression_check.py"
T_SIZES = "tests/test_regression_sizes.py"

EXTENSIONS_WITH_SH = '''                     ".rb", ".php", ".js", ".jsx", ".swift", ".c", ".cpp", ".h", ".cs",
                     ".sh", ".zig")'''
EXTENSIONS_WITHOUT_SH = '''                     ".rb", ".php", ".js", ".jsx", ".swift", ".c", ".cpp", ".h", ".cs",
                     ".zig")'''

TEST_PREFIX_WITH_SH = 'TEST_PREFIX_EXTENSIONS = (".py", ".sh", ".zig")'
TEST_PREFIX_WITHOUT_SH = 'TEST_PREFIX_EXTENSIONS = (".py", ".zig")'

DIRS_WITH_SCRIPTS = 'SOURCE_DIRS = []\nfor candidate in ["src", "lib", "app", "extensions", "scripts", "internal", "pkg", "cmd", "game",'
DIRS_WITHOUT_SCRIPTS = 'SOURCE_DIRS = []\nfor candidate in ["src", "lib", "app", "extensions", "internal", "pkg", "cmd", "game",'

MUTATIONS = [
    # S1 — the extension list. Killed by the MUST-flag test; the
    # classification test dies with it, because an unsized file is also an
    # unclassified one.
    ("S1: `.sh` dropped from SOURCE_EXTENSIONS — shell scripts sized again by nobody",
     [(SIZES, EXTENSIONS_WITH_SH, EXTENSIONS_WITHOUT_SH)],
     [T_SIZES], {}),

    # S2 — the test-file prefix convention. Killed by the classification test
    # ALONE: `tests/test_giant.sh` is still flagged as source (601 > 500), so
    # only the assertion that it was judged at TEST_HARD can see this.
    ("S2: `.sh` dropped from TEST_PREFIX_EXTENSIONS — shell tests judged at SRC_HARD",
     [(SIZES, TEST_PREFIX_WITH_SH, TEST_PREFIX_WITHOUT_SH)],
     [T_SIZES], {}),

    # S3 — the directory list. `.sh` in the extension list is inert unless the
    # walk enters scripts/, which is where every shell script here lives. This
    # mutation is what found the missing assertion.
    ("S3: `scripts` dropped from the SOURCE_DIRS candidates — the walk never enters it",
     [(CHECK, DIRS_WITH_SCRIPTS, DIRS_WITHOUT_SCRIPTS)],
     [T_SIZES], {}),
]

# Must SURVIVE. See the docstring: this pins the harness's own kill detection,
# not a fixture property.
NEGATIVE_CONTROLS = [
    ("N1: an extension nothing in the tree uses — must change no outcome",
     [(SIZES, EXTENSIONS_WITH_SH, EXTENSIONS_WITH_SH.replace('".sh", ".zig")', '".sh", ".zig", ".bak")'))],
     [T_SIZES], {}),
]


if __name__ == "__main__":
    sys.exit(mutation_harness.main(
        MUTATIONS, NEGATIVE_CONTROLS,
        "this one MUST survive — it pins the battery's own kill detection"))
