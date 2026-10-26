# Text charset standard (fw-charset-01)

**Rule:** tracked text files are **ASCII** (0x00–0x7F). Non-ASCII glyphs are a
defect: they are not English, and their rendering is not portable across
terminals, fonts, log pipelines, review UIs, and AI tokenizers.

## The defect this closes

`U+00A7 SECTION SIGN is used across the source specs as a section
marker (`spec 12 U+00A7 3.2`). In several clients it renders as a dollar-ish glyph,
so a reviewer read `spec 12 U+00A7 3.2` as `spec 12 $3.2` and filed it as a defect.
The character is not an English-language character, and the ambiguity is real.
The same class covers curly quotes, en/em dashes, arrows, box-drawing, and
emoji used in place of plain English.

## The gate

`scripts/check_charset.py` (wired into the `self-gates` CI job) fails on any
non-ASCII codepoint in a tracked text file that is not on the reviewed
allowlist. It reports `file:line:column`, the codepoint, and the ASCII
replacement.

```bash
python3 scripts/check_charset.py --repo .            # normal (ratchet)
python3 scripts/check_charset.py --repo . --list     # every violation
python3 scripts/check_charset.py --repo . --no-baseline  # strict, zero tolerance
python3 scripts/check_charset.py --repo . --write-baseline  # regenerate the ratchet
```

### Policy: `.guardrails/charset-allowlist.json`

An explicit, reason-carrying allowlist preserves typography that carries
structural meaning (dashes, arrows, box-drawing, status glyphs, math and
currency signs). It may **narrow** the standard but never disable it:

- every row needs a `reason`; a malformed row is a hard error (exit 2);
- the `deny` list always beats `allow`; a codepoint in both refuses to run;
- `U+00A7` is **denied** so a later edit cannot silently reintroduce the
  reported defect;
- `strict_zero` rows name path prefixes the ratchet may **not** grandfather —
  code stays zero-tolerance even when a baseline exists;
- `ignore` rows exempt content/data fixtures whose bytes are the record
  itself (e.g. an as-received post-content export that is the import source of
  record) from the whole check, substitution artifacts included. This is not
  a general escape hatch: an `ignore` row that covers a `strict_zero` scope is
  a policy contradiction and refuses to run — content is exemptable, code is
  not, by construction.

### Ratchet: `.guardrails/charset-baseline.json`

Landing an ASCII-only standard across a large existing tree cannot be a
big-bang rewrite. The baseline grandfathers each file's current count so the
gate can go live immediately, while a file may **never exceed** its baseline
(new debt fails) and a file that drops below it is reported so the baseline
can be tightened. This mirrors `traceability-ratchet.json`. Fix files as you
touch them and rerun `--write-baseline`.

## ASCII replacements

| Glyph | Codepoint | Use instead |
| --- | --- | --- |
| U+00A7 | U+00A7 | `Sec.` |
| `—` `–` | U+2014 / U+2013 | `-` |
| `“` `”` `‘` `’` | U+201C/D / U+2018/9 | `"` / `'` |
| `…` | U+2026 | `...` |
| `→` `←` | U+2192 / U+2190 | `->` / `<-` |
| `×` | U+00D7 | `x` |
| emoji | U+1F300–U+1FAFF | plain English (`OK`, `FAIL`) |

## Propagation

DevGate is consumed as a submodule at `.devgate/`; the `self-gates` job runs
the bundled gate against the consumer's own tree, and `.guardrails/` is the
per-project overlay. Fixing this gate in DevGate ships the standard to every
consumer. Existing consumer debt is handled by that repo's own
`.guardrails/charset-baseline.json`, tightened as CI runs.
