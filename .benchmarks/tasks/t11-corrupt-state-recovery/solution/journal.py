import json
from pathlib import Path


def load_journal(path):
    """Return (entries, recovered) from a JSONL journal file.

    recovered=True when the trailing line was incomplete (partial write)
    and was skipped. A corrupt NON-trailing line is a hard ValueError.
    """
    entries = []
    text = Path(path).read_text(encoding="utf-8")
    lines = text.splitlines()
    for i, line in enumerate(lines):
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            if i == len(lines) - 1:
                return entries, True  # trailing partial write: recover
            raise ValueError(f"corrupt journal line {i + 1}") from None
    return entries, False
