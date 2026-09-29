#!/usr/bin/env python3
"""Parity matrix: gate_common.py and scripts/lib/gate_common.mjs must agree.

One case table, two runtimes, identical verdicts. This is the contract that
made the consolidation trustworthy — before it, "identical semantics" was a
comment each copy wrote about itself.

Shapes covered (per consolidate-shared-gate-logic task 4):
  annotation forms   // id: reason, # id: reason, bare colon, prev-line
  glob shapes        **, zero-segment **/, nested *, basename vs relpath
  layouts            submodule, standalone, markerless parent (path-only)
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import gate_common  # noqa: E402

JS = SCRIPTS / "lib" / "gate_common.mjs"


def _js_verdicts(cases: list[dict]) -> list:
    # ESM specifier must be a file: URL on every platform.
    spec = json.dumps(JS.resolve().as_uri())
    probe = f"""\
import {{ readFileSync }} from "node:fs";
import {{ globMatch, globMatchesAny, lineHasAllow, projectRootFor }} from {spec};
const cases = JSON.parse(readFileSync(0, "utf8"));
const out = cases.map((c) => {{
  if (c.kind === "allow") return lineHasAllow(c.line, c.id);
  if (c.kind === "glob") return globMatch(c.glob, c.path);
  if (c.kind === "globAny") return globMatchesAny(c.globs, c.rel, c.base);
  if (c.kind === "root") return projectRootFor(c.devgate);
  return null;
}});
process.stdout.write(JSON.stringify(out));
"""
    res = subprocess.run(
        ["node", "--input-type=module", "-e", probe],
        input=json.dumps(cases),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert res.returncode == 0, f"node probe crashed: {res.stderr[:800]}"
    return json.loads(res.stdout)


def test_allow_annotation_forms_parity():
    cases = [
        {"kind": "allow", "line": "// guardrails-allow RULE-1: why", "id": "RULE-1"},
        {"kind": "allow", "line": "# guardrails-allow RULE-1: why", "id": "RULE-1"},
        {"kind": "allow", "line": "// guardrails-allow RULE-1:", "id": "RULE-1"},
        {"kind": "allow", "line": "// guardrails-allow RULE-1:   ", "id": "RULE-1"},
        {"kind": "allow", "line": "// bare next to code", "id": "RULE-1"},
        {"kind": "allow", "line": "code(); // guardrails-allow RULE-1: trailing", "id": "RULE-1"},
        {"kind": "allow", "line": "// guardrails-allow RULE-10: one", "id": "RULE-1"},
        {"kind": "allow", "line": "/* guardrails-allow RULE-1: block */", "id": "RULE-1"},
    ]
    expected = [True, True, False, False, False, True, False, True]
    js = _js_verdicts(cases)
    for case, want, got_py, got_js in zip(cases, expected, [
        gate_common.line_has_allow(c["line"], c["id"]) for c in cases
    ], js):
        assert got_py == want, f"py {case} -> {got_py}, want {want}"
        assert got_js == want, f"js {case} -> {got_js}, want {want}"
        assert got_py == got_js, f"PARITY BREAK {case}: py={got_py} js={got_js}"


def test_glob_shapes_parity():
    cases = [
        {"kind": "glob", "glob": "*.go", "path": "a/b/c.go"},
        {"kind": "glob", "glob": "*.go", "path": "c.go"},
        {"kind": "glob", "glob": "a/**/b", "path": "a/b"},
        {"kind": "glob", "glob": "a/**/b", "path": "a/x/b"},
        {"kind": "glob", "glob": "a/**/b", "path": "a/x/y/b"},
        {"kind": "glob", "glob": "src/**/*", "path": "src/a.rs"},
        {"kind": "glob", "glob": "src/**/*", "path": "src/a/b.rs"},
        {"kind": "glob", "glob": "*.rs", "path": "src/a.rs"},
        {"kind": "globAny", "globs": ["*.py"], "rel": "src/x.py", "base": "x.py"},
        {"kind": "globAny", "globs": ["*.rs"], "rel": "src/x.py", "base": "x.py"},
        {"kind": "globAny", "globs": ["src/*.py"], "rel": "src/x.py", "base": "x.py"},
    ]
    expected = [True, True, True, True, True, True, True, True, True, False, True]
    js = _js_verdicts(cases)
    for case, want, got_js in zip(cases, expected, js):
        if case["kind"] == "glob":
            got_py = gate_common.glob_matches(case["path"], [case["glob"]])
        else:
            got_py = gate_common.glob_matches(case["rel"], case["globs"]) or \
                     gate_common.glob_matches(case["base"], case["globs"])
        assert got_py == want, f"py {case} -> {got_py}, want {want}"
        assert got_js == want, f"js {case} -> {got_js}, want {want}"
        assert got_py == got_js, f"PARITY BREAK {case}: py={got_py} js={got_js}"


def test_layout_root_parity(tmp_path):
    """Submodule/standalone resolution must be path-identical on both sides."""
    sub = tmp_path / ".devgate"
    sub.mkdir()
    standalone = tmp_path / "solo"
    standalone.mkdir()
    markerless_parent = tmp_path / "parent"
    child = markerless_parent / "repo"
    child.mkdir(parents=True)
    (markerless_parent / "package.json").write_text("{}", encoding="utf-8")

    cases = [
        {"kind": "root", "devgate": str(sub)},
        {"kind": "root", "devgate": str(standalone)},
        {"kind": "root", "devgate": str(child)},
    ]
    js = _js_verdicts(cases)
    for case, got_js in zip(cases, js):
        got_py = str(gate_common.project_root_for(Path(case["devgate"])))
        assert got_py == got_js, f"PARITY BREAK {case}: py={got_py} js={got_js}"


def test_readme_form_is_accepted_by_both():
    """The documented line must stay a working exemption on both runtimes."""
    line = "// guardrails-allow PREVENT-029: This file is the API boundary — network calls are intentional"
    assert gate_common.line_has_allow(line, "PREVENT-029")
    assert _js_verdicts([{"kind": "allow", "line": line, "id": "PREVENT-029"}]) == [True]