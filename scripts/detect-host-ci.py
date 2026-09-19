#!/usr/bin/env python3
"""detect-host-ci.py — resolve the host repo's CI / runner info from DevGate.

DevGate is distributed as a submodule (or clone) inside a HOST project at
`.devgate/`. This script answers one question, secrets-cleanly: *"what CI
runner(s) and scheduled drift scans does the host repo already declare?"* so
DevGate's workflow templates can bind to the host's own infrastructure instead
of hardcoding `ubuntu-latest` or a fixed self-hosted label.

Scope of what is extracted — and nothing else:
  * `runs-on:` values from the host's `.github/workflows/*.yml` (runner labels
    and/or `group:`/`labels:` bodies). Labels are identifiers, not secrets.
  * `schedule:` cron lines from those same workflows (drift-scan cadence).

Deliberately NOT extracted (secrets hygiene — this repo is public and the
output may be shared):
  * any `secrets.*`, `env:`, `Environment=`, `RUNNER_TOKEN=`, or token-shaped
    value is redacted to a placeholder before it can reach stdout.
  * no credentials, tokens, URLs with auth, or IP/host addresses are emitted.

Usage:
    python3 detect-host-ci.py                # print JSON summary (exit 0)
    python3 detect-host-ci.py --fail-on-missing   # exit 1 if no host CI found

Output is a JSON object; every field is safe to log/paste.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REDACT = "<redacted>"

# Token/secret/credential shapes that must never survive to stdout.
# The lookarounds treat underscore as a SEPARATOR (unlike \b, which does not
# match between `_` and a letter — RUNNER_TOKEN= must be caught) while still
# refusing to match inside ordinary identifiers like "blacksmith-2x" or
# "make-runner" (the old unanchored alternation redacted 40 characters from
# such labels).
_SECRET_PATTERNS = [
    re.compile(r"(?i)(?<![a-z0-9])(?:token|secret|password|passwd|api[_-]?key|credential|ak|sk)(?![a-z0-9])[^\n]{0,40}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{10,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"),  # JWT-shaped
    re.compile(r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b"),  # IPv4
    re.compile(r"https?://[^\s]+@"),  # URL with embedded auth
]

# Directories never walked when hunting runner assets: VCS metadata,
# dependency trees, and build output can be huge or unreadable, and the old
# unguarded rglob crashed the drift workflow on the first unreadable file.
_WALK_SKIP = {".git", "node_modules", "vendor", "target", "dist", "build",
              "__pycache__", ".venv", "venv", ".devgate"}

_RUNS_ON = re.compile(r"^\s*runs-on:\s*(.+?)\s*$")
_CRON = re.compile(r"^\s*-\s*cron:\s*['\"]?(.+?)['\"]?\s*$")
_SCHEDULE = re.compile(r"^\s*schedule:\s*$")
_TOKENS = set()


def devgate_root() -> Path:
    """Directory this script lives in (the DevGate tree)."""
    return Path(__file__).resolve().parent.parent


def host_repo_root() -> Path | None:
    """The HOST repo that contains DevGate as `.devgate/` (or None standalone).

    Submodule layout:   <host>/.devgate/scripts/detect-host-ci.py
    Clone layout:       <host>/scripts/detect-host-ci.py   (DevGate IS the repo)
    """
    dg = devgate_root()
    if dg.name == ".devgate":
        host = dg.parent
        if (host / ".git").exists() or (host / ".github").exists():
            return host
    # DevGate checked out standalone: it is its own repo, no host to inspect.
    return None


def redact(text: str) -> str:
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub(REDACT, out)
    return out


def collect_workflow_info(host: Path) -> dict[str, list[str]]:
    """Return {'runs_on': [...], 'crons': [...]} from host workflows."""
    runs_on: list[str] = []
    crons: list[str] = []
    wf_dir = host / ".github" / "workflows"
    if not wf_dir.is_dir():
        return {"runs_on": runs_on, "crons": crons}
    # Both extensions: a host may name its workflows .yaml (the old glob
    # missed them entirely and reported "no host CI found").
    for wf in sorted(list(wf_dir.glob("*.yml")) + list(wf_dir.glob("*.yaml"))):
        try:
            raw = wf.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        in_schedule = False
        sched_indent = -1
        for line in raw.splitlines():
            if _SCHEDULE.match(line):
                in_schedule = True
                sched_indent = len(line) - len(line.lstrip())
                continue
            if in_schedule:
                stripped = line.strip()
                if not stripped:
                    continue  # blank lines inside the block are legal YAML
                # Indent-based block end: a sibling/parent key at or left of
                # `schedule:` closes it. The old blank-line-only reset let a
                # `- cron:` under a LATER list (workflow_dispatch) be
                # misattributed to the schedule.
                if (len(line) - len(line.lstrip())) <= sched_indent:
                    in_schedule = False
            m = _RUNS_ON.match(line)
            if m:
                val = redact(m.group(1).strip())
                if val and val not in runs_on:
                    runs_on.append(val)
            c = _CRON.match(line)
            if c and in_schedule:
                crons.append(redact(c.group(1).strip()))
    return {"runs_on": runs_on, "crons": crons}


def collect_runner_assets(host: Path) -> dict[str, list[str]]:
    """Containerfile / quadlet assets the host uses to self-deploy runners.

    Walk is bounded to .github/ and the repo root's immediate tree: runner
    assets live there by convention, and an unguarded rglob over a large
    checkout was slow, followed symlinks, and crashed on unreadable paths."""
    images: list[str] = []
    labels: list[str] = []
    candidates = []
    for base in (host / ".github", host):
        if not base.is_dir():
            continue
        for name in ("Containerfile", "*.container", "*Dockerfile", "*.image"):
            for p in base.rglob(name):
                if any(part in _WALK_SKIP for part in p.relative_to(host).parts):
                    continue
                candidates.append(p)
    for p in sorted(set(candidates)):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # unreadable asset: skipped, never a crash
        for line in text.splitlines():
            if line.strip().startswith("#"):
                continue
            if line.lstrip().startswith("FROM "):
                parts = line.split(None, 2)
                if len(parts) < 2:
                    continue
                img = parts[1]
                if img.startswith("--"):
                    # FROM --platform=... <image>
                    if len(parts) < 3:
                        continue
                    img = parts[2].split()[0]
                img = redact(img.strip())
                if img and img not in images:
                    images.append(img)
            if "RUNNER_LABELS=" in line:
                lab = redact(line.split("=", 1)[1].strip())
                if lab and lab not in labels:
                    labels.append(lab)
    return {"images": images, "labels": labels}


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--fail-on-missing", action="store_true")
    ap.add_argument("--json", action="store_true", help="pretty-print (default)")
    args = ap.parse_args()

    host = host_repo_root()
    if host is None:
        result = {
            "devgate_layout": "standalone",
            "host_repo": None,
            "note": "DevGate is not embedded as .devgate/ — no host CI to resolve.",
        }
        print(json.dumps(result, indent=2))
        return 1 if args.fail_on_missing else 0

    wf = collect_workflow_info(host)
    ra = collect_runner_assets(host)
    result = {
        "devgate_layout": "submodule",
        "host_repo": str(host),
        "runs_on_labels": wf["runs_on"],
        "scheduled_crons": wf["crons"],
        "runner_images": ra["images"],
        "runner_labels": ra["labels"],
    }
    print(json.dumps(result, indent=2))
    has_ci = bool(wf["runs_on"])
    return 1 if (args.fail_on_missing and not has_ci) else 0


if __name__ == "__main__":
    sys.exit(main())