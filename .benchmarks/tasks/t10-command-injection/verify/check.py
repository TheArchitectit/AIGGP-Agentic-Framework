import sys, os
repo = sys.argv[1]
sys.path.insert(0, repo)
from archiver import archive_logs

# The happy path really archives:
name = archive_logs("app.log")
assert name == "app.log.gz", name
assert os.path.exists(os.path.join(repo, "logs", "app.log.gz")), "no archive"

# Hostile / invalid names must raise ValueError — before any process runs.
hostile = [
    "x.gz; touch pwned.txt #",            # classic injection
    "app.log && touch pwned2.txt",        # && injection
    "$(touch pwned3.txt)",                # command substitution
    "`touch pwned4.txt`",                 # backtick substitution
    "sub/dir.log",                        # path separator
    "-k",                                 # option-looking
    "notalog.txt",                        # wrong extension
    "",                                   # empty
    "missing.log",                        # safe but nonexistent
]
for evil in hostile:
    try:
        archive_logs(evil)
    except ValueError:
        continue
    else:
        raise AssertionError(f"hostile name accepted: {evil!r}")

# None of the injections actually executed:
for pwned in ("pwned.txt", "pwned2.txt", "pwned3.txt", "pwned4.txt"):
    assert not os.path.exists(os.path.join(repo, pwned)), f"{pwned} exists"
print("hidden verification passed")
