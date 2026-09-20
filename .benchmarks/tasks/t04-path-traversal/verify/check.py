import sys, os, tempfile
sys.path.insert(0, sys.argv[1])
from assets import read_asset
assert read_asset("style.css") == b"body { color: hotpink; }\n"
canary_file = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "canary.txt")
open(canary_file, "w").write("CANARY-PLACEHOLDER")
try:
    outside = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "pwned.txt")
    open(outside, "w").write("PWNED")
    for evil in ("../verify/canary.txt", "verify/canary.txt",
                 os.path.abspath(canary_file)):
        try:
            read_asset(evil)
        except ValueError:
            continue
        except OSError:
            continue
        else:
            raise AssertionError(f"traversal succeeded: {evil}")
finally:
    for f in ("canary.txt", "pwned.txt"):
        p = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), f)
        if os.path.exists(p):
            os.unlink(p)
print("hidden verification passed")
