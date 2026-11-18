#!/usr/bin/env python3
"""Tests for scripts/fleet-app-enroll.py (automatic fleet App enrollment).

Every test uses an in-memory fake GitHub API: no network, no real credential,
and no repository outside the test's own temporary directory. The PEM used by
the sealing tests is assembled at run time and never resembles a real key.

Dual-runnable: pytest collects test_*; PyNaCl is needed only where a secret is
actually sealed, so the read/plan tests still run on a bare interpreter.
"""
import base64
import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "fleet-app-enroll.py"
WORKFLOW = HERE.parent / ".github" / "workflows" / "fleet-app-enroll.yml"

sys.path.insert(0, str(HERE))

import workflow_read as wr  # noqa: E402

try:  # sealing tests are skipped, not red, when the dependency is absent
    from nacl.encoding import Base64Encoder
    from nacl.public import PrivateKey, SealedBox
except ImportError:  # pragma: no cover - environment guard
    PrivateKey = None
    SealedBox = None
    Base64Encoder = None

needs_nacl = pytest.mark.skipif(PrivateKey is None, reason="PyNaCl not installed")

APP_ID = "123456"
TOKEN = "dummy-token-not-a-credential"


def _load_script():
    spec = importlib.util.spec_from_file_location("fleet_app_enroll", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # dataclasses (3.14) resolve annotations through sys.modules.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


enroll = _load_script()


def dummy_pem():
    """A PEM-SHAPED string assembled at run time; not a key, not a literal."""
    dashes = "-" * 5
    begin = dashes + "BEGIN " + "PRIVATE" + " " + "KEY" + dashes
    end = dashes + "END " + "PRIVATE" + " " + "KEY" + dashes
    body = "ZmFrZS10ZXN0LW9ubHktcGF5bG9hZA=="
    return f"{begin}\n{body}\n{end}\n"


def base_env(**overrides):
    env = {
        "FLEET_APP_ID": APP_ID,
        "FLEET_APP_TOKEN": TOKEN,
        "FLEET_APP_PRIVATE_KEY": dummy_pem(),
        "FLEET_OWNER": "TheArchitectit",
    }
    env.update(overrides)
    return env


def repo(name, *, archived=False, owner=None, private=False, fork=False):
    login = owner or name.split("/", 1)[0]
    return {"full_name": name, "owner": {"login": login},
            "archived": archived, "private": private, "fork": fork}


def _keypair():
    private = PrivateKey.generate()
    return private, private.public_key.encode(Base64Encoder).decode()


class FakeGitHub:
    """An in-memory GitHub API. Transport only; no sockets."""

    def __init__(self, repos, *, variables=None, secrets=None, page_size=None,
                 failures=None, public_key_b64=None):
        self.repos = list(repos)
        self.variables = dict(variables or {})
        self.secrets = set(secrets or ())
        self.page_size = page_size
        self.failures = list(failures or ())
        self.public_key_b64 = public_key_b64 or base64.b64encode(
            bytes(range(32))).decode()
        self.calls = []
        self.writes = []
        self.secret_puts = []

    def _repo(self, full_name):
        for candidate in self.repos:
            if candidate["full_name"] == full_name:
                return candidate
        return None

    def _page(self, parts):
        page = int(parse_qs(parts.query).get("page", ["1"])[0])
        size = self.page_size or len(self.repos) or 1
        start = (page - 1) * size
        chunk = self.repos[start:start + size]
        headers = {}
        if start + size < len(self.repos):
            next_url = (f"{enroll.API_ROOT}/installation/repositories"
                        f"?per_page={enroll.PER_PAGE}&page={page + 1}")
            headers["Link"] = f'<{next_url}>; rel="next"'
        body = json.dumps({"total_count": len(self.repos),
                           "repositories": chunk}).encode()
        return 200, headers, body

    def transport(self, method, url, headers, body, timeout):
        parts = urlsplit(url)
        path = parts.path
        self.calls.append((method, path))
        for failure_method, marker, status in self.failures:
            if failure_method == method and marker in path:
                return status, {}, b""
        if method == "GET" and path == "/installation/repositories":
            return self._page(parts)
        if method == "GET" and re.fullmatch(r"/repos/[^/]+/[^/]+", path):
            found = self._repo(path[len("/repos/"):])
            if found is None:
                return 404, {}, b""
            return 200, {}, json.dumps(found).encode()
        prefix = r"/repos/([^/]+/[^/]+)/actions"
        match = re.fullmatch(
            prefix + r"/variables/" + re.escape(enroll.VARIABLE_NAME), path)
        if match:
            full_name = match.group(1)
            if method == "GET":
                if full_name in self.variables:
                    doc = {"name": enroll.VARIABLE_NAME,
                           "value": self.variables[full_name]}
                    return 200, {}, json.dumps(doc).encode()
                return 404, {}, b""
            if method == "PATCH":
                doc = json.loads(body.decode())
                self.variables[full_name] = doc["value"]
                self.writes.append((method, path, doc))
                return 204, {}, b""
        match = re.fullmatch(prefix + r"/variables", path)
        if match and method == "POST":
            full_name = match.group(1)
            doc = json.loads(body.decode())
            self.variables[full_name] = doc["value"]
            self.writes.append((method, path, doc))
            return 201, {}, b""
        match = re.fullmatch(prefix + r"/secrets/public-key", path)
        if match and method == "GET":
            doc = {"key_id": "test-key-id", "key": self.public_key_b64}
            return 200, {}, json.dumps(doc).encode()
        match = re.fullmatch(
            prefix + r"/secrets/" + re.escape(enroll.SECRET_NAME), path)
        if match:
            full_name = match.group(1)
            if method == "GET":
                if full_name in self.secrets:
                    return 200, {}, json.dumps(
                        {"name": enroll.SECRET_NAME}).encode()
                return 404, {}, b""
            if method == "PUT":
                doc = json.loads(body.decode())
                self.secrets.add(full_name)
                self.secret_puts.append((full_name, doc))
                self.writes.append((method, path, doc))
                return 201, {}, b""
        return 500, {}, b""


def _api(fake):
    return enroll.GitHubAPI("dummy-token", transport=fake.transport, timeout=5)


def invoke(tmp_path, fake, *flags, env=None):
    report_path = tmp_path / "report.json"
    rc = enroll.run(["--report", str(report_path), *flags],
                    api=_api(fake), env=env or base_env())
    report = None
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
    return rc, report


def test_installation_repositories_paginate_with_link_headers(tmp_path):
    names = [f"TheArchitectit/repo{i}" for i in range(3)]
    fake = FakeGitHub([repo(name) for name in names], page_size=2,
                      variables={name: APP_ID for name in names},
                      secrets=set(names))
    rc, report = invoke(tmp_path, fake)
    assert rc == 0
    listing = [call for call in fake.calls
               if call[1] == "/installation/repositories"]
    assert len(listing) == 2, "the second page must be fetched from rel=next"
    assert report["counts"]["repos"] == 3
    assert report["counts"]["processed"] == 3
    assert report["counts"]["failed"] == 0
    for name in names:
        assert [call for call in fake.calls if name in call[1]], name


def test_archived_repositories_are_skipped_and_counted(tmp_path):
    live = "TheArchitectit/live"
    old = "TheArchitectit/old"
    fake = FakeGitHub([repo(live), repo(old, archived=True)],
                      variables={live: APP_ID}, secrets={live})
    rc, report = invoke(tmp_path, fake)
    assert rc == 0
    assert report["counts"]["archived_skipped"] == 1
    assert report["counts"]["processed"] == 1
    assert not [call for call in fake.calls if old in call[1]]
    record = [item for item in report["repos"] if item["name"] == old][0]
    assert record["actions"] == ["skipped-archived"]


def test_variable_is_created_updated_or_left_alone(tmp_path):
    absent = "TheArchitectit/absent"
    wrong = "TheArchitectit/wrong"
    right = "TheArchitectit/right"
    fake = FakeGitHub([repo(absent), repo(wrong), repo(right)],
                      variables={wrong: "999", right: APP_ID},
                      secrets={absent, wrong, right})
    rc, report = invoke(tmp_path, fake)
    assert rc == 0
    assert fake.variables[absent] == APP_ID
    assert fake.variables[wrong] == APP_ID
    writes = {(method, path) for method, path, _body in fake.writes}
    assert ("POST", f"/repos/{absent}/actions/variables") in writes
    assert ("PATCH",
            f"/repos/{wrong}/actions/variables/{enroll.VARIABLE_NAME}") in writes
    assert not [write for write in fake.writes if right in write[1]]
    actions = {item["name"]: item["actions"] for item in report["repos"]}
    assert "variable-created" in actions[absent]
    assert "variable-updated" in actions[wrong]
    assert "variable-unchanged" in actions[right]


@needs_nacl
def test_secret_is_created_only_when_absent_and_is_sealed(tmp_path):
    private, public = _keypair()
    absent = "TheArchitectit/needs-secret"
    present = "TheArchitectit/has-secret"
    fake = FakeGitHub([repo(absent), repo(present)],
                      variables={absent: APP_ID, present: APP_ID},
                      secrets={present}, public_key_b64=public)
    rc, report = invoke(tmp_path, fake)
    assert rc == 0
    assert [name for name, _doc in fake.secret_puts] == [absent]
    put_doc = fake.secret_puts[0][1]
    assert put_doc["key_id"] == "test-key-id"
    pem = base_env()["FLEET_APP_PRIVATE_KEY"]
    ciphertext = put_doc["encrypted_value"]
    assert ciphertext != pem
    plain = SealedBox(private).decrypt(base64.b64decode(ciphertext))
    assert plain.decode() == pem
    assert not [call for call in fake.calls
                if present in call[1] and "public-key" in call[1]]
    actions = {item["name"]: item["actions"] for item in report["repos"]}
    assert "secret-created" in actions[absent]
    assert "secret-unchanged" in actions[present]


@needs_nacl
def test_rotate_reseals_an_existing_secret(tmp_path):
    private, public = _keypair()
    name = "TheArchitectit/rotate-me"
    fake = FakeGitHub([repo(name)], variables={name: APP_ID},
                      secrets={name}, public_key_b64=public)
    rc, _report = invoke(tmp_path, fake)
    assert rc == 0
    assert fake.secret_puts == [], "an existing secret is not replaced by default"

    rotated = FakeGitHub([repo(name)], variables={name: APP_ID},
                         secrets={name}, public_key_b64=public)
    rc, report = invoke(tmp_path, rotated, "--rotate")
    assert rc == 0
    assert len(rotated.secret_puts) == 1
    ciphertext = rotated.secret_puts[0][1]["encrypted_value"]
    plain = SealedBox(private).decrypt(base64.b64decode(ciphertext))
    assert plain.decode() == base_env()["FLEET_APP_PRIVATE_KEY"]
    assert "secret-rotated" in report["repos"][0]["actions"]


def test_dry_run_performs_no_writes(tmp_path):
    name = "TheArchitectit/unconfigured"
    fake = FakeGitHub([repo(name)])
    rc, report = invoke(tmp_path, fake, "--dry-run")
    assert rc == 0
    assert fake.writes == []
    assert report["mode"] == "dry-run"
    assert report["repos"][0]["actions"] == [
        "variable-create-planned", "secret-create-planned"]


def test_one_repo_error_does_not_stop_the_others_and_exits_nonzero(tmp_path):
    broken = "TheArchitectit/broken"
    healthy = "TheArchitectit/healthy"
    fake = FakeGitHub(
        [repo(broken), repo(healthy)],
        variables={healthy: APP_ID}, secrets={broken, healthy},
        failures=[("GET", f"/repos/{broken}/actions/variables/", 500)])
    rc, report = invoke(tmp_path, fake)
    assert rc == 1
    assert report["counts"]["failed"] == 1
    records = {item["name"]: item for item in report["repos"]}
    assert records[broken]["errors"]
    assert records[healthy]["errors"] == []
    assert "secret-unchanged" in records[healthy]["actions"]


@needs_nacl
def test_credentials_never_reach_stdout_or_the_report(tmp_path, capsys):
    _private, public = _keypair()
    name = "TheArchitectit/needs-secret"
    fake = FakeGitHub([repo(name)], public_key_b64=public)
    pem = dummy_pem()
    rc, _report = invoke(tmp_path, fake, env=base_env(
        FLEET_APP_PRIVATE_KEY=pem, FLEET_APP_TOKEN=TOKEN))
    assert rc == 0
    captured = capsys.readouterr()
    report_text = (tmp_path / "report.json").read_text(encoding="utf-8")
    body_line = pem.splitlines()[1]
    for text in (captured.out, captured.err, report_text):
        assert pem not in text
        assert body_line not in text
        assert TOKEN not in text


def test_missing_token_is_a_usage_error_and_writes_nothing(tmp_path):
    report_path = tmp_path / "report.json"
    rc = enroll.run(["--report", str(report_path)],
                    api=_api(FakeGitHub([])),
                    env=base_env(FLEET_APP_TOKEN=""))
    assert rc == 2
    assert not report_path.exists()


def test_report_is_pure_json_on_stdout_when_no_path_is_given(capsys):
    name = "TheArchitectit/quiet"
    fake = FakeGitHub([repo(name)], variables={name: APP_ID}, secrets={name})
    rc = enroll.run([], api=_api(fake), env=base_env())
    captured = capsys.readouterr()
    assert rc == 0
    report = json.loads(captured.out)
    assert report["counts"]["repos"] == 1
    assert "[enroll]" in captured.err, "progress lines stay off stdout"


def test_repo_flag_limits_scope_and_skips_the_listing(tmp_path):
    inside = "TheArchitectit/inside"
    outside = "TheArchitectit/outside"
    fake = FakeGitHub([repo(inside), repo(outside)],
                      variables={inside: APP_ID, outside: APP_ID},
                      secrets={inside, outside})
    rc, report = invoke(tmp_path, fake, "--repo", inside)
    assert rc == 0
    assert report["counts"]["repos"] == 1
    assert not [call for call in fake.calls if outside in call[1]]
    assert not [call for call in fake.calls
                if call[1] == "/installation/repositories"]


def test_repositories_outside_the_owner_scope_are_counted_not_touched(tmp_path):
    ours = "TheArchitectit/ours"
    theirs = "someone-else/theirs"
    fake = FakeGitHub([repo(ours), repo(theirs)],
                      variables={ours: APP_ID, theirs: APP_ID},
                      secrets={ours, theirs})
    rc, report = invoke(tmp_path, fake)
    assert rc == 0
    assert report["counts"]["other_owner_skipped"] == 1
    assert not [call for call in fake.calls if theirs in call[1]]


def _workflow():
    return wr.read_workflow(WORKFLOW.read_text(encoding="utf-8"))


def test_workflow_has_no_pull_request_trigger_and_a_safe_dispatch_default():
    workflow = _workflow()
    assert set(workflow.triggers) == {"schedule", "workflow_dispatch"}
    dry_run_input = workflow.dispatch_input("dry_run")
    assert dry_run_input["type"] == "boolean"
    assert str(dry_run_input["default"]).lower() == "true"


def test_workflow_runs_nightly_on_devgate_off_the_hour():
    workflow = _workflow()
    schedule = workflow.triggers["schedule"]
    assert isinstance(schedule, list) and schedule
    cron = schedule[0]["cron"]
    minute = cron.split()[0]
    assert minute not in {"0", "30"}, cron
    job = workflow.jobs["enroll"]
    assert job["runs-on"] == "devgate"
    assert str(job["timeout-minutes"]) == "45"
    assert "concurrency" in workflow.tree


def test_workflow_keeps_the_private_key_in_env_and_pins_actions():
    text = WORKFLOW.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "run:" in line and "DEVGATE_SWEEP_APP_PRIVATE_KEY" in line:
            raise AssertionError(f"private key referenced in a run line: {line}")
    assert ("FLEET_APP_PRIVATE_KEY: "
            "${{ secrets.DEVGATE_SWEEP_APP_PRIVATE_KEY }}") in text
    assert ("actions/create-github-app-token@"
            "fee1f7d63c2ff003460e3d139729b119787bc349") in text
    assert ("actions/upload-artifact@"
            "ea165f8d65b6e75b540449e92b4886f43607fa02") in text
    assert "PyNaCl==1.5.0" in text
