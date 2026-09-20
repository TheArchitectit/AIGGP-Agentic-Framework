import subprocess, sys, os
repo = sys.argv[1]
cli = os.path.join(repo, "check_cli.py")
py = sys.executable
cases = [
    (["good"], 0, "OK\n"),
    (["bad"], 2, "FAIL\n"),
    ([], 1, "usage: check <value>\n"),
]
for argv, want_code, want_out in cases:
    r = subprocess.run([py, cli] + argv, capture_output=True, text=True)
    assert r.returncode == want_code, (argv, r.returncode, want_code)
    assert r.stdout == want_out, (argv, r.stdout)
print("hidden verification passed")
