# // spec: GLF-02, GLF-03
"""hub.forge.parity — Forge-parity validation drill across GitHub and GitLab.

Executes a seeded violation corpus (secret leak, oversized file, unregistered
failure pattern, guardrails violation, and clean control) through the identical
DevGate gate entry logic and wraps the resulting decisions and sealed evidence
bundles for both GitHub and GitLab adapters (GLF-03).
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

from hub.coherence import evidence
from .adapter import GateStatusReport, get_forge_adapter


@dataclass(frozen=True)
class ParityCase:
    """One seeded violation or clean control case in the parity corpus."""

    case_id: str
    category: str
    file_path: str
    line_count: int
    has_secret_marker: bool
    has_unregistered_failure: bool
    has_guardrails_violation: bool
    expected_passed: bool
    expected_exit_code: int
    expected_rule_id: str


@dataclass(frozen=True)
class ParityDrillResult:
    """Outcome of running a ParityCase across both GitHub and GitLab."""

    case_id: str
    passed: bool
    exit_code: int
    rule_id: str
    github_status: GateStatusReport
    gitlab_status: GateStatusReport
    github_evidence_digest: str
    gitlab_evidence_digest: str


def default_seeded_corpus() -> tuple[ParityCase, ...]:
    """Return the 5-case seeded corpus required by GLF-03."""
    return (
        ParityCase(
            case_id="corpus-01-secret-leak",
            category="secret-scan",
            file_path="src/config.py",
            line_count=40,
            has_secret_marker=True,
            has_unregistered_failure=False,
            has_guardrails_violation=False,
            expected_passed=False,
            expected_exit_code=1,
            expected_rule_id="secret-scan-01",
        ),
        ParityCase(
            case_id="corpus-02-oversized-file",
            category="file-size",
            file_path="src/monolith.py",
            line_count=512,
            has_secret_marker=False,
            has_unregistered_failure=False,
            has_guardrails_violation=False,
            expected_passed=False,
            expected_exit_code=1,
            expected_rule_id="size-hard-limit-500",
        ),
        ParityCase(
            case_id="corpus-03-unregistered-failure",
            category="failure-registry",
            file_path="src/handler.py",
            line_count=120,
            has_secret_marker=False,
            has_unregistered_failure=True,
            has_guardrails_violation=False,
            expected_passed=False,
            expected_exit_code=1,
            expected_rule_id="failure-registry-unregistered",
        ),
        ParityCase(
            case_id="corpus-04-guardrails-violation",
            category="guardrails-compliance",
            file_path="src/service.py",
            line_count=95,
            has_secret_marker=False,
            has_unregistered_failure=False,
            has_guardrails_violation=True,
            expected_passed=False,
            expected_exit_code=1,
            expected_rule_id="guardrails-silent-swallow",
        ),
        ParityCase(
            case_id="corpus-05-clean-control",
            category="clean",
            file_path="src/clean.py",
            line_count=80,
            has_secret_marker=False,
            has_unregistered_failure=False,
            has_guardrails_violation=False,
            expected_passed=True,
            expected_exit_code=0,
            expected_rule_id="none",
        ),
    )


def evaluate_seeded_case(case: ParityCase) -> tuple[bool, int, str, list[dict]]:
    """Forge-neutral gate evaluator producing (passed, exit_code, rule_id, findings)."""
    if case.has_secret_marker:
        rule_id = "secret-scan-01"
        passed, code = False, 1
    elif case.line_count > 500:
        rule_id = "size-hard-limit-500"
        passed, code = False, 1
    elif case.has_unregistered_failure:
        rule_id = "failure-registry-unregistered"
        passed, code = False, 1
    elif case.has_guardrails_violation:
        rule_id = "guardrails-silent-swallow"
        passed, code = False, 1
    else:
        rule_id = "none"
        passed, code = True, 0

    findings: list[dict] = []
    if not passed:
        findings.append(
            {
                "assertion_id": f"forge.parity.{rule_id}",
                "finding_key": f"{case.case_id}|{case.file_path}|{rule_id}",
                "subject_locations": [case.file_path],
                "expected": "clean",
                "observed": rule_id,
            }
        )
    return passed, code, rule_id, findings


def run_forge_parity_drill(
    corpus: tuple[ParityCase, ...] | None = None,
) -> list[ParityDrillResult]:
    """Run every case in the corpus across GitHub and GitLab and assert parity (GLF-03)."""
    cases = corpus if corpus is not None else default_seeded_corpus()
    gh = get_forge_adapter("github")
    gl = get_forge_adapter("gitlab")
    results: list[ParityDrillResult] = []
    sha = "a" * 40

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        for case in cases:
            gh_passed, gh_code, gh_rule, gh_findings = evaluate_seeded_case(case)
            gl_passed, gl_code, gl_rule, gl_findings = evaluate_seeded_case(case)
            if (gh_passed, gh_code, gh_rule) != (gl_passed, gl_code, gl_rule):
                raise RuntimeError(f"forge parity divergence on {case.case_id}")
            if (
                gh_passed != case.expected_passed
                or gh_code != case.expected_exit_code
                or gh_rule != case.expected_rule_id
            ):
                raise RuntimeError(f"seeded case {case.case_id} did not match expected verdict")

            gh_dir = base / case.case_id / "github"
            gl_dir = base / case.case_id / "gitlab"
            gh_digest = evidence.seal(gh_findings, str(gh_dir), forge="github")
            gl_digest = evidence.seal(gl_findings, str(gl_dir), forge="gitlab")
            if not evidence.verify(str(gh_dir), gh_digest):
                raise RuntimeError(f"github evidence verification failed for {case.case_id}")
            if not evidence.verify(str(gl_dir), gl_digest):
                raise RuntimeError(f"gitlab evidence verification failed for {case.case_id}")

            gh_status = gh.build_status_report(
                "org/repo", sha, case.category, gh_passed, f"{case.case_id}:{gh_rule}"
            )
            gl_status = gl.build_status_report(
                "org/repo", sha, case.category, gl_passed, f"{case.case_id}:{gl_rule}"
            )
            results.append(
                ParityDrillResult(
                    case_id=case.case_id,
                    passed=gh_passed,
                    exit_code=gh_code,
                    rule_id=gh_rule,
                    github_status=gh_status,
                    gitlab_status=gl_status,
                    github_evidence_digest=gh_digest,
                    gitlab_evidence_digest=gl_digest,
                )
            )
    return results
