"""Compare canonical requirement headings with the pinned OpenSpec CLI inventory."""
# spec: spec-fmt-05
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.spec_discovery import DRAFT, _requirement_blocks
ID_LINE = re.compile(r"^\s*<!--\s*id:\s*(.*?)\s*-->\s*$")
ID_DIRECTIVE = re.compile(r"<!--\s*id:", re.I)
HEADING = re.compile(r"^### Requirement:\s*(.+?)\s*$", re.M)
SUPPORTED_ID = re.compile(r"[A-Za-z0-9-]+\Z")
UNSUPPORTED_ID = {"...", "…"}


def canonical_inventory(root: Path) -> tuple[dict[str, list[str]], list[str]]:
    """Return capability -> headings and actionable local format errors."""
    headings: dict[str, list[str]] = {}
    errors: list[str] = []
    seen_ids: dict[str, str] = {}
    for path in sorted((root / "openspec/specs").glob("*/spec.md")):
        capability = path.parent.name
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        entries = list(HEADING.finditer(text))
        headings[capability] = [m.group(1) for m in entries]
        assigned_lines: set[int] = set()
        local_ids: list[str] = []
        for i, match in enumerate(entries):
            label = f"{capability}: {match.group(1)}"
            end = entries[i + 1].start() if i + 1 < len(entries) else len(text)
            requirement_text = text[match.end():end]
            heading_line = text.count("\n", 0, match.start())
            marker_line = heading_line + 1
            while marker_line < len(lines) and not lines[marker_line].strip():
                marker_line += 1
            raw_marker = lines[marker_line] if marker_line < len(lines) else ""
            marker = ID_LINE.fullmatch(raw_marker)
            if not marker:
                if ID_DIRECTIVE.search(raw_marker):
                    assigned_lines.add(marker_line)
                    detail = "unclosed" if "-->" not in raw_marker else "malformed"
                    errors.append(f"{label}: {detail} ID marker immediately below the requirement heading")
                else:
                    errors.append(f"{label}: missing ID marker immediately below the requirement heading")
                continue
            assigned_lines.add(marker_line)
            rid = marker.group(1).strip()
            if not SUPPORTED_ID.fullmatch(rid) or rid in UNSUPPORTED_ID:
                errors.append(f"{label}: malformed or unsupported ID marker {rid!r}")
                continue
            if rid in seen_ids:
                errors.append(f"{label}: duplicate ID {rid!r} (also {seen_ids[rid]})")
            seen_ids[rid] = label
            if not DRAFT.search(requirement_text):
                local_ids.append(rid)
        in_fence = False
        for line_number, line in enumerate(lines):
            if re.match(r"^\s*(```|~~~)", line):
                in_fence = not in_fence
                continue
            if (not in_fence and line_number not in assigned_lines
                    and line.lstrip().startswith("<!--") and ID_DIRECTIVE.search(line)):
                if "-->" not in line:
                    errors.append(f"{capability}: unclosed extra ID marker outside a requirement heading")
                elif ID_LINE.fullmatch(line):
                    errors.append(f"{capability}: extra ID marker outside a requirement heading")
                else:
                    errors.append(f"{capability}: malformed extra ID marker outside a requirement heading")
        shared_ids = [rid for rid, block in _requirement_blocks(text) if not DRAFT.search(block)]
        if shared_ids != local_ids:
            errors.append(
                f"{capability}: shared parser IDs {shared_ids!r} differ from heading IDs {local_ids!r}"
            )
    return headings, errors


def cli_inventory(executable: str = "openspec") -> tuple[dict[str, list[str]], list[str]]:
    """Read canonical requirement names/counts through OpenSpec CLI JSON."""
    def run(*args: str) -> dict:
        result = subprocess.run([executable, *args], cwd=ROOT, capture_output=True,
                                text=True, check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        return json.loads(result.stdout)

    listed = run("list", "--specs", "--json")["specs"]
    inventory: dict[str, list[str]] = {}
    errors: list[str] = []
    for spec in listed:
        capability = spec["id"]
        detail = run("show", capability, "--type", "spec", "--json")
        names = [req["name"] for req in detail["requirements"]]
        if detail["requirementCount"] != len(names) or spec["requirementCount"] != len(names):
            errors.append(f"{capability}: CLI count disagrees with returned requirements")
        inventory[capability] = names
    return inventory, errors


def validate(local: dict[str, list[str]], cli: dict[str, list[str]], errors: list[str]) -> list[str]:
    failures = list(errors)
    for capability in sorted(set(local) | set(cli)):
        ours, theirs = local.get(capability, []), cli.get(capability, [])
        if ours != theirs:
            failures.append(f"{capability}: CLI headings {theirs!r} differ from marker inventory {ours!r}")
    return failures


def main() -> int:
    executable = sys.argv[1] if len(sys.argv) > 1 else "openspec"
    try:
        local, errors = canonical_inventory(ROOT)
        cli, cli_errors = cli_inventory(executable)
    except (OSError, RuntimeError, ValueError, KeyError) as exc:
        print(f"spec ID inventory: ERROR: {exc}", file=sys.stderr)
        return 2
    failures = validate(local, cli, errors + cli_errors)
    if failures:
        print("spec ID inventory: FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    total = sum(map(len, local.values()))
    print(f"spec ID inventory: PASS ({len(local)} capabilities, {total} requirements)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
