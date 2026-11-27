"""Collect one reference PR's native jobs. Pass --publish to upsert its two App checks."""
import argparse
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path

REPO = "TheArchitectit/AIGGP-Agentic-Framework"
API = f"/repos/{REPO}/"
PIN = "bdbd450e0275a05b319ce29d83f761e8ed552e69"
INFRA = "cc62e68128bcfb86528baf2718bc42caee57b932"
APP = 2550930
BASE = "codex/reference-promotion"
ROOT = Path(__file__).resolve().parents[4]
TEMPLATE = ROOT / "templates/consumer-delivery-reference"
WORKFLOWS = {
    "reference-consumer.yml": "Synthetic source behavior",
    "text-integrity.yml": "Text integrity (charset / encoding / corruption)",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git_file(repo, revision, path):
    return subprocess.check_output(["git", "-C", str(repo), "show", f"{revision}:{path}"])


class GitHubApp:
    def __init__(self, infra):
        # Send the reviewed helper object to AI02, even if the checkout is dirty.
        self.helper = git_file(infra, INFRA, "scripts/gh-app-api")

    def request(self, endpoint, method="GET", body=None, raw=False):
        command = ["sudo", "-n", "python3", "-"]
        if raw:
            command.append("--raw")
        command.extend([method, API + endpoint])
        if body is not None:
            command.append(json.dumps(body, separators=(",", ":")))
        response = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "ai02", shlex.join(command)],
            input=self.helper, stdout=subprocess.PIPE, check=True, timeout=90,
        )
        return response.stdout if raw else json.loads(response.stdout)

    def publish(self, sha, name, receipt, existing):
        owned = [c for c in existing if c["app"]["id"] == APP and c["name"] == name]
        require(len(owned) <= 1, f"duplicate App checks for {name}")
        body = {"name": name, "details_url": receipt["url"], "status": "completed",
                "conclusion": receipt["verdict"], "output": {"title": name,
                "summary": json.dumps(receipt, sort_keys=True)}}
        if owned:
            check = self.request(f"check-runs/{owned[0]['id']}", "PATCH", body)
        else:
            check = self.request("check-runs", "POST", {**body, "head_sha": sha})
        require(check["app"]["id"] == APP and check["head_sha"] == sha and
                check["details_url"] == receipt["url"] and check["conclusion"] == receipt["verdict"],
                "published check readback mismatch")
        return check["html_url"]


def blob_id(content):
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def verify_inputs(app, merge):
    tree = app.request(f"git/trees/{merge}?recursive=1")
    require(not tree["truncated"], "incomplete consumer tree")
    blobs = {x["path"]: x for x in tree["tree"] if x["type"] == "blob"}
    text = ".github/workflows/text-integrity.yml"
    trusted = git_file(ROOT, PIN, "templates/github-workflows/text-integrity.yml")
    approved_text = trusted.replace(b"REPLACE_WITH_REVIEWED_FULL_40_HEX_COMMIT", PIN.encode())
    paths = (".gitattributes", ".gitignore", ".guardrails/scope.json", ".guardrails/charset-allowlist.json",
             "tests/test_app.py", "tests/run_tests.py", ".github/workflows/reference-consumer.yml")
    for path in (*paths, text):
        content = approved_text if path == text else (TEMPLATE / path).read_bytes()
        require(path in blobs and blobs[path]["mode"] == "100644" and blobs[path]["sha"] == blob_id(content),
                f"stale tooling or changed trusted input: {path}")
    require(set(blobs) == {*paths, text, "app.py", "case.txt"} and
            all(x["type"] in ("blob", "tree") for x in tree["tree"]), "unexpected consumer tree")
    app_src = (TEMPLATE / "app.py").read_bytes()
    broken = app_src.replace(b"return value * 2", b"return value + 2")
    require(blobs["app.py"]["mode"] == "100644" and blobs["app.py"]["sha"] in
            {blob_id(app_src), blob_id(broken)} and blobs["case.txt"]["mode"] == "100644",
            "unreviewed executable payload")
    return len(blobs)


