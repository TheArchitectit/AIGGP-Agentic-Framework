from pathlib import Path

ROOT = Path(__file__).resolve().parent / "public"


def read_asset(rel_path):
    """Return the bytes of an asset inside ./public."""
    target = ROOT / rel_path   # BUG: no containment check
    return target.read_bytes()
