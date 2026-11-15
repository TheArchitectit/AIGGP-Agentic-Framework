# // spec: GLF-01, GLF-02, GLF-03, GLF-10, GLF-13
"""Tests for deployer config, GitLab API walk, fleet declaration, monitoring,
and the pinned parity corpus. No live GitLab instance is contacted."""

from __future__ import annotations

import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from hub.forge import (  # noqa: E402
    BackupDrillReport,
    DeploymentConfigError,
    FleetDeclarationError,
    ForgeError,
    GitLabApiError,
    GitLabClient,
    OwnershipValidationError,
    audit_deployment,
    build_fleet_declaration,
    corpus_lock,
    get_forge_adapter,
    hosted_surface_enabled,
    load_instance_declarations,
    resolve_instance_adapter,
    verify_corpus_pin,
)
from hub.forge import parity  # noqa: E402

STUB_TOKEN = "devgate-local-stub-value"
SELF_HOSTED = """
version = 1

[[instance]]
instance_id = "lab-gitlab"
forge = "gitlab"
host_alias = "gitlab-lab.example.invalid"
service_name = "gitlab-ce"
owner = "platform-ops"
backup_path = "/var/opt/gitlab/backups"
runner_scope = "instance-dedicated"
default_visibility = "private"
tls_valid = true
security_patch_cadence_days = 30
upgrade_cadence_days = 90
supported_version = "17.4"
surface = "self-hosted"

[instance.ip_repo_visibilities]
"example-group/core" = "private"
"""


def write_config(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "instances.toml"
    path.write_text(body, encoding="utf-8")
    return path


def hosted_declaration() -> str:
    return (
        SELF_HOSTED.replace('"lab-gitlab"', '"gitlab.com"')
        .replace('"gitlab-lab.example.invalid"', '"gitlab.com"')
        .replace('"gitlab-ce"', '"gitlab.com"')
        .replace('surface = "self-hosted"', 'surface = "hosted"')
    )


def test_glf13_shipped_config_declares_nothing_and_refuses_undeclared():
    """GLF-13: a fresh deployment has no GitLab surface and says so by name."""
    declarations = load_instance_declarations()
    assert declarations == {}
    with pytest.raises(OwnershipValidationError, match="no ownership/cadence declaration"):
        resolve_instance_adapter("gitlab", "lab-gitlab", declarations)
    github = resolve_instance_adapter("github", None, declarations)
    assert github.forge_name == "github"


def test_glf13_declared_self_hosted_instance_resolves_and_hosted_stays_off(tmp_path):
    declarations = load_instance_declarations(write_config(tmp_path, SELF_HOSTED))
    assert sorted(declarations) == ["lab-gitlab"]
    adapter = resolve_instance_adapter("gitlab", "lab-gitlab", declarations)
    assert adapter.forge_name == "gitlab"
    assert hosted_surface_enabled(declarations) is False
    with pytest.raises(OwnershipValidationError, match="stays off unless declared"):
        resolve_instance_adapter("gitlab", "gitlab.com", declarations)


def test_glf13_gitlab_com_requires_an_explicit_hosted_declaration(tmp_path):
    mismatched = SELF_HOSTED.replace('"lab-gitlab"', '"gitlab.com"')
    with pytest.raises(DeploymentConfigError, match="surface='hosted' is reserved"):
        load_instance_declarations(write_config(tmp_path, mismatched))

    hosted = write_config(tmp_path, hosted_declaration())
    declarations = load_instance_declarations(hosted)
    assert declarations["gitlab.com"].surface == "hosted"
    assert hosted_surface_enabled(declarations) is True
    assert resolve_instance_adapter("gitlab", "gitlab.com", declarations).forge_name == "gitlab"


@pytest.mark.parametrize(
    "mutation",
    [
        SELF_HOSTED.replace("security_patch_cadence_days = 30", "security_patch_cadence_days = 0"),
        SELF_HOSTED.replace("security_patch_cadence_days = 30\n", ""),
        SELF_HOSTED.replace('supported_version = "17.4"', 'supported_version = "seventeen"'),
        SELF_HOSTED.replace("tls_valid = true", "unexpected_field = true"),
        SELF_HOSTED.replace('owner = "platform-ops"', 'owner = " "'),
    ],
)
def test_glf13_config_refuses_incomplete_or_unknown_declarations(tmp_path, mutation):
    with pytest.raises(DeploymentConfigError):
        load_instance_declarations(write_config(tmp_path, mutation))


class FakeWalkClient:
    def __init__(self, urls):
        self._urls = urls

    def project_urls(self):
        return list(self._urls)


def test_glf13_fleet_walk_merges_sources_and_refuses_undeclared(tmp_path):
    declarations = load_instance_declarations(write_config(tmp_path, SELF_HOSTED))
    clients = {
        "lab-gitlab": FakeWalkClient(
            [
                "https://gitlab.example.invalid/example-group/core/",
                "https://gitlab.example.invalid/example-group/core.git",
                "https://gitlab.example.invalid/example-group/tools",
            ]
        )
    }
    merged = build_fleet_declaration(
        ["https://github.com/example-org/framework"], declarations, clients
    )
    assert merged == [
        "https://github.com/example-org/framework",
        "https://gitlab.example.invalid/example-group/core",
        "https://gitlab.example.invalid/example-group/tools",
    ]

    with pytest.raises(FleetDeclarationError, match="undeclared GitLab instance"):
        build_fleet_declaration([], declarations, {"not-declared": FakeWalkClient([])})
    with pytest.raises(FleetDeclarationError, match="no walk client"):
        build_fleet_declaration(["https://github.com/example-org/framework"], declarations, {})
    with pytest.raises(FleetDeclarationError, match="empty"):
        build_fleet_declaration([], {}, {})


class _StubGitLab(BaseHTTPRequestHandler):
    seen_tokens: list[str] = []
    seen_pages: list[str] = []

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
        type(self).seen_tokens.append(self.headers.get("PRIVATE-TOKEN", ""))
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        page = (query.get("page") or ["1"])[0]
        type(self).seen_pages.append(page)
        if page == "1":
            payload = [
                {"web_url": "https://gitlab.example.invalid/g/alpha", "archived": False},
                {"web_url": "https://gitlab.example.invalid/g/beta", "archived": False},
            ]
            next_page = "2"
        else:
            payload = [
                {"web_url": "https://gitlab.example.invalid/g/old", "archived": True},
                {"web_url": "https://gitlab.example.invalid/g/gamma", "archived": False},
            ]
            next_page = ""
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if next_page:
            self.send_header("X-Next-Page", next_page)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        return


def test_glf02_api_walk_paginates_against_a_local_stub():
    _StubGitLab.seen_tokens = []
    _StubGitLab.seen_pages = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), _StubGitLab)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = GitLabClient(
            f"http://127.0.0.1:{server.server_address[1]}",
            STUB_TOKEN,
            allow_insecure=True,
            per_page=2,
        )
        assert client.project_urls() == [
            "https://gitlab.example.invalid/g/alpha",
            "https://gitlab.example.invalid/g/beta",
            "https://gitlab.example.invalid/g/gamma",
        ]
    finally:
        server.shutdown()
        thread.join(timeout=5)
    assert _StubGitLab.seen_pages == ["1", "2"]
    assert _StubGitLab.seen_tokens == [STUB_TOKEN, STUB_TOKEN]


