"""Exercise catch-all signatures with an inert synthetic adapter fixture."""
import importlib.util
import json
from pathlib import Path


fixture_path = Path(__file__).resolve().parents[1] / "tests" / "test_adapters_v1.py"
spec = importlib.util.spec_from_file_location("adapter_fixture", fixture_path)
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class DigestCatchAll(fixture.FakeAdapter):
    def ensure_image(self, operation_key, **digest):
        return digest


class ReferenceCatchAll(fixture.FakeAdapter):
    def create_runner(self, operation_key, **registration_ref):
        return registration_ref


class UnnamedCatchAll(fixture.FakeAdapter):
    def ensure_image(self, **kwargs):
        return kwargs


def outcome(adapter):
    try:
        fixture.check_contract(adapter(), runtime=fixture.Runtime.PODMAN)
    except fixture.AdapterContractError as exc:
        return {"result": "rejected", "reason": str(exc)}
    return {"result": "accepted"}


results = {
    "named_digest_catchall": outcome(DigestCatchAll),
    "named_registration_ref_catchall": outcome(ReferenceCatchAll),
    "unnamed_catchall": outcome(UnnamedCatchAll),
}
assert results["named_digest_catchall"]["result"] == "accepted"
assert results["named_registration_ref_catchall"]["result"] == "accepted"
assert results["unnamed_catchall"]["result"] == "rejected"
print(json.dumps(results, indent=2, sort_keys=True))
