# Design

## Context

Independent Windows execution found that `scripts/forge_parity_drill.py`
exits 1 because `corpus-02-surface-divergence` gets a usage exit 2. The
root cause is `_materialize` in `hub/forge/parity.py`: the seed contains
`{root}` inside JSON produced by `json.dumps`, then substitutes native
`str(root)`. A Windows path such as `C:\\...` becomes raw JSON string
content with invalid escapes. Slash normalization alone also fails for legal
POSIX paths containing a double quote. The substitution must use
`json.dumps(root.as_posix())[1:-1]` so both separators and JSON-special
characters are escaped, while JSON decoding returns the same absolute path.
Command-line argument substitution is a separate code path and retains native
path form.

## Goals / Non-Goals

**Goals:** preserve JSON validity and absolute path semantics on Windows and
for legal POSIX path characters, and keep the pinned corpus bytes/digest stable.

**Non-Goals:** change the corpus version, expected gate outcomes, forge
normalization, or any live GitLab acceptance claim.

## Decisions

- Apply slash normalization and JSON string escaping only when replacing
  `{root}` inside serialized seed file content. `json.dumps(...)[1:-1]`
  escapes quotes and backslashes while retaining a decodable absolute path.
- Keep `_run_commands` argument substitution as `str(root)` because subprocess
  argv is not JSON and requires native path resolution.
- Add a test that calls the real `_materialize`, parses `surfaces.json`, and
  verifies each generated path is absolute and points into the fixture root.
- Keep the corpus definition and `hub/forge/corpus.lock.json` unchanged.

## Risks / Trade-offs

- [A path separator or quote makes the seed JSON invalid] -> assert decoded
  absolute paths for Windows roots and quoted POSIX roots, then run the actual
  surface gate on the POSIX quoted-path fixture.
- [A host-specific fix changes the lock] -> compare `corpus_digest()` before
  and after; the placeholder corpus is deliberately left untouched.

## Migration Plan

Land the focused test and substitution change, run the direct five-case drill
and relevant adapter/template tests on Windows, then run the same drill on a
Linux checkout with the pinned toolchain. Preserve exact exit codes and the
existing corpus lock; archive after independent review.
