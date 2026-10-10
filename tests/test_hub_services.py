"""Tests for hub/services.py + the GET /services endpoints (mon-svcdisco-01).

Wires a real hub ThreadingHTTPServer on an ephemeral port (stdlib only, no
network beyond loopback) and drives it with urllib. Verifies:
  - GET /services returns the committed example map
  - GET /services/<known> is 200
  - GET /services/<unknown> is 404 unknown_service
  - resolution against an enrolled runner sets host/resolved
  - no token/secret appears in any response

Dual-runnable: pytest collects test_*; `python3 tests/test_hub_services.py`
runs them too.
"""
import json
import sys
import threading
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hub.config import Config  # noqa: E402
from hub.server import create_server  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = REPO_ROOT / "hub" / "schema" / "services.example.json"


def _get(port: int, path: str):
    """GET path from the hub; returns (status, parsed-json)."""
    url = f"http://127.0.0.1:{port}{path}"
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def _serve(tmp_path, services_source: Path | None = None):
    """Start a hub server over a fresh data dir. Optionally seed services.json
    from a committed file so the test asserts against a shipped artifact."""
    config = Config()
    config.data_dir = str(tmp_path / "hubdata")
    import os
    os.makedirs(config.data_dir, exist_ok=True)
    if services_source is not None:
        (Path(config.data_dir) / "services.json").write_text(
            services_source.read_text(), encoding="utf-8")
    server = create_server(config, bind=("127.0.0.1", 0))
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, port


def test_services_endpoint_returns_committed_map(tmp_path):
    """/services returns the committed example map verbatim."""
    expected = json.loads(EXAMPLE.read_text(encoding="utf-8"))["services"]
    server, port = _serve(tmp_path, services_source=EXAMPLE)
    try:
        status, body = _get(port, "/services")
        assert status == 200
        assert body["ok"] is True
        assert body["count"] == len(expected)
        assert body["services"] == expected
    finally:
        server.shutdown()


def test_services_endpoint_known_name_200(tmp_path):
    """/services/<known> resolves to a 200 entry carrying the name."""
    server, port = _serve(tmp_path, services_source=EXAMPLE)
    try:
        status, body = _get(port, "/services/ci-postgres")
        assert status == 200
        assert body["name"] == "ci-postgres"
        assert body["port"] == 5432
        assert "resolved" in body and body["resolved"] is False
    finally:
        server.shutdown()


def test_services_endpoint_unknown_name_404(tmp_path):
    """/services/<unknown> is 404 unknown_service."""
    server, port = _serve(tmp_path, services_source=EXAMPLE)
    try:
        status, body = _get(port, "/services/does-not-exist")
        assert status == 404
        assert body == {"ok": False, "error": "unknown_service"}
    finally:
        server.shutdown()


def test_resolution_against_enrolled_runner(tmp_path):
    """An enrolled runner for the service's host_alias sets host + resolved."""
    server, port = _serve(tmp_path, services_source=EXAMPLE)
    try:
        state = server.hub_state  # type: ignore[attr-defined]
        # Enroll a runner whose host_alias matches ci-postgres's provider and
        # that publishes an explicit address.
        state.registry.add_enrollment_token("tok")
        state.registry.consume_enrollment_token("tok")
        runner = state.registry.enroll(
            "svc-host-1", "owner/repo", ["devgate"], "example-service-host")
        runner["address"] = "192.0.2.10"  # TEST-NET-1, documentation range
        state.registry.save()

        status, body = _get(port, "/services/ci-postgres")
        assert status == 200
        assert body["resolved"] is True
        assert body["host"] == "192.0.2.10"
        assert body["host_alias"] == "example-service-host"
    finally:
        server.shutdown()


def test_no_address_enrolled_runner_resolves_but_host_null(tmp_path):
    """Enrolled but no published address -> resolved True, host null (never invented)."""
    server, port = _serve(tmp_path, services_source=EXAMPLE)
    try:
        state = server.hub_state  # type: ignore[attr-defined]
        state.registry.add_enrollment_token("tok")
        state.registry.consume_enrollment_token("tok")
        state.registry.enroll(
            "svc-host-2", "owner/repo", ["devgate"], "example-service-host")
        state.registry.save()

        status, body = _get(port, "/services/ci-postgres")
        assert status == 200
        assert body["resolved"] is True
        assert body["host"] is None
    finally:
        server.shutdown()


def test_no_secret_leaks_in_services_responses(tmp_path):
    """No heartbeat token appears in any /services response body."""
    server, port = _serve(tmp_path, services_source=EXAMPLE)
    try:
        state = server.hub_state  # type: ignore[attr-defined]
        state.registry.add_enrollment_token("tok")
        state.registry.consume_enrollment_token("tok")
        runner = state.registry.enroll(
            "svc-host-3", "owner/repo", ["devgate"], "example-service-host")
        secret = runner["heartbeat_token"]
        state.registry.save()

        for path in ("/services", "/services/ci-postgres",
                     "/services/llama", "/services/nope"):
            url = f"http://127.0.0.1:{port}{path}"
            try:
                with urllib.request.urlopen(url) as resp:
                    raw = resp.read().decode()
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode()
            assert secret not in raw, f"token leaked in {path}"
            assert "heartbeat_token" not in raw, f"token field leaked in {path}"
    finally:
        server.shutdown()


def main() -> int:
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))


if __name__ == "__main__":
    main()
