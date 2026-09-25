"""workflow_read.py — read a workflow file structurally, without PyYAML.

WHY A READER AND NOT A YAML PARSER
The hosted lane installs only pytest (`.github/workflows/ci.yml`, "Install
pytest") and this repository owns no YAML dependency anywhere, so a module-level
`import yaml` in `tests/` does not degrade one guard — it aborts collection and
takes all 900-odd tests down with it. That happened on the first push of the
publish-trigger guard, and `add-secret-scanning` tasks 6.3 already records the
same failure mode. `parse_workflow` in `test_secret_validation_template.py`
reads `.github/workflows/` this way for the same reason; this is that idiom in
one place, usable by the guard and by the mutation harness.

WHAT IT IS, HONESTLY
A narrow indentation reader for the subset this repository writes: two-space
indents, `key: value`, `key:`, `- item` sequences, inline `[a, b]` flow, `#`
comments, and `|`/`>` block scalars. It is NOT a YAML parser. It refuses — with
an exception, never a silent empty result — anything outside that subset: tabs,
odd indentation, a line that is neither a key nor an item, a flow bracket left
open at end of line, and a block scalar where a scalar is asked for. Refusing is
the contract: the harness asks this reader whether a mutation left the file
readable, and a reader that accepted anything would report a YAML mutation that
breaks parsing as one a test killed.

`Workflow.job_if` therefore raises for an absent job, an absent `if:`, and a
block-scalar `if:` — the three ways a guard could otherwise be handed an empty
or invented condition and quietly evaluate it as false.

Kept out of the `test_*.py` namespace so pytest's collection stays about the
product; the guards for this file are `test_workflow_read.py`.
"""
from __future__ import annotations

_KEY_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"


class WorkflowReadError(Exception):
    """The file uses something this reader does not implement.

    Never raised for a file it merely dislikes: every raise here means the
    caller would otherwise be handed a value the file does not contain.
    """


class _Block(str):
    """A block scalar's body. A `str` so callers that want the text can have it
    — `str` is what `contains a line` assertions want — and a distinct type so
    a caller that wants a SCALAR can refuse instead of silently receiving a
    multi-line string where the file has an indicator."""


def _strip_comment(value: str) -> str:
    """Drop a trailing `# comment`, keeping `#` inside quotes and inside a
    value that does not start one.

    Every action reference in this repository is written `uses: x@sha # v5`; a
    reader that kept the comment would hand the guard a string that matches
    nothing else in the tree.
    """
    out: list[str] = []
    quote = ""
    for i, ch in enumerate(value):
        if quote:
            out.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            out.append(ch)
            continue
        if ch == "#" and (i == 0 or value[i - 1] == " "):
            break
        out.append(ch)
    return "".join(out).strip()


