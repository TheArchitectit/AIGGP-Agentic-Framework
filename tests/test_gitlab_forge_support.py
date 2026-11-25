# // spec: GLF-01, GLF-02, GLF-03, GLF-10, GLF-11, GLF-12, GLF-13, GLF-14
"""Tests for GitLab forge parity and self-hosted instance/runner support."""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from hub.coherence import evidence, schemacheck  # noqa: E402
from hub.forge import (  # noqa: E402
    BackupDrillReport,
    ForgeAuthError,
    ForgeError,
    InstanceDeclaration,
    OwnershipValidationError,
    RunnerImageError,
    get_forge_adapter,
    run_forge_parity_drill,
    seeded_corpus,
    validate_backup_restore_drill,
    validate_instance_declaration,
    validate_runner_image_pin,
    verify_gitlab_ci_template_mirrors,
)
from hub.registry import Registry  # noqa: E402
from hub.forge.parity import _materialize  # noqa: E402
from tests.fixtures.runner_spoke import HUB, SCRIPT, Spoke  # noqa: E402


def test_glf01_all_github_workflow_templates_have_pinned_gitlab_mirrors():
    """GLF-01 & GLF-12: every reusable GitHub workflow template has a GitLab CI mirror
    with a digest-pinned image."""
    mirrors = verify_gitlab_ci_template_mirrors(REPO)
    gh_count = len(list((REPO / "templates" / "github-workflows").glob("*.yml")))
    assert len(mirrors) == gh_count == 10
    assert "guardrails-compliance.gitlab-ci.yml" in mirrors
    assert "secret-validation.gitlab-ci.yml" in mirrors


def test_glf02_github_and_gitlab_webhook_verification_and_diff_context():
    """GLF-02: constant-time webhook verification, diff context extraction, and status payloads."""
    gh = get_forge_adapter("github")
    gl = get_forge_adapter("gitlab")
    with pytest.raises(ForgeError):
        get_forge_adapter("bitbucket")

    secret = "webhook-test-secret-not-real"
    body = b'{"object_kind":"merge_request"}'
    gh_sig = "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    assert gh.verify_webhook({"X-Hub-Signature-256": gh_sig}, body, secret) is True
    with pytest.raises(ForgeAuthError):
        gh.verify_webhook({"X-Hub-Signature-256": "sha256=" + "0" * 64}, body, secret)

    assert gl.verify_webhook({"X-Gitlab-Token": secret}, body, secret) is True
    with pytest.raises(ForgeAuthError):
        gl.verify_webhook({"X-Gitlab-Token": "wrong-token"}, body, secret)

    gh_ctx = gh.extract_diff_context(
        {
            "repository": {"full_name": "aiggp/framework"},
            "pull_request": {
                "number": 42,
                "base": {"ref": "main"},
                "head": {"sha": "b" * 40},
            },
            "changed_files": ["hub/server.py", "README.md"],
        }
    )
    assert gh_ctx.forge == "github"
    assert gh_ctx.repository == "aiggp/framework"
    assert gh_ctx.change_id == 42
    assert gh_ctx.changed_files == ("hub/server.py", "README.md")

    gl_ctx = gl.extract_diff_context(
        {
            "project": {"path_with_namespace": "aiggp/framework"},
            "object_attributes": {
                "iid": 42,
                "target_branch": "main",
                "last_commit": {"id": "b" * 40},
            },
            "changed_files": ["hub/server.py", "README.md"],
        }
    )
    assert gl_ctx.forge == "gitlab"
    assert gl_ctx.repository == "aiggp/framework"
    assert gl_ctx.change_id == 42
    assert gl_ctx.head_sha == "b" * 40

    gl_status = gl.build_status_report("aiggp/framework", "b" * 40, "secret-scan", False, "failed")
    assert gl_status.endpoint == f"/api/v4/projects/aiggp%2Fframework/statuses/{'b' * 40}"
    assert gl_status.state == "failed"


def test_glf02_evidence_bundle_records_and_verifies_forge_metadata():
    """GLF-02: sealed evidence bundles record forge ('github' | 'gitlab') and verify."""
    finding = {
        "assertion_id": "forge.parity.check",
        "finding_key": "k1",
        "subject_locations": ["src/a.py"],
        "expected": "clean",
        "observed": "violated",
    }
    with tempfile.TemporaryDirectory() as td:
        out_gl = Path(td) / "gl"
        digest = evidence.seal([dict(finding)], str(out_gl), forge="gitlab")
        manifest = json.loads((out_gl / "evidence-manifest.json").read_text(encoding="utf-8"))
        assert manifest["forge"] == "gitlab"
        assert evidence.verify(str(out_gl), digest) is True

        with pytest.raises(evidence.EvidenceError):
            evidence.seal([dict(finding)], str(Path(td) / "bad"), forge="gitea")


def test_glf03_forge_parity_drill_matches_across_seeded_corpus():
    """GLF-03: every seeded case runs a real gate and both forge paths agree."""
    corpus = seeded_corpus()
    assert len(corpus) == 5
    results = run_forge_parity_drill(corpus)
    assert len(results) == 5
    by_id = {r.case_id: r for r in results}
    assert by_id["corpus-01-unevidenced-marker"].passed is False
    assert by_id["corpus-01-unevidenced-marker"].rule_id == "evc"
    assert by_id["corpus-02-surface-divergence"].rule_id == "srch"
    assert by_id["corpus-03-aged-untriaged"].rule_id == "oia"
    assert by_id["corpus-04-scrubbed-not-revoked"].rule_id == "sr"
    assert by_id["corpus-05-clean-control"].passed is True
    assert by_id["corpus-05-clean-control"].exit_code == 0
    for result in results:
        assert (result.github_status.state == "success") == (
            result.gitlab_status.state == "success"
        )