def inspect_job(app, run, name, sha, merge, checks, size):
    require(run["status"] == "completed", "job run incomplete")
    jobs = app.request(f"actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs")["jobs"]
    require(len(jobs) == 1 and jobs[0]["name"] == name, "missing or ambiguous job")
    job = jobs[0]
    native = [c for c in checks if c["id"] == job["id"] and c["app"]["id"] == 15368 and
              c["head_sha"] == sha and c["check_suite"]["id"] == run["check_suite_id"]]
    require(len(native) == 1 and native[0]["conclusion"] == job["conclusion"] and
            job["head_sha"] == sha and job["status"] == "completed", "native check/job mismatch")
    row = {"job": job["id"], "url": job["html_url"], "run": run["id"], "attempt": run["run_attempt"],
           "runner": job["runner_name"], "runner_id": job["runner_id"], "labels": job["labels"],
           "native": job["conclusion"], "failed_steps": [s["name"] for s in job["steps"] if s["conclusion"] == "failure"],
           "skipped": [s["name"] for s in job["steps"] if s["conclusion"] == "skipped"]}
    try:
        require(job["labels"] == ["ubuntu-latest"] and job["runner_name"].startswith("GitHub Actions "),
                "wrong or missing runner")
        log = app.request(f"actions/jobs/{job['id']}/logs", raw=True).decode("utf-8", errors="replace")
        require("Hosted Compute Agent" in log, "missing hosted provisioner")
        checkouts = re.findall(r"(?m)^\S+Z ([a-f0-9]{40})\r?$", log)
        require(len(checkouts) == 1, "missing or ambiguous checkout SHA")
        row["checkout"] = checkouts[0]
        require(row["checkout"] == merge, "superseded merge checkout")
        if name == WORKFLOWS["text-integrity.yml"]:
            pin = re.findall(r"(?m)^\S+Z DevGate ready at ([a-f0-9]{40}) under \.devgate/", log)
            require(len(pin) == 1, "tool bootstrap missing")
            row["tool"] = pin[0]
            require(pin[0] == PIN, "stale tool pin")
            if job["conclusion"] != "success":
                row["text_inputs"] = "NOT_REPORTED"
                if "case.txt:2:1  U+00A7" in log and "1 file(s) exceed their charset baseline" in log:
                    row.update(diagnostic="Denied U+00A7 at case.txt:2:1", offending_files=1)
                raise ValueError("text job " + job["conclusion"])
            # Self-tests intentionally log rejections. Read the consumer scans before those tests.
            scans, marker, controls = log.partition("for t in test_check_charset.py")
            require(marker and all(f"check-{gate}: OK - {size} text file(s)" in scans
                    for gate in ("charset", "encoding", "corruption")), "missing nonempty content scans")
            require("check-corruption: OK - diff scan clean" in scans and
                    all(f"Ran {n} tests in" in controls for n in (18, 11, 26)), "missing range or gate controls")
            row["text_inputs"] = size
        else:
            require("checked out revision: " + merge in log and "Behavior test cases: 2" in log,
                    "missing real entry-point tests")
            row["tests"] = 2
            if "AssertionError: 'synthetic result: 23' != 'synthetic result: 42'" in log:
                row["diagnostic"] = "Expected 42 from input 21, observed 23."
            require(job["conclusion"] == "success" and " synthetic result: 42\n" in log and
                    " error: value must be non-negative\n" in log, "application job failed or incomplete")
        require(all(s["conclusion"] == "success" for s in job["steps"]), "required step skipped or failed")
    except ValueError as exc:
        row["issues"] = [str(exc)]
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--infra", type=Path, required=True, help="trusted infra-info clone")
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--head", required=True, help="operator-reviewed consumer SHA")
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    require(re.fullmatch("[0-9a-f]{40}", args.head), "full lowercase SHA required")
    app = GitHubApp(args.infra)
    pr = app.request(f"pulls/{args.pr}")
    sha, merge = args.head, pr["merge_commit_sha"]
    require(pr["state"] == "open" and pr["head"]["repo"]["full_name"] == REPO and
            pr["head"]["ref"].startswith("codex/reference-consumer-") and pr["head"]["sha"] == sha and
            pr["base"]["ref"] == BASE, "PR identity or base mismatch")
    parents = app.request(f"git/commits/{merge}")["parents"]
    require([p["sha"] for p in parents] == [pr["base"]["sha"], sha], "stale merge parents")
    common = []
    try:
        size = verify_inputs(app, merge)
    except ValueError as exc:
        size = 0
        common.append(str(exc))
    runs = app.request(f"actions/runs?event=pull_request&head_sha={sha}&per_page=100")
    checks = app.request(f"commits/{sha}/check-runs?per_page=100")
    require(max(runs["total_count"], checks["total_count"]) <= 100, "incomplete paginated evidence")
    rows = []
    for file, name in WORKFLOWS.items():
        matches = [r for r in runs["workflow_runs"] if r["path"] == ".github/workflows/" + file and
                   r["event"] == "pull_request" and r["head_sha"] == sha and
                   any(p["number"] == args.pr for p in r["pull_requests"])]
        try:
            require(matches, "missing workflow run")
            latest = max(matches, key=lambda r: (r["run_number"], r["run_attempt"]))
            row = inspect_job(app, latest, name, sha, merge, checks["check_runs"], size)
        except ValueError as exc:
            row = {"url": pr["html_url"], "issues": [str(exc)]}
        issues = common + row.get("issues", [])
        row.update(name="AIGGP reference / " + name, head=sha, current_merge=merge, issues=issues,
                   verdict="failure" if issues else "success")
        rows.append(row)
    again = app.request(f"pulls/{args.pr}")
    require(again["head"]["sha"] == sha and again["merge_commit_sha"] == merge, "PR changed during collection")
    for row in rows:
        if args.publish:
            row["app_url"] = app.publish(sha, row["name"], row, checks["check_runs"])
        print(json.dumps(row, sort_keys=True))
    return int(any(r["issues"] for r in rows))


if __name__ == "__main__":
    raise SystemExit(main())
