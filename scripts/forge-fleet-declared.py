#!/usr/bin/env python3
# // spec: GLF-10, GLF-13
"""forge-fleet-declared.py — add declared GitLab sources to a fleet declaration.

The GitHub half of the declaration is produced by
`scripts/secret-scan-declared.sh`. This script merges the GitLab half from the
deployer's declared instances and writes the one-URL-per-line declaration
`scripts/secret-scan-fleet.sh --declared` consumes.

    scripts/secret-scan-declared.sh --out gh.txt
    scripts/forge-fleet-declared.py --github-declaration gh.txt --out all.txt

The access token is read from `GITLAB_TOKEN` (override with `--token-env`) and
is never written to the output or a log line. This is the component that
contacts an instance, so running it against a real instance is Sprint 0 work;
the merge itself is exercised hermetically by tests with a local stub.

Exit codes: 0 declaration written | 2 usage/config/token error |
3 an empty declaration or a refused instance.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hub.forge import (  # noqa: E402
    FleetDeclarationError,
    GitLabClient,
    build_fleet_declaration,
    declared_gitlab_instances,
    load_instance_declarations,
    render_declaration,
)

EXIT_OK, EXIT_USAGE, EXIT_DECLARATION = 0, 2, 3


def read_urls(path: Path | None) -> list[str]:
    if path is None:
        return []
    if not path.is_file():
        raise FleetDeclarationError(f"github declaration not found: {path}")
    urls = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            urls.append(line)
    return urls


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=None,
                    help="instance config (default: FORGE_INSTANCES_CONFIG or hub/forge/instances.toml)")
    ap.add_argument("--github-declaration", type=Path, default=None,
                    help="output of scripts/secret-scan-declared.sh")
    ap.add_argument("--out", type=Path, required=True,
                    help="merged declaration to write")
    ap.add_argument("--token-env", default="GITLAB_TOKEN",
                    help="environment variable holding the API token")
    ap.add_argument("--allow-insecure", action="store_true",
                    help="use http:// for declared instances (tailnet-only)")
    args = ap.parse_args(argv)

    try:
        declarations = load_instance_declarations(args.config)
        github_urls = read_urls(args.github_declaration)
    except (FleetDeclarationError, ValueError) as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return EXIT_USAGE

    declared = declared_gitlab_instances(declarations)
    token = os.environ.get(args.token_env, "")
    if declared and not token.strip():
        print(
            f"FAIL: {len(declared)} GitLab instance(s) declared but "
            f"{args.token_env} is empty; the walk cannot authenticate",
            file=sys.stderr,
        )
        return EXIT_USAGE

    scheme = "http" if args.allow_insecure else "https"
    clients = {
        instance_id: GitLabClient(
            f"{scheme}://{declarations[instance_id].host_alias}",
            token,
            allow_insecure=args.allow_insecure,
        )
        for instance_id in declared
    }

    try:
        urls = build_fleet_declaration(github_urls, declarations, clients)
        body = render_declaration(urls)
    except FleetDeclarationError as e:
        print(f"FAIL: {e}", file=sys.stderr)
        return EXIT_DECLARATION

    args.out.write_text(body, encoding="utf-8")
    print(
        f"[forge-fleet-declared] wrote {len(urls)} source(s) "
        f"({len(github_urls)} github, {len(declared)} gitlab instance(s) walked)"
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
