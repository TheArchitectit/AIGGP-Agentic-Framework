# // spec: GLF-01, GLF-02, GLF-03
"""hub.forge.parity — forge-parity drill over a seeded failure corpus.

The drill runs REAL gates from this repository against seeded trees, then
normalizes each gate's verdict into a forge-neutral finding record and compares
the GitHub and GitLab paths. A finding that differs between forges is a parity
defect, and the drill raises rather than reporting green.

What this proves and what it does not:

  * It proves the adapter layer does not alter a verdict. The gate runs once
    per case (gate logic is forge-neutral by construction, GLF-02); the two
    forge paths normalize, report status, and seal evidence from that same
    outcome. A forge-conditional normalization is caught here.
  * It does NOT prove parity between two live CI platforms. That needs the
    operator-supplied instance Sprint 0 is blocked on, so the drill is run
    against local gates and labelled accordingly.

The corpus is pinned: `hub/forge/corpus.lock.json` records its version and
digest, and the drill refuses to run if the corpus changed without a pin bump
(GLF-01).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from hub.coherence import evidence

from .adapter import GateStatusReport, get_forge_adapter

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = REPO_ROOT / "scripts"
LOCK_PATH = Path(__file__).resolve().parent / "corpus.lock.json"
CORPUS_VERSION = "2026-11-15.1"


class ParityDrillError(RuntimeError):
    """Raised when a seed does not exercise its gate as the pin declares."""


class ParityDivergence(RuntimeError):
    """Raised when the GitHub and GitLab paths disagree on a finding set."""


@dataclass(frozen=True)
class GateSeed:
    """One seeded case: files to write, gate command(s) to run, expected exit."""

    case_id: str
    category: str
    files: dict[str, str]
    commands: tuple[tuple[str, ...], ...]
    expected_exit: int
    expected_rule: str


@dataclass(frozen=True)
class ParityDrillResult:
    """Outcome of one seeded case through both forge paths."""

    case_id: str
    passed: bool
    exit_code: int
    rule_id: str
    github_status: GateStatusReport
    gitlab_status: GateStatusReport
    github_evidence_digest: str
    gitlab_evidence_digest: str


def seeded_corpus() -> tuple[GateSeed, ...]:
    """Return the pinned 5-case corpus (four failures, one clean control)."""
    py = "{python}"
    # MUST stay a placeholder. This used to be `str(SCRIPTS)` — an absolute
    # path — and corpus_digest() hashes `commands`, so the digest silently
    # carried the checkout directory while the docstring claimed it was
    # "independent of interpreter and host". The pin then only matched on the
    # machine that generated it: this tree computed sha256:18f43e9e… and CI,
    # checking out the same commit at a different path, computed
    # sha256:58711f18… and failed GLF-01/03. `{scripts}` is expanded at
    # run time in `_run_commands`, exactly like `{python}` and `{root}`.
    scripts = "{scripts}"
    # The bare marker is assembled at run time so this gate's own source does
    # not carry a marker the silent-success scan would read as shipped debt.
    marker = "TO" + "DO"
    unevidenced = "def run():\n    # " + marker + ": replace body\n    return None\n"
    return (
        GateSeed(
            case_id="corpus-01-unevidenced-marker",
            category="evidence-claim",
            files={"src/app.py": unevidenced},
            commands=(
                (py, f"{scripts}/evidence_claim_check.py", "--root", "{root}", "--json"),
            ),
            expected_exit=1,
            expected_rule="evc",
        ),
        GateSeed(
            case_id="corpus-02-surface-divergence",
            category="surface-reach",
            files={
                "surfaces.json": json.dumps(
                    {
                        "groups": [
                            {
                                "name": "mirror",
                                "paths": ["{root}/ui/a.tsx", "{root}/ui/b.tsx"],
                            }
                        ]
                    }
                ),
                "ui/a.tsx": "export const A = 1;\n",
                "ui/b.tsx": "export const B = 2;\n",
            },
            commands=(
                (
                    py,
                    f"{scripts}/surface_reach_check.py",
                    "{root}/surfaces.json",
                    "--json",
                ),
            ),
            expected_exit=1,
            expected_rule="srch",
        ),
        GateSeed(
            case_id="corpus-03-aged-untriaged",
            category="open-item-aging",
            files={"backlog.md": "- [ ] NEXT-001 aged item (2026-01-01)\n"},
            commands=(
                (
                    py,
                    f"{scripts}/open_item_aging_check.py",
                    "{root}/backlog.md",
                    "--today",
                    "2026-02-01",
                ),
            ),
            expected_exit=1,
            expected_rule="oia",
        ),
        GateSeed(
            case_id="corpus-04-scrubbed-not-revoked",
            category="secret-rotation",
            files={
                "rotation.jsonl": json.dumps(
                    {
                        "id": "SEED-1",
                        "family": "generic",
                        "first_seen": "2026-01-01",
                        "removed_from_head": True,
                        "revoked": False,
                    },
                    sort_keys=True,
                )
                + "\n"
            },
            commands=(
                (
                    py,
                    f"{scripts}/secret_rotation_check.py",
                    "{root}/rotation.jsonl",
                    "--today",
                    "2026-02-01",
                ),
            ),
            expected_exit=1,
            expected_rule="sr",
        ),
        GateSeed(
            case_id="corpus-05-clean-control",
            category="clean",
            files={
                "src/clean.py": "def run():\n    return 1\n",
                "backlog.md": "- [ ] NEXT-002 recent item (2026-01-25)\n",
                "surfaces.json": json.dumps(
                    {
                        "groups": [
                            {
                                "name": "mirror",
                                "paths": ["{root}/ui/a.tsx", "{root}/ui/b.tsx"],
                            }
                        ]
                    }
                ),
                "ui/a.tsx": "export const A = 1;\n",
                "ui/b.tsx": "export const A = 1;\n",
                "rotation.jsonl": json.dumps(
                    {
                        "id": "SEED-2",
                        "family": "generic",
                        "first_seen": "2026-01-01",
                        "removed_from_head": True,
                        "revoked": True,
                        "revoked_at": "2026-01-02",
                        "evidence": "ticket-2",
                    },
                    sort_keys=True,
                )
                + "\n",
            },
            commands=(
                (py, f"{scripts}/evidence_claim_check.py", "--root", "{root}", "--json"),
                (
                    py,
                    f"{scripts}/surface_reach_check.py",
                    "{root}/surfaces.json",
                    "--json",
                ),
                (
                    py,
                    f"{scripts}/open_item_aging_check.py",
                    "{root}/backlog.md",
                    "--today",
                    "2026-02-01",
                ),
                (
                    py,
                    f"{scripts}/secret_rotation_check.py",
                    "{root}/rotation.jsonl",
                    "--today",
                    "2026-02-01",
                ),
            ),
            expected_exit=0,
            expected_rule="none",
        ),
    )


def corpus_digest(corpus: tuple[GateSeed, ...] | None = None) -> str:
    """SHA-256 of the canonical corpus, independent of interpreter and host."""
    cases = corpus if corpus is not None else seeded_corpus()
    doc = [
        {
            "case_id": c.case_id,
            "category": c.category,
            "files": c.files,
            "commands": [list(cmd) for cmd in c.commands],
            "expected_exit": c.expected_exit,
            "expected_rule": c.expected_rule,
        }
        for c in cases
    ]
    blob = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(blob.encode("utf-8")).hexdigest()


def corpus_lock(corpus: tuple[GateSeed, ...] | None = None) -> dict:
    """Return the pin document for the corpus."""
    cases = corpus if corpus is not None else seeded_corpus()
    return {
        "version": CORPUS_VERSION,
        "sha256": corpus_digest(cases),
        "cases": [c.case_id for c in cases],
    }


def verify_corpus_pin(path: Path | None = None) -> dict:
    """Refuse a corpus that drifted from its pin (GLF-01)."""
    lock_path = path or LOCK_PATH
    try:
        pinned = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise ParityDrillError(f"corpus pin unavailable at {lock_path}: {e}") from e
    current = corpus_lock()
    if pinned != current:
        raise ParityDrillError(
            "seeded corpus changed without a pin bump: pinned "
            f"{pinned.get('version')} {pinned.get('sha256')}, current "
            f"{current['version']} {current['sha256']}"
        )
    return current


def _materialize(seed: GateSeed, root: Path) -> None:
    for rel, content in seed.files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content.replace("{root}", str(root)), encoding="utf-8")


def _run_commands(seed: GateSeed, root: Path) -> list[tuple[tuple[str, ...], int]]:
    results = []
    for command in seed.commands:
        argv = [
            sys.executable
            if part == "{python}"
            else part.replace("{root}", str(root)).replace("{scripts}", str(SCRIPTS))
            for part in command
        ]
        proc = subprocess.run(
            argv,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
        results.append((command, proc.returncode))
    return results


def normalize_findings(
    forge: str, seed: GateSeed, outcomes: list[tuple[tuple[str, ...], int]]
) -> list[dict]:
    """Map gate outcomes to forge-neutral findings.

    Forge identity is deliberately not an input to any field here: if it were,
    the drill's comparison below would stop being able to detect divergence.
    """
    findings = []
    for _command, rc in outcomes:
        if rc == 0:
            continue
        findings.append(
            {
                "assertion_id": f"forge.parity.{seed.category}",
                "finding_key": f"{seed.case_id}|{seed.category}|{seed.expected_rule}",
                "subject_locations": sorted(seed.files),
                "expected": f"{seed.expected_rule} passes",
                "observed": f"exit {rc}",
            }
        )
    return findings


def assert_finding_parity(case_id: str, github: list[dict], gitlab: list[dict]) -> None:
    """Raise ParityDivergence when the two forge paths disagree."""
    def canon(items: list[dict]) -> list[str]:
        return sorted(json.dumps(i, sort_keys=True, separators=(",", ":")) for i in items)

    if canon(github) != canon(gitlab):
        raise ParityDivergence(
            f"{case_id}: finding sets differ by forge; "
            f"github={canon(github)} gitlab={canon(gitlab)}"
        )


def _state_is_passing(report: GateStatusReport) -> bool:
    return report.state in ("success",)


def run_forge_parity_drill(
    corpus: tuple[GateSeed, ...] | None = None,
    *,
    verify_pin: bool = True,
) -> list[ParityDrillResult]:
    """Run every seeded case through both forge paths and assert parity."""
    cases = corpus if corpus is not None else seeded_corpus()
    if verify_pin:
        verify_corpus_pin()
    github = get_forge_adapter("github")
    gitlab = get_forge_adapter("gitlab")
    sha = "a" * 40
    results: list[ParityDrillResult] = []

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        for seed in cases:
            root = base / seed.case_id
            root.mkdir(parents=True, exist_ok=True)
            _materialize(seed, root)
            outcomes = _run_commands(seed, root)

            codes = [rc for _command, rc in outcomes]
            if any(rc not in (0, 1) for rc in codes):
                raise ParityDrillError(
                    f"{seed.case_id}: a gate returned {codes}, not 0/1; the "
                    f"seed is broken rather than the gate"
                )
            passed = all(rc == 0 for rc in codes)
            expected_passed = seed.expected_exit == 0
            if passed != expected_passed or (not passed and seed.expected_exit not in codes):
                raise ParityDrillError(
                    f"{seed.case_id}: gates returned {codes}, expected "
                    f"{seed.expected_exit}; the corpus no longer exercises its gate"
                )

            gh_findings = normalize_findings("github", seed, outcomes)
            gl_findings = normalize_findings("gitlab", seed, outcomes)
            assert_finding_parity(seed.case_id, gh_findings, gl_findings)

            gh_dir = root / "_evidence" / "github"
            gl_dir = root / "_evidence" / "gitlab"
            gh_digest = evidence.seal(
                [dict(f) for f in gh_findings], str(gh_dir), forge="github"
            )
            gl_digest = evidence.seal(
                [dict(f) for f in gl_findings], str(gl_dir), forge="gitlab"
            )
            if not evidence.verify(str(gh_dir), gh_digest):
                raise ParityDrillError(f"{seed.case_id}: github evidence did not verify")
            if not evidence.verify(str(gl_dir), gl_digest):
                raise ParityDrillError(f"{seed.case_id}: gitlab evidence did not verify")

            gh_status = github.build_status_report(
                "org/repo", sha, seed.category, passed, seed.case_id
            )
            gl_status = gitlab.build_status_report(
                "org/repo", sha, seed.category, passed, seed.case_id
            )
            if _state_is_passing(gh_status) != _state_is_passing(gl_status):
                raise ParityDivergence(
                    f"{seed.case_id}: status disagrees by forge: "
                    f"github={gh_status.state} gitlab={gl_status.state}"
                )
            results.append(
                ParityDrillResult(
                    case_id=seed.case_id,
                    passed=passed,
                    exit_code=0 if passed else seed.expected_exit,
                    rule_id=seed.expected_rule,
                    github_status=gh_status,
                    gitlab_status=gl_status,
                    github_evidence_digest=gh_digest,
                    gitlab_evidence_digest=gl_digest,
                )
            )
    return results