def test_glf14_materialized_json_paths_remain_absolute_and_valid(tmp_path):
    """GLF-14: seed paths are JSON-safe on Windows and POSIX hosts."""
    seed = next(case for case in seeded_corpus() if case.case_id == "corpus-02-surface-divergence")
    root = (tmp_path / seed.case_id).resolve()
    _materialize(seed, root)
    surfaces = json.loads((root / "surfaces.json").read_text(encoding="utf-8"))
    paths = surfaces["groups"][0]["paths"]
    assert len(paths) == 2
    assert all(Path(path).is_absolute() for path in paths)
    assert all(Path(path).resolve().is_relative_to(root) for path in paths)


def test_glf14_materialized_json_escapes_quote_in_posix_root(tmp_path):
    """GLF-14: JSON-special characters in a legal POSIX root stay decodable."""
    import pytest

    if sys.platform == "win32":
        pytest.skip('Windows does not permit double quotes in path components')
    seed = next(case for case in seeded_corpus() if case.case_id == "corpus-02-surface-divergence")
    root = (tmp_path / 'fixture"root').resolve()
    _materialize(seed, root)
    surfaces = json.loads((root / "surfaces.json").read_text(encoding="utf-8"))
    paths = surfaces["groups"][0]["paths"]
    assert all(Path(path).is_absolute() for path in paths)
    assert all(Path(path).resolve().is_relative_to(root) for path in paths)


def test_glf10_and_glf13_instance_discovery_backup_drill_and_ownership():
    """GLF-10 & GLF-13: instance declaration, ownership rules, and backup/restore drill."""
    decl = InstanceDeclaration(
        instance_id="gitlab-ucs03",
        forge="gitlab",
        host_alias="ucs03",
        service_name="gitlab-ce",
        owner="platform-ops",
        backup_path="/var/opt/gitlab/backups",
        runner_scope="instance-dedicated",
        default_visibility="private",
        ip_repo_visibilities={"aiggp/core": "private", "aiggp/internal-tools": "internal"},
        tls_valid=True,
        security_patch_cadence_days=30,
        upgrade_cadence_days=90,
        supported_version="17.4",
        surface="self-hosted",
    )
    assert validate_instance_declaration(decl) == decl

    # Reject public visibility on IP repositories (GLF-13)
    bad_public = InstanceDeclaration(
        **{**decl.__dict__, "ip_repo_visibilities": {"aiggp/core": "public"}}
    )
    with pytest.raises(OwnershipValidationError, match="cannot have visibility 'public'"):
        validate_instance_declaration(bad_public)

    # Reject missing owner (GLF-13)
    bad_owner = InstanceDeclaration(**{**decl.__dict__, "owner": ""})
    with pytest.raises(OwnershipValidationError, match="missing designated owner"):
        validate_instance_declaration(bad_owner)

    # Backup and restore drill (GLF-10)
    drill = BackupDrillReport(
        instance_id="gitlab-ucs03",
        backup_archive_digest="sha256:" + "c" * 64,
        restored_commit_sha="d" * 40,
        expected_commit_sha="d" * 40,
        restored_mr_count=12,
        expected_mr_count=12,
        restored_variables_digest="sha256:" + "e" * 64,
        expected_variables_digest="sha256:" + "e" * 64,
    )
    assert validate_backup_restore_drill(drill) is True

    bad_drill = BackupDrillReport(**{**drill.__dict__, "restored_mr_count": 11})
    with pytest.raises(ValueError, match="merge request metadata count"):
        validate_backup_restore_drill(bad_drill)


def test_glf11_and_glf12_runner_enrollment_and_digest_pin(tmp_path):
    """GLF-11 & GLF-12: registry schema, runner-enroll.sh --forge gitlab, and digest pin."""
    pinned = "ghcr.io/aiggp/gitlab-runner@sha256:" + "f" * 64
    assert validate_runner_image_pin(pinned) == pinned
    for mutable in ("gitlab/gitlab-runner:latest", "gitlab/gitlab-runner:v17.4.0"):
        with pytest.raises(RunnerImageError):
            validate_runner_image_pin(mutable)

    reg_path = tmp_path / "runners.json"
    reg = Registry(str(reg_path))
    runner, _ = reg.enroll("gl-runner-1", "aiggp/core", ["devgate"], "ucs03", forge="gitlab")
    assert runner["forge"] == "gitlab"
    reg.save()
    schema = json.loads((REPO / "hub" / "schema" / "runners.schema.json").read_text(encoding="utf-8"))
    assert schemacheck.validate(json.loads(reg_path.read_text(encoding="utf-8")), schema) == []

    if sys.platform != "win32":
        s = Spoke(tmp_path)
        r = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                HUB,
                "enroll-tok",
                "--runner-name",
                "gl-alpha",
                "--repo",
                "aiggp/core",
                "--forge",
                "gitlab",
                "--runner-image",
                pinned,
            ],
            env=s.env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode == 0, r.stderr
        posts = s.requests("/enroll")
        assert json.loads(posts[-1]["data"])["forge"] == "gitlab"

        r_bad = subprocess.run(
            [
                "bash",
                str(SCRIPT),
                HUB,
                "enroll-tok",
                "--runner-name",
                "gl-beta",
                "--repo",
                "aiggp/core",
                "--forge",
                "gitlab",
                "--runner-image",
                "gitlab/gitlab-runner:latest",
            ],
            env=s.env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r_bad.returncode != 0
        assert "digest-pinned" in (r_bad.stdout + r_bad.stderr)
