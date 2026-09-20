import json
from pathlib import Path


def load_journal(path):
    """Return (entries, recovered) from a JSONL journal file.

    recovered=True when the trailing line was incomplete (partial write)
    and was skipped. A corrupt NON-trailing line is a hard ValueError.
    BUG: any bad line crashes.
    """
    entries = []
    text = Path(path).read_text(encoding="utf-8")
    for line in text.splitlines():
        entries.append(json.loads(line))  # BUG: no trailing-line tolerance
    return entries, False
