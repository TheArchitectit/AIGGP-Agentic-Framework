"""Compare OpenSpec CLI and marker-parser requirement IDs in main specs."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, "scripts/lib")
from spec_discovery import DRAFT, _requirement_blocks  # noqa: E402

CLI = "./node_modules/.bin/openspec"
ID_MARKER = re.compile(r"<!--\s*id:\s*([A-Za-z0-9-]+)\s*-->")


def query(*arguments):
    output = subprocess.check_output([CLI, *arguments, "--json"])
    return json.loads(output)


def compare(entry):
    capability = entry["id"]
    parsed = query("show", capability)
    cli_ids = []
    for requirement in parsed["requirements"]:
        cli_ids.extend(ID_MARKER.findall(requirement["text"]))
    spec_path = Path("openspec/specs") / capability / "spec.md"
    marker_ids = [
        requirement_id
        for requirement_id, block in _requirement_blocks(spec_path.read_text())
        if not DRAFT.search(block)
    ]
    matched = (
        len(cli_ids) == entry["requirementCount"]
        and len(cli_ids) == len(set(cli_ids))
        and sorted(cli_ids) == sorted(marker_ids)
    )
    return {
        "capability": capability,
        "cli_count": entry["requirementCount"],
        "cli_ids": cli_ids,
        "marker_ids": marker_ids,
        "matched": matched,
    }


entries = query("list", "--specs")["specs"]
with ThreadPoolExecutor(max_workers=6) as pool:
    results = sorted(pool.map(compare, entries), key=lambda row: row["capability"])
report = {
    "capabilities": len(results),
    "matched": sum(row["matched"] for row in results),
    "mismatches": [row for row in results if not row["matched"]],
    "results": results,
}
print(json.dumps(report, indent=2, sort_keys=True))
