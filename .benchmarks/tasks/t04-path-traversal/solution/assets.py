from pathlib import Path

ROOT = Path(__file__).resolve().parent / "public"


def read_asset(rel_path):
    """Return the bytes of an asset inside ./public."""
    if not isinstance(rel_path, str) or not rel_path:
        raise ValueError("asset path must be a non-empty string")
    candidate = Path(rel_path)
    if candidate.is_absolute():
        raise ValueError("absolute asset paths are not allowed")
    target = (ROOT / candidate).resolve()
    if target != ROOT and ROOT not in target.parents:
        raise ValueError("asset path escapes the assets root")
    return target.read_bytes()
