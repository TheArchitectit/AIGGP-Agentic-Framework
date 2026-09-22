# // spec: root-anchor-01, root-anchor-03
"""DevGate scanner project-root contract — the Python home for "which tree does
a scanner operate on." Mirrors scripts/lib/project-root.mjs; both implement the
same layout rule so a Python and a Node scanner never disagree on the root.

The contract (external audit 2026-09-20, requirements root-anchor-01 / -03):
  A scanner resolves the project root from its OWN file location by layout. The
  directory that CONTAINS `.devgate/` is the project (submodule layout); when
  DevGate runs as its own repository (standalone), DevGate itself IS the
  project. A scanner SHALL NOT choose a root by walking ancestors looking for a
  marker file (package.json / .git / Cargo.toml / ...), and SHALL NOT use
  process.cwd().

Why not a marker walk-up: regression_check.py and scene_inventory.py resolved
their root by scanning up from Path.cwd() for the first marker. Run inside a
repo that has no marker of its own, whose PARENT is a shared directory (e.g.
/mnt/data/git, which carries a package.json), the walk-up settled on that
parent and the scanner evaluated sibling repositories — a gate that believed it
covered the project silently covered a foreign tree. Worse, the answer moved
with the invocation directory, so the same command resolved different roots
from different cwds. A root named by layout is a pure function of the script's
path: stable, and never outside the tree it ships in.

devgate_root is the caller's own directory (the `.devgate/` or standalone repo
that contains scripts/), resolved the same way every scanner already resolves
its siblings:
    Path(__file__).resolve().parent.parent
"""

from __future__ import annotations

from pathlib import Path

_MARKER = ".devgate"


def project_root_for(devgate_root: Path | str) -> Path:
    """Return the project root for a scanner living under ``devgate_root``.

    Pure function of the path — never consults the filesystem. ``devgate_root``
    is the directory that holds this scanner's ``scripts/`` folder (the
    ``.devgate/`` submodule dir, or the standalone DevGate checkout).
    """
    devgate_root = Path(devgate_root)
    if devgate_root.name == _MARKER:
        # Submodule layout: the dir CONTAINING .devgate/ is the project.
        return devgate_root.parent
    # Standalone layout: DevGate is its own project.
    return devgate_root
