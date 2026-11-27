# Monitor recovery input inventory

Reviewed AIGGP commit `80d18b0f0f4e080c9e47d4e534cc2c56c29308ca`.
The service takes its state root from `Config.data_dir`. The default is
`/data`, the environment override is `HUB_DATA_DIR`, and the command-line
`--data-dir` takes precedence. [Configuration](../../../hub/config.py) and
[startup](../../../hub/main.py).

| Configured input | On-disk format and writer | Recovery decision |
| --- | --- | --- |
| `runners.json` | The [registry](../../../hub/registry.py) replaces this file atomically. The [v1 schema](../../../hub/schema/runners.schema.json) includes runner data, enrollment state and toolchain state. | Pending one-time enrollment values and legacy plaintext heartbeat fields disqualify a raw backup. Preserve the salt and authorized verifier hashes together. Handle runner addresses, toolchain decision history and spent nonces explicitly in the backup format. Restoring historical authorization state requires reconciliation before service resumes. |
| `services.json` | The [service map](../../../hub/services.py) replaces this file atomically. Its [v1 schema](../../../hub/schema/services.schema.json) stores a service name, host alias, port and optional protocol or description. | Keep discovery metadata private. Validate the declared schema before replacement. Resolve the current runner address through authenticated reconciliation. A restored service entry alone cannot establish reachability. |
| `alerts/alerts-YYYY-MM-DD.jsonl` | The [alert writer](../../../hub/alerts.py) appends one JSON object with `ts`, `repo`, `check_class`, `runner` and `detail`. The on-disk row carries no format-version field. | Version the accepted row shape in the backup manifest. Free-text detail and runner or repository identifiers need privacy review. Reject a generation whose fields cannot meet the backup contract. Reconcile open issues separately before issuing a convergence receipt. |

Restrict collection to the qualified state paths. Keep environment files,
enrollment and polling credentials, container definitions, temporary save files,
and unrelated instance data outside the recovery set. The two JSON saves and
the daily log append are independent operations. A consistent generation still
requires a quiesced writer and exclusive ownership.

## Verification

A network-isolated Linux fixture used the source commit above and a fresh
temporary data directory. It ran the startup enrollment loader with a generated
one-time value, saved a fresh registry and service map, then appended one
synthetic alert. It asserted that the registry retained the pending value,
both JSON documents had version 1, and the single alert had exactly the five
fields listed above. Exactly three files were created. No credential value
was printed. This verifies input identification and content sensitivity.

Manifest validation, writer fencing, restore and post-restore convergence
remain open in the [implementation checklist](tasks.md).

To repeat the input check, run the following at the repository root with
Python 3 and the hub dependencies installed. It uses a temporary directory
and the hub's local persistence functions. Successful output is
`PASS: recovery-input inventory`.

```sh
python3 - <<'PY'
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from secrets import token_hex
from hub.config import Config
from hub.main import load_enrollment_tokens
from hub.registry import Registry
from hub.services import Services
from hub.alerts import _append_jsonl
with TemporaryDirectory() as name:
    root = Path(name)
    cfg = Config(data_dir=name)
    registry = Registry(cfg.registry_path)
    value = token_hex(24)
    load_enrollment_tokens(registry, value)
    registry.save()
    state = json.loads(Path(cfg.registry_path).read_bytes())
    assert state["version"] == 1 and state["enrollment_tokens"] == [value]
    Services(cfg.services_path).save()
    assert json.loads(Path(cfg.services_path).read_bytes()) == {"version": 1, "services": {}}
    _append_jsonl(Path(cfg.alerts_dir), "fixture/repo", "fixture-check", "fixture-runner", "fixture detail")
    logs = list(Path(cfg.alerts_dir).glob("alerts-*.jsonl"))
    assert len(logs) == 1
    row = json.loads(logs[0].read_bytes())
    assert set(row) == {"ts", "repo", "check_class", "runner", "detail"} and row["detail"] == "fixture detail"
    assert {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()} == {"runners.json", "services.json", logs[0].relative_to(root).as_posix()}
print("PASS: recovery-input inventory")
PY
```
