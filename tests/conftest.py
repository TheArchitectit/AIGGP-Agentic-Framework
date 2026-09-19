"""Repo-root on sys.path so `python3 -m pytest` works from any CWD.

The test files self-insert the repo root too, but conftest runs before
collection — this is the deterministic first insertion (fw-ci-01: test
discovery must not depend on the caller's working directory).
"""
import sys
from pathlib import Path

REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