def test_glf13_api_refuses_plain_http_and_credentials_in_url():
    with pytest.raises(GitLabApiError, match="plain HTTP"):
        GitLabClient("http://gitlab.example.invalid", STUB_TOKEN)
    with pytest.raises(GitLabApiError, match="must not carry credentials"):
        GitLabClient("https://user:pass@gitlab.example.invalid", STUB_TOKEN)
    with pytest.raises(GitLabApiError, match="absolute http"):
        GitLabClient("gitlab.example.invalid", STUB_TOKEN)


def test_glf10_monitor_audits_declarations_and_backup_drill(tmp_path):
    declarations = load_instance_declarations(write_config(tmp_path, SELF_HOSTED))
    drill = BackupDrillReport(
        instance_id="lab-gitlab",
        backup_archive_digest="sha256:" + "c" * 64,
        restored_commit_sha="d" * 40,
        expected_commit_sha="d" * 40,
        restored_mr_count=4,
        expected_mr_count=4,
        restored_variables_digest="sha256:" + "e" * 64,
        expected_variables_digest="sha256:" + "e" * 64,
    )
    green = audit_deployment(declarations, [drill])
    assert green["green"] is True
    assert green["hosted_surface_enabled"] is False

    missing_drill = audit_deployment(declarations)
    assert missing_drill["green"] is False
    assert any(f["rule"] == "GLF-10" for f in missing_drill["findings"])

    undeclared = audit_deployment(declarations, [drill], requested=["gitlab.com"])
    assert any(f["rule"] == "GLF-13" for f in undeclared["findings"])


def test_glf01_corpus_pin_is_current_and_drift_is_refused(tmp_path):
    assert verify_corpus_pin() == corpus_lock()
    mutated = parity.seeded_corpus()
    changed = list(mutated)
    first = changed[0]
    changed[0] = parity.GateSeed(
        case_id=first.case_id,
        category=first.category,
        files={"src/changed.py": "def run():\n    return 0\n"},
        commands=first.commands,
        expected_exit=first.expected_exit,
        expected_rule=first.expected_rule,
    )
    pin = tmp_path / "corpus.lock.json"
    pin.write_text(json.dumps(parity.corpus_lock(tuple(changed))), encoding="utf-8")
    with pytest.raises(parity.ParityDrillError, match="changed without a pin bump"):
        parity.verify_corpus_pin(pin)


def test_glf03_drill_detects_a_forge_conditional_normalization(monkeypatch):
    real = parity.normalize_findings

    def skewed(forge, seed, outcomes):
        findings = real(forge, seed, outcomes)
        if forge == "gitlab" and findings:
            findings = [dict(f, subject_locations=[]) for f in findings]
        return findings

    monkeypatch.setattr(parity, "normalize_findings", skewed)
    with pytest.raises(parity.ParityDivergence, match="finding sets differ by forge"):
        parity.run_forge_parity_drill()


def test_glf13_unknown_forge_still_fails_closed():
    with pytest.raises(ForgeError):
        get_forge_adapter("bitbucket")
