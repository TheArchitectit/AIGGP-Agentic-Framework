# // spec: fw-storage-01
"""Conformance tests for the storage-hygiene gate (fw-storage-01).

The gate has two halves and they fail differently, so they are pinned
separately.

The AUDIT half is configuration-reading, and configuration is where a bound
is easiest to lose quietly: a new upload step added without `retention-days:`
looks like any other step, and nothing downstream notices until storage
fills. Every fixture below is a real shape from this fleet -- an unbounded
upload, a bound above the declared maximum, and a bound that belongs to the
NEXT step (the adjacency failure an implementation that greps the whole file
would pass).

The TRIM half is a deletion policy, so the property that matters is what it
REFUSES to delete: an age-only rule removes the release evidence the policy
deliberately keeps. The newest-N-per-name exemption is therefore tested
directly, and the cache idle rule separately, because the two allowances are
separate pools (cache is not shared with artifacts).

Dual-runnable: pytest collects test_*; `python3 <this file>` runs them too.
No PyYAML: the repo is stdlib-only and a module-level `import yaml` in tests/
aborts collection for the whole suite.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest  # noqa: E402

from scripts import artifact_hygiene as ah  # noqa: E402

NOW = datetime(2026, 10, 20, 12, 0, 0, tzinfo=timezone.utc)


def _wf(tmp_path: Path, body: str) -> Path:
    d = tmp_path / ".github" / "workflows"
    d.mkdir(parents=True, exist_ok=True)
    (d / "ci.yml").write_text(body, encoding="utf-8")
    return tmp_path


UPLOAD = """name: CI
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
{steps}
"""


# --------------------------------------------------------------------------
# audit
# --------------------------------------------------------------------------

def test_unbounded_upload_is_a_finding(tmp_path):
    """The measured origin: an upload with no `retention-days:` is a future
    quota incident with a commit date on it."""
    steps = ("      - uses: actions/upload-artifact@aaa # v4\n"
             "        with:\n"
             "          name: x\n"
             "          path: out/\n")
    root = _wf(tmp_path, UPLOAD.format(steps=steps))
    findings = ah.audit(root, ah.DEFAULT_POLICY)
    assert len(findings) == 1
    assert "no retention-days bound" in findings[0]
    assert "ci.yml:7" in findings[0]


def test_bounded_upload_is_clean(tmp_path):
    steps = ("      - uses: actions/upload-artifact@aaa # v4\n"
             "        with:\n"
             "          name: x\n"
             "          path: out/\n"
             "          retention-days: 7\n")
    root = _wf(tmp_path, UPLOAD.format(steps=steps))
    assert ah.audit(root, ah.DEFAULT_POLICY) == []


def test_bound_above_the_declared_maximum_is_a_finding(tmp_path):
    """A bound is only a bound relative to the declared maximum. 91 days with
    max 90 is the same defect as no bound at all, one policy edit later."""
    steps = ("      - uses: actions/upload-artifact@aaa # v4\n"
             "        with:\n"
             "          name: x\n"
             "          retention-days: 91\n")
    root = _wf(tmp_path, UPLOAD.format(steps=steps))
    findings = ah.audit(root, {**ah.DEFAULT_POLICY, "max_retention_days": 90})
    assert len(findings) == 1
    assert "exceeds the declared maximum 90" in findings[0]


def test_bound_belongs_to_its_own_step_not_a_neighbour(tmp_path):
    """The adjacency failure. A checker that greps the whole file for
    `retention-days` passes this; a checker that scopes to the step fails it.
    Two uploads, one bounded, the second unbounded -- exactly one finding."""
    steps = ("      - uses: actions/upload-artifact@aaa # v4\n"
             "        with:\n"
             "          name: ok\n"
             "          retention-days: 7\n"
             "      - uses: actions/upload-artifact@bbb # v4\n"
             "        with:\n"
             "          name: not-ok\n"
             "          path: out/\n")
    root = _wf(tmp_path, UPLOAD.format(steps=steps))
    findings = ah.audit(root, ah.DEFAULT_POLICY)
    assert len(findings) == 1, findings
    assert "not-ok" not in findings[0]  # names the step by line, not by name
    assert "ci.yml:11" in findings[0]


def test_zero_workflow_files_is_a_finding_not_a_pass(tmp_path):
    """Non-vacuity: a scan that evaluated nothing must never read as green.
    This is the failure mode the gate exists to prevent, applied to itself."""
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    findings = ah.audit(tmp_path, ah.DEFAULT_POLICY)
    assert findings and "no workflow files" in findings[0]


def test_missing_workflow_dir_is_a_finding(tmp_path):
    findings = ah.audit(tmp_path, ah.DEFAULT_POLICY)
    assert findings and "nothing was scanned" in findings[0]


def test_zero_uploads_is_reported_not_hidden(tmp_path, capsys):
    """A repo with no uploads has no upload risk. Saying so explicitly is
    different from saying nothing, and the difference is auditable."""
    steps = "      - run: echo hi\n"
    root = _wf(tmp_path, UPLOAD.format(steps=steps))
    assert ah.audit(root, ah.DEFAULT_POLICY) == []
    out = capsys.readouterr().out
    assert "0 upload steps inspected" in out


def test_yaml_extension_is_also_scanned(tmp_path):
    d = tmp_path / ".github" / "workflows"
    d.mkdir(parents=True)
    (d / "rel.yaml").write_text(UPLOAD.format(
        steps="      - uses: actions/upload-artifact@a\n"), encoding="utf-8")
    findings = ah.audit(tmp_path, ah.DEFAULT_POLICY)
    assert len(findings) == 1 and "rel.yaml" in findings[0]


# --------------------------------------------------------------------------
# policy loading
# --------------------------------------------------------------------------

def test_malformed_policy_is_a_hard_error(tmp_path):
    """A policy that cannot be read must not make the gate LESS strict than
    the file asked for -- no silent fall-through to defaults."""
    (tmp_path / ".guardrails").mkdir()
    (tmp_path / ".guardrails" / "storage-policy.json").write_text(
        "{not json", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        ah.load_policy(tmp_path)
    assert e.value.code == ah.EXIT_USAGE


def test_missing_policy_uses_defaults(tmp_path):
    assert ah.load_policy(tmp_path) == ah.DEFAULT_POLICY


def test_non_integer_policy_value_is_rejected(tmp_path):
    (tmp_path / ".guardrails").mkdir()
    (tmp_path / ".guardrails" / "storage-policy.json").write_text(
        '{"trim_keep_days": "thirty"}', encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        ah.load_policy(tmp_path)
    assert e.value.code == ah.EXIT_USAGE


# --------------------------------------------------------------------------
# trim selection
# --------------------------------------------------------------------------

def _art(i: int, name: str, days: int, size: int = 100,
         expired: bool = False) -> dict:
    return {"id": i, "name": name, "size_in_bytes": size,
            "expired": expired,
            "created_at": (NOW - timedelta(days=days)).strftime(
                "%Y-%m-%dT%H:%M:%SZ")}


def test_old_artifacts_are_selected():
    """Two runs of one name, keep_latest=1: the fresh one is protected, the
    stale one goes."""
    arts = [_art(1, "report", 60), _art(2, "report", 2)]
    doomed = ah.select_artifacts(arts, keep_days=30, keep_latest=1, now=NOW)
    assert [a["id"] for a in doomed] == [1]


def test_fresh_artifacts_are_kept():
    arts = [_art(1, "report", 2)]
    assert ah.select_artifacts(arts, 30, 5, NOW) == []


def test_newest_per_name_survives_any_age():
    """The property that matters: an age-only rule deletes release evidence.
    Ten ancient nightly reports -- the newest two stay, the rest go, and the
    bound is per name, not per repo."""
    arts = [_art(i, "nightly", days=200 - i) for i in range(10)]
    doomed = ah.select_artifacts(arts, keep_days=30, keep_latest=2, now=NOW)
    kept = {a["id"] for a in arts} - {a["id"] for a in doomed}
    # id 9 is the most recent (191 days), id 8 the next; both beat the window.
    assert kept == {8, 9}, kept


def test_the_exemption_is_per_name_not_global():
    """A global 'keep newest N' would let one busy artifact name shield an
    unrelated stale one. Two names, keep_latest=1: each keeps its own newest."""
    arts = [_art(1, "alpha", 100), _art(2, "alpha", 1),
            _art(3, "beta", 100), _art(4, "beta", 1)]
    doomed = ah.select_artifacts(arts, keep_days=30, keep_latest=1, now=NOW)
    assert {a["id"] for a in doomed} == {1, 3}


def test_expired_artifact_is_selected_regardless_of_age():
    """Expiration already judged it dead, so it is deletable even when fresh;
    and it does not consume the newest-N budget, so it cannot shield the live
    sibling behind it."""
    arts = [_art(1, "report", 1, expired=True), _art(2, "report", 60),
            _art(3, "report", 61)]
    doomed = ah.select_artifacts(arts, keep_days=30, keep_latest=1, now=NOW)
    # id 2 (60d) is the newest LIVE run and stays; the expired id 1 and the
    # stale id 3 both go.
    assert {a["id"] for a in doomed} == {1, 3}


def test_keep_latest_zero_deletes_on_age_only():
    arts = [_art(1, "report", 60)]
    doomed = ah.select_artifacts(arts, keep_days=30, keep_latest=0, now=NOW)
    assert [a["id"] for a in doomed] == [1]


def test_newest_n_of_a_name_is_protected_even_when_stale():
    """With keep_latest=5 and a single old run, nothing is selected -- the
    newest five of a name are exempt from age by design. Stated as a test so
    the exemption is a decision, not a surprise."""
    arts = [_art(1, "report", 400)]
    assert ah.select_artifacts(arts, keep_days=30, keep_latest=5, now=NOW) == []


def test_cache_idle_rule_is_separate():
    """Cache storage is a separate allowance from artifacts, so it is a
    separate rule with a separate threshold."""
    old = (NOW - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    fresh = (NOW - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    caches = [{"id": 1, "key": "go", "last_accessed_at": old},
              {"id": 2, "key": "pnpm", "last_accessed_at": fresh}]
    doomed = ah.select_caches(caches, idle_days=14, now=NOW)
    assert [c["id"] for c in doomed] == [1]


def test_cache_falls_back_to_created_at():
    old = (NOW - timedelta(days=40)).strftime("%Y-%m-%dT%H:%M:%SZ")
    caches = [{"id": 1, "key": "k", "last_accessed_at": None,
               "created_at": old}]
    assert [c["id"] for c in ah.select_caches(caches, 14, NOW)] == [1]


def test_trim_dry_run_never_deletes(tmp_path, monkeypatch, capsys):
    """Default is a dry run. A gate that deletes by accident is worse than
    the quota it fixes."""
    calls: list[str] = []

    def fake_api(url, token, method="GET"):
        calls.append(method)
        if "/artifacts?" in url:
            return 200, {"artifacts": [_art(1, "report", 90),
                                       _art(2, "report", 91)]}
        if "/caches?" in url:
            return 200, {"actions_caches": []}
        raise AssertionError(f"unexpected call {method} {url}")

    monkeypatch.setattr(ah, "_api", fake_api)
    pol = {**ah.DEFAULT_POLICY, "trim_keep_latest": 1}
    assert ah.trim("o/r", "tok", pol, apply=False) == ah.EXIT_OK
    assert calls == ["GET", "GET"], calls
    # _art's third argument is AGE, so id 1 (90d) is the newer of the two and
    # is the newest-1 that survives; id 2 (91d) is the one past the window.
    assert "would delete artifact 2" in capsys.readouterr().out


def test_trim_apply_deletes_and_counts(tmp_path, monkeypatch):
    calls: list[tuple[str, str]] = []

    def fake_api(url, token, method="GET"):
        calls.append((method, url))
        if "/artifacts?" in url:
            return 200, {"artifacts": [_art(1, "report", 90),
                                       _art(2, "report", 91)]}
        if "/caches?" in url:
            return 200, {"actions_caches": []}
        return 204, {}

    monkeypatch.setattr(ah, "_api", fake_api)
    pol = {**ah.DEFAULT_POLICY, "trim_keep_latest": 1}
    assert ah.trim("o/r", "tok", pol, apply=True) == ah.EXIT_OK
    assert ("DELETE", "https://api.github.com/repos/o/r/actions/artifacts/2") \
        in calls


def test_trim_api_failure_is_fail_closed(monkeypatch, capsys):
    monkeypatch.setattr(ah, "_api", lambda u, t, m="GET": (404, {"e": 1}))
    assert ah.trim("o/r", "tok", ah.DEFAULT_POLICY, apply=False) \
        == ah.EXIT_FINDINGS
    assert "FAIL" in capsys.readouterr().err


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------

def test_cli_requires_a_mode(capsys):
    with pytest.raises(SystemExit) as e:
        ah.main(["--repo", "."])
    assert e.value.code == 2


def test_cli_trim_without_slug_is_usage_error(monkeypatch, tmp_path):
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    rc = ah.main(["--repo", str(tmp_path), "--trim"])
    assert rc == ah.EXIT_USAGE


def test_cli_audit_on_the_real_repo_passes():
    """The repository must satisfy its own gate -- the standard this repo
    applies to consumers first."""
    repo = Path(__file__).resolve().parent.parent
    assert ah.audit(repo, ah.load_policy(repo)) == []


def main() -> int:
    sys.exit(pytest.main([__file__, "-v"]))


if __name__ == "__main__":
    main()