def _unquote(value: str) -> str:
    """A scalar written as one quoted string is that string.

    Only when the WHOLE value is wrapped: `if: a == "#b"` is a plain scalar
    whose quotes are part of it — a GitHub expression's own string literal —
    and stripping those would hand the guard an expression the file does not
    contain. Two quote characters exactly, so an escaped one inside is left
    alone rather than guessed at.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'" \
            and value.count(value[0]) == 2:
        return value[1:-1]
    return value


def _without_quoted(value: str) -> str:
    """The value with quoted segments blanked, so bracket counting cannot be
    fooled by a `[` inside a description."""
    out: list[str] = []
    quote = ""
    for ch in value:
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            continue
        out.append(ch)
    return "".join(out)


def _check_flow(value: str, lineno: int) -> None:
    """A flow bracket left open means the value continues on a later line —
    which this reader cannot follow. The mutations the harness judges are
    single-line edits, so this is the shape that has to be caught rather than
    guessed at."""
    bare = _without_quoted(value)
    for opener, closer in (("[", "]"), ("{", "}")):
        if bare.count(opener) != bare.count(closer):
            raise WorkflowReadError(
                f"line {lineno}: flow syntax spans lines (unbalanced {opener!r} "
                f"in {value!r}); this reader cannot follow it")


def _indent_of(raw: str, lineno: int) -> int:
    lead = raw[:len(raw) - len(raw.lstrip(" \t"))]
    if "\t" in lead:
        raise WorkflowReadError(
            f"line {lineno}: tab in indentation — tabs are not indentation in "
            f"YAML, and accepting them invents a nesting no parser agrees with")
    if len(lead) % 2:
        raise WorkflowReadError(
            f"line {lineno}: indentation of {len(lead)} spaces is not a "
            f"multiple of two")
    return len(lead)


def _split_key(content: str, lineno: int) -> tuple[str, str]:
    """`key:` / `key: value` -> (key, value). Value is "" for a nested block."""
    quote = ""
    for i, ch in enumerate(content):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            continue
        if ch != ":":
            continue
        value = content[i + 1:]
        # `key:value` is a plain scalar in YAML, not a mapping.
        if value and not value.startswith(" "):
            break
        key = content[:i].strip()
        if key and all(c in _KEY_CHARS for c in key):
            return key, _unquote(_strip_comment(value))
        break
    raise WorkflowReadError(
        f"line {lineno}: not a `key:` or a `- ` item: {content!r}")


def _is_comment_or_blank(raw: str) -> bool:
    s = raw.strip()
    return not s or s.startswith("#")


def _next_content(lines: list[str], start: int) -> str:
    for raw in lines[start:]:
        if not _is_comment_or_blank(raw):
            return raw
    return ""


def _block_body(lines: list[str], start: int, parent_indent: int) -> tuple[_Block, int]:
    """Consume a block scalar's body: every following line indented deeper than
    the key, blank lines included. Returns the body and the next index.

    The body is shell, python, or a heredoc in this repository, and parsing it
    as YAML would invent jobs and conditions no runner evaluates.
    """
    body: list[str] = []
    i = start
    while i < len(lines):
        raw = lines[i]
        if not raw.strip():
            body.append("")
            i += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent <= parent_indent:
            break
        body.append(raw)
        i += 1
    while body and not body[-1].strip():
        body.pop()
    if not body:
        return _Block(""), i
    inner = min(len(b) - len(b.lstrip(" ")) for b in body if b.strip())
    return _Block("\n".join(b[inner:] if b.strip() else "" for b in body)), i


def _is_block_scalar(value: str) -> bool:
    if not value or value[0] not in "|>":
        return False
    return all(c in "|>+-0123456789" for c in value)


def _read(text: str) -> dict:
    lines = text.splitlines()
    root: dict = {}
    # (indent that OWNS this container, container). A container is owned by the
    # indent of the key that introduced it, so a sibling at that indent
    # correctly closes it and a child one level deeper does not.
    stack: list[tuple[int, object]] = [(-1, root)]
    i = 0
    while i < len(lines):
        raw = lines[i]
        lineno = i + 1
        if _is_comment_or_blank(raw):
            i += 1
            continue
        indent = _indent_of(raw, lineno)
        content = raw[indent:].rstrip()
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        holder = stack[-1][1]

        if content.startswith("- "):
            if not isinstance(holder, list):
                raise WorkflowReadError(
                    f"line {lineno}: a sequence item under a mapping")
            item: dict = {}
            holder.append(item)
            inner = content[2:].strip()
            if inner:
                if inner.startswith("- "):
                    raise WorkflowReadError(
                        f"line {lineno}: nested sequences are not implemented")
                key, value = _split_key(inner, lineno)
                if value and not _is_block_scalar(value):
                    _check_flow(value, lineno)
                    item[key] = value
                elif _is_block_scalar(value):
                    body, i = _block_body(lines, i + 1, indent)
                    item[key] = body
                    stack.append((indent, item))
                    continue
            stack.append((indent, item))
            i += 1
            continue

        if not isinstance(holder, dict):
            raise WorkflowReadError(f"line {lineno}: a mapping key under a sequence")

        key, value = _split_key(content, lineno)
        if value and not _is_block_scalar(value):
            _check_flow(value, lineno)
            holder[key] = value
            i += 1
            continue
        if _is_block_scalar(value):
            body, i = _block_body(lines, i + 1, indent)
            holder[key] = body
            continue

        nxt = _next_content(lines, i + 1)
        if nxt:
            nxt_indent = len(nxt) - len(nxt.lstrip(" "))
            child: object = [] if (nxt_indent == indent + 2
                                   and nxt[nxt_indent:].startswith("- ")) else {}
        else:
            child = {}
        holder[key] = child
        stack.append((indent, child))
        i += 1
    return root


class Workflow:
    """The tree, plus the two lookups the guards need. The lookups raise rather
    than return a default: see the module docstring."""

    def __init__(self, tree: dict) -> None:
        self.tree = tree

    @property
    def triggers(self) -> dict:
        value = self.tree.get("on")
        return value if isinstance(value, dict) else {}

    @property
    def jobs(self) -> dict:
        value = self.tree.get("jobs")
        return value if isinstance(value, dict) else {}

    def job_if(self, job: str) -> str:
        found = self.jobs.get(job)
        if not isinstance(found, dict):
            raise WorkflowReadError(
                f"no job {job!r} in this workflow (jobs: "
                f"{', '.join(sorted(self.jobs)) or 'none'})")
        if "if" not in found:
            raise WorkflowReadError(
                f"job {job!r} has no `if:` — this guard reads a condition, and "
                f"reading its absence as an empty string would evaluate false "
                f"and report the job as deliberate")
        cond = found["if"]
        if isinstance(cond, _Block) or "\n" in cond:
            raise WorkflowReadError(
                f"job {job!r}'s `if:` is a block scalar; this reader does not "
                f"fold block scalars, and folding would hand the guard a "
                f"condition the file does not contain")
        return cond

    def dispatch_input(self, name: str) -> dict:
        dispatch = self.triggers.get("workflow_dispatch")
        if not isinstance(dispatch, dict):
            raise WorkflowReadError(
                "workflow_dispatch is not a trigger of this workflow")
        inputs = dispatch.get("inputs")
        inputs = inputs if isinstance(inputs, dict) else {}
        found = inputs.get(name)
        if not isinstance(found, dict):
            raise WorkflowReadError(
                f"no {name!r} input on workflow_dispatch (inputs: "
                f"{', '.join(sorted(inputs)) or 'none'})")
        return found


def read_workflow(text: str) -> Workflow:
    return Workflow(_read(text))
