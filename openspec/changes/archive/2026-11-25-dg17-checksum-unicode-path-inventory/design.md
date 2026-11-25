# Design

## Context

The inventory command currently asks Git for newline-delimited, text-decoded paths. Git may quote paths containing non-ASCII bytes when `core.quotePath` is enabled. The generator filters the quoted representation as if it were the real path, allowing a supported Unicode script to be omitted while generation and verification both succeed. The line-based `CHECKSUMS.sha256` format also cannot represent some Git pathnames safely: CR/LF split or corrupt rows, backslash has host-dependent separator meaning, and trailing whitespace is removed by the current verifier.

## Goals and Non-Goals

**Goals:** include every supported tracked script whose path is valid UTF-8 and representable by the current manifest; reject invalid or unrepresentable supported paths consistently before generation or verification.

**Non-Goals:** change checksum algorithms, the `scripts/` and `hub/` inventory roots, supported script extensions, digest format, unrelated malformed/duplicate-record validation from DG-16, or the CI invocation fixed by DG-13.

## Decisions

1. Invoke `git ls-files -z -- scripts/ hub/` with binary capture and split only on NUL. Do not infer Git path boundaries from `core.quotePath`, locale, or line breaks.
2. Select supported script candidates by their final ASCII extension bytes before decoding. Decode only selected candidate paths as strict UTF-8. Preserve valid Unicode exactly; reject invalid bytes with a stable error that displays escaped bytes.
3. Before either mode proceeds, reject supported paths containing any separator recognized by Python `str.splitlines()` or a backslash. Preserve internal spaces, including spaces in directory components, and other valid UTF-8 names that the current record parser can represent. Escape control/invalid bytes in diagnostics.
4. Reject a duplicate supported raw path record. An unresolved Git index can yield the same pathname at stages 1, 2, and 3; silently hashing it multiple times would create a manifest that verification rejects.
5. Make inventory validation a shared prerequisite for generate and verify. An invalid inventory returns the existing usage exit status, emits no success message, and cannot overwrite an existing manifest. Verification fails before parsing or accepting manifest records.
6. Keep records in the existing `64-hex + two spaces + path` format. Do not introduce Git quoting or alternate escaping syntax.

## Validation design

- In a disposable Git repository with `core.quotePath=true`, commit an ordinary script and a script whose path is constructed from `r\\u00e9sum\\u00e9.py`. Generation must emit both exact records and verification must pass. Also confirm an internal-space path is preserved.
- On capable POSIX fixtures, track each supported `.py` path containing LF, CR, a backslash, a Unicode line separator, or invalid UTF-8 in a separate disposable repository. Check the specific diagnostic in both modes and preserve a sentinel manifest. A noncandidate final suffix with newline is ignored by the checksum inventory. On all hosts, create a real unresolved three-stage index entry and check that duplicate raw paths fail in both modes before manifest I/O.
- Retain DG-16 malformed-digest and duplicate-path controls; retain DG-13 guarded CI diagnostics.

## Risks and Trade-offs

- **Git path is valid but not portable/representable:** explicit failure is preferable to a manifest that drops or aliases a supported script.
- **Strict UTF-8 rejects a byte pathname:** the current manifest is UTF-8 text; fail closed and identify bytes safely rather than generating lossy data.
- **A path contains line separators:** fail before manifest mutation because the record grammar has no escaping layer.
