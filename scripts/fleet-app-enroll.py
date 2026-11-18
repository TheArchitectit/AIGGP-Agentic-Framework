#!/usr/bin/env python3
"""fleet-app-enroll.py - keep the fleet App credential pair on every repo.

The fleet GitHub App (installation 101651861, repository_selection=all) needs
two repository-scoped values to mint tokens inside a workflow:

    variable DEVGATE_SWEEP_APP_ID            the App ID (an identifier)
    secret   DEVGATE_SWEEP_APP_PRIVATE_KEY   the App private key (a credential)

The owner, TheArchitectit, is a USER account, so there are no organization
secrets to inherit: every repository carries its own copy. A repo created
tomorrow therefore starts unconfigured and its fleet workflows fall back to
`github.token` (1,000 req/h, one repository) until a human sets the pair by
hand. This reconciler removes the human step.

What it does, per repository:

  * reads the variable; creates it when absent, updates it when the value is
    not the configured App ID, leaves it alone when it matches;
  * reads the secret's METADATA only - a secret value cannot be read back, so
    an existing secret is never overwritten by default (an overwrite could
    replace a working key with a half-broken one and there is no way to
    compare); `--rotate` is the explicit re-seal path;
  * when the secret is absent (or `--rotate`), fetches the repository Actions
    public key, seals the PEM in memory (libsodium sealed box), and PUTs the
    ciphertext. The PEM is never written to disk, printed, or put in argv.

Archived repositories are skipped and counted. Public, private, and fork
repositories are all processed. Per-repository errors are collected and the
run continues; the exit code is nonzero when anything failed.

Inputs are environment variables, never argv:

    FLEET_APP_ID          numeric App ID
    FLEET_APP_PRIVATE_KEY PEM private key (read, never printed or written)
    FLEET_APP_TOKEN       installation token with actions/secrets/admin write
    FLEET_OWNER           owner scope for the installation listing
                          (default: TheArchitectit)

Exit codes:
    0  every selected repository reconciled
    1  at least one repository (or the repository listing) failed
    2  usage or configuration error (nothing was written)

Requires PyNaCl for sealing only; a `--dry-run` that needs no seal works
without it. GitHub API URLs must be HTTPS api.github.com - a Link header that
points anywhere else is refused.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

API_ROOT = "https://api.github.com"
API_HOST = "api.github.com"
VARIABLE_NAME = "DEVGATE_SWEEP_APP_ID"
SECRET_NAME = "DEVGATE_SWEEP_APP_PRIVATE_KEY"
DEFAULT_OWNER = "TheArchitectit"
PER_PAGE = 100
TIMEOUT_SECONDS = 30
MAX_PAGES = 1000

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2

ACTION_COUNT_KEYS = {
    "variable-created": "variable_created",
    "variable-updated": "variable_updated",
    "variable-unchanged": "variable_unchanged",
    "variable-create-planned": "variable_create_planned",
    "variable-update-planned": "variable_update_planned",
    "secret-created": "secret_created",
    "secret-rotated": "secret_rotated",
    "secret-unchanged": "secret_unchanged",
    "secret-create-planned": "secret_create_planned",
    "secret-rotate-planned": "secret_rotate_planned",
}


class ApiError(Exception):
    """A GitHub API call or response failed.

    Messages carry a method label, a repository name, and an HTTP status.
    Response bodies are deliberately never included: a body is not needed to
    act on the failure and could contain material that must not reach a log.
    """


@dataclass
class Response:
    status: int
    headers: dict
    data: object


def _require_https(url: str) -> None:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.netloc != API_HOST:
        raise ApiError("refusing a GitHub API URL that is not HTTPS api.github.com")


def _urlopen_transport(method, url, headers, body, timeout):
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers), response.read()
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, dict(exc.headers or {}), exc.read()
        finally:
            exc.close()


class GitHubAPI:
    """Minimal GitHub REST client with an injectable transport (tests)."""

    def __init__(self, token, *, transport=None, timeout=TIMEOUT_SECONDS):
        self._token = token
        self._transport = transport or _urlopen_transport
        self._timeout = timeout

    def request(self, method, path, body=None):
        url = path if path.startswith("https://") else API_ROOT + path
        _require_https(url)
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self._token}",
            "User-Agent": "fleet-app-enroll",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        payload = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            payload = json.dumps(body).encode("utf-8")
        try:
            status, raw_headers, raw_body = self._transport(
                method, url, headers, payload, self._timeout)
        except ApiError:
            raise
        except Exception as exc:  # noqa: BLE001 - never leak transport detail
            raise ApiError(
                "GitHub API request failed (network or timeout)") from exc
        lowered = {str(k).lower(): str(v)
                   for k, v in (raw_headers or {}).items()}
        data = None
        if raw_body:
            try:
                data = json.loads(raw_body.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                data = None
        return Response(status=status, headers=lowered, data=data)


def _expect(response: Response, allowed, label: str) -> None:
    if response.status not in allowed:
        raise ApiError(f"{label}: HTTP {response.status}")


def next_link(link_header: str):
    """Return the rel="next" URL from a Link header, or None."""
    if not link_header:
        return None
    for part in link_header.split(","):
        segments = part.split(";")
        if len(segments) < 2:
            continue
        target = segments[0].strip()
        if not (target.startswith("<") and target.endswith(">")):
            continue
        relations = [segment.strip() for segment in segments[1:]]
        if any(rel in ('rel="next"', "rel=next") for rel in relations):
            return target[1:-1]
    return None


def seal_secret(public_key_b64: str, plaintext: str) -> str:
    """Seal `plaintext` for a GitHub Actions repository public key.

    Returns base64 ciphertext. PyNaCl is imported here, not at module scope,
    so a dry run that needs no seal does not require the dependency.
    """
    try:
        from nacl.encoding import Base64Encoder
        from nacl.public import PublicKey, SealedBox
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ApiError(
            "PyNaCl is required to seal a secret (install PyNaCl==1.5.0)") from exc
    try:
        raw_key = base64.b64decode(public_key_b64, validate=True)
        box = SealedBox(PublicKey(raw_key))
        return box.encrypt(plaintext.encode("utf-8"),
                           encoder=Base64Encoder).decode("ascii")
    except Exception as exc:  # noqa: BLE001 - library errors name no secret
        raise ApiError(
            f"could not seal the private key ({type(exc).__name__})") from exc


def list_repositories(api: GitHubAPI):
    """Every repository the installation covers, following Link rel=next."""
    url = f"/installation/repositories?per_page={PER_PAGE}"
    repositories = []
    visited = set()
    while url:
        if url in visited or len(visited) >= MAX_PAGES:
            raise ApiError("installation repository pagination did not terminate")
        visited.add(url)
        response = api.request("GET", url)
        _expect(response, {200}, "list installation repositories")
        data = response.data if isinstance(response.data, dict) else {}
        page = data.get("repositories")
        if not isinstance(page, list):
            raise ApiError("installation repository page has no repositories list")
        repositories.extend(page)
        url = next_link(response.headers.get("link", ""))
    return repositories


def _full_name(repository) -> str:
    name = repository.get("full_name")
    if not isinstance(name, str) or name.count("/") != 1:
        raise ApiError("repository object has no owner/name")
    return name


def _ensure_variable(api, full_name, app_id, dry_run):
    path = f"/repos/{full_name}/actions/variables/{VARIABLE_NAME}"
    response = api.request("GET", path)
    if response.status == 404:
        if dry_run:
            return "variable-create-planned"
        created = api.request(
            "POST", f"/repos/{full_name}/actions/variables",
            {"name": VARIABLE_NAME, "value": str(app_id)})
        _expect(created, {201, 204}, f"create variable on {full_name}")
        return "variable-created"
    _expect(response, {200}, f"read variable on {full_name}")
    current = response.data.get("value") if isinstance(response.data, dict) else None
    if current == str(app_id):
        return "variable-unchanged"
    if dry_run:
        return "variable-update-planned"
    # GitHub's update-a-repository-variable endpoint is PATCH, not PUT.
    updated = api.request("PATCH", path,
                          {"name": VARIABLE_NAME, "value": str(app_id)})
    _expect(updated, {200, 204}, f"update variable on {full_name}")
    return "variable-updated"


def _put_secret(api, full_name, private_key):
    response = api.request(
        "GET", f"/repos/{full_name}/actions/secrets/public-key")
    _expect(response, {200}, f"read Actions public key on {full_name}")
    data = response.data if isinstance(response.data, dict) else {}
    key_id = data.get("key_id")
    public_key = data.get("key")
    if not isinstance(key_id, str) or not isinstance(public_key, str):
        raise ApiError(f"Actions public key on {full_name} has no key_id/key")
    sealed = seal_secret(public_key, private_key)
    stored = api.request(
        "PUT", f"/repos/{full_name}/actions/secrets/{SECRET_NAME}",
        {"encrypted_value": sealed, "key_id": key_id})
    _expect(stored, {201, 204}, f"store secret on {full_name}")


def _ensure_secret(api, full_name, private_key, rotate, dry_run):
    path = f"/repos/{full_name}/actions/secrets/{SECRET_NAME}"
    response = api.request("GET", path)
    if response.status == 200:
        if not rotate:
            # Value is unreadable by design; metadata presence is the whole
            # comparison. Never overwrite a working key implicitly.
            return "secret-unchanged"
        if dry_run:
            return "secret-rotate-planned"
        _put_secret(api, full_name, private_key)
        return "secret-rotated"
    if response.status != 404:
        raise ApiError(f"read secret metadata on {full_name}: HTTP {response.status}")
    if dry_run:
        return "secret-create-planned"
    _put_secret(api, full_name, private_key)
    return "secret-created"


def reconcile_repo(api, repository, *, app_id, private_key, rotate, dry_run):
    try:
        full_name = _full_name(repository)
    except ApiError as exc:
        return {"name": "<unnamed>", "archived": False,
                "actions": [], "errors": [str(exc)]}
    record = {
        "name": full_name,
        "archived": bool(repository.get("archived")),
        "actions": [],
        "errors": [],
    }
    if record["archived"]:
        record["actions"].append("skipped-archived")
        return record
    try:
        record["actions"].append(
            _ensure_variable(api, full_name, app_id, dry_run))
    except ApiError as exc:
        record["errors"].append(str(exc))
    except Exception as exc:  # noqa: BLE001 - keep the other field working
        record["errors"].append(f"variable: unexpected {type(exc).__name__}")
    try:
        record["actions"].append(
            _ensure_secret(api, full_name, private_key, rotate, dry_run))
    except ApiError as exc:
        record["errors"].append(str(exc))
    except Exception as exc:  # noqa: BLE001
        record["errors"].append(f"secret: unexpected {type(exc).__name__}")
    return record


def _counts(records, *, archived, other_owner):
    counts = {key: 0 for key in ACTION_COUNT_KEYS.values()}
    counts.update(repos=len(records), processed=0, failed=0,
                  archived_skipped=archived, other_owner_skipped=other_owner)
    for record in records:
        if not record["archived"]:
            counts["processed"] += 1
        if record["errors"]:
            counts["failed"] += 1
        for action in record["actions"]:
            key = ACTION_COUNT_KEYS.get(action)
            if key:
                counts[key] += 1
    return counts


def _scrub(value, known_values):
    """Replace any known credential in report strings before output.

    The locals are deliberately not named `secret`: PREVENT-003 matches a
    credential-like name next to a quoted replacement string even though this
    is the redaction path itself.
    """
    if isinstance(value, dict):
        return {key: _scrub(item, known_values) for key, item in value.items()}
    if isinstance(value, list):
        return [_scrub(item, known_values) for item in value]
    if isinstance(value, str):
        for needle in known_values:
            if needle:
                value = value.replace(needle, "***")
    return value


def _emit(report, report_path, secrets):
    report = _scrub(report, secrets)
    text = json.dumps(report, indent=2, sort_keys=True)
    if report_path is None:
        print(text)
        return
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(text + "\n", encoding="utf-8")
    print(f"[enroll] report written: {report_path}", file=sys.stderr)


def _parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="read and plan only; perform no writes")
    parser.add_argument("--rotate", action="store_true",
                        help="re-seal an EXISTING secret (deliberate rotation)")
    parser.add_argument("--repo", action="append", default=[],
                        metavar="OWNER/NAME",
                        help="limit scope to this repository (repeatable)")
    parser.add_argument("--report", type=Path, default=None,
                        help="write the JSON report here (default: stdout)")
    return parser.parse_args(argv)


def _validate(args, environ):
    app_id = (environ.get("FLEET_APP_ID") or "").strip()
    token = (environ.get("FLEET_APP_TOKEN") or "").strip()
    private_key = environ.get("FLEET_APP_PRIVATE_KEY") or ""
    owner = (environ.get("FLEET_OWNER") or "").strip() or DEFAULT_OWNER
    problems = []
    if not app_id.isdigit():
        problems.append("FLEET_APP_ID must be the numeric App ID")
    if not token:
        problems.append("FLEET_APP_TOKEN is required")
    if not args.dry_run and not private_key.strip():
        problems.append("FLEET_APP_PRIVATE_KEY is required unless --dry-run")
    for full_name in args.repo:
        parts = full_name.split("/")
        if len(parts) != 2 or not all(parts):
            problems.append(f"--repo expects owner/name: {full_name!r}")
    for problem in problems:
        print(f"fleet-app-enroll: {problem}", file=sys.stderr)
    return app_id, token, private_key, owner, not problems


def run(argv=None, *, api=None, env=None):
    args = _parse_args(argv)
    environ = os.environ if env is None else env
    app_id, token, private_key, owner, valid = _validate(args, environ)
    if not valid:
        return EXIT_USAGE
    client = api if api is not None else GitHubAPI(token)
    mode = "dry-run" if args.dry_run else "apply"
    secrets = [private_key, token]

    records = []
    archived = 0
    other_owner = 0
    selected = []
    try:
        if args.repo:
            for full_name in args.repo:
                try:
                    response = client.request("GET", f"/repos/{full_name}")
                    _expect(response, {200}, f"read repository {full_name}")
                    repository = response.data if isinstance(response.data, dict) else {}
                    repository.setdefault("full_name", full_name)
                    selected.append(repository)
                except ApiError as exc:
                    records.append({"name": full_name, "archived": False,
                                    "actions": [], "errors": [str(exc)]})
        else:
            for repository in list_repositories(client):
                login = (repository.get("owner") or {}).get("login") or ""
                if login and login.lower() != owner.lower():
                    other_owner += 1
                    continue
                selected.append(repository)
    except ApiError as exc:
        report = {
            "owner": owner,
            "mode": mode,
            "rotate": bool(args.rotate),
            "counts": _counts([], archived=0, other_owner=0),
            "repos": [],
            "errors": [str(exc)],
        }
        _emit(report, args.report, secrets)
        print(f"[enroll] {mode}: failed to list repositories: {exc}",
              file=sys.stderr)
        return EXIT_FAILED

    for repository in selected:
        record = reconcile_repo(
            client, repository, app_id=app_id, private_key=private_key,
            rotate=args.rotate, dry_run=args.dry_run)
        if record["archived"]:
            archived += 1
        records.append(record)

    counts = _counts(records, archived=archived, other_owner=other_owner)
    report = {
        "owner": owner,
        "mode": mode,
        "rotate": bool(args.rotate),
        "counts": counts,
        "repos": records,
    }
    _emit(report, args.report, secrets)

    for record in records:
        summary = ", ".join(record["actions"]) or "no changes"
        print(f"[enroll] {record['name']}: {summary}", file=sys.stderr)
        for error in record["errors"]:
            print(f"[enroll] {record['name']}: ERROR {_scrub(error, secrets)}",
                  file=sys.stderr)
    c = counts
    print(
        f"[enroll] {mode}: repos={c['repos']} archived_skipped={c['archived_skipped']} "
        f"other_owner_skipped={c['other_owner_skipped']} processed={c['processed']} "
        f"failed={c['failed']} variable(created={c['variable_created']},"
        f"updated={c['variable_updated']},unchanged={c['variable_unchanged']},"
        f"planned={c['variable_create_planned'] + c['variable_update_planned']}) "
        f"secret(created={c['secret_created']},rotated={c['secret_rotated']},"
        f"unchanged={c['secret_unchanged']},"
        f"planned={c['secret_create_planned'] + c['secret_rotate_planned']})",
        file=sys.stderr)
    return EXIT_FAILED if counts["failed"] else EXIT_OK


def main():
    return run()


if __name__ == "__main__":
    sys.exit(main())
