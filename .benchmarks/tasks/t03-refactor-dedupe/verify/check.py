import sys, os, ast
repo = sys.argv[1]
sys.path.insert(0, repo)
import users
assert users.format_user("  Ada   Lovelace ") == "user:ada lovelace"
assert users.format_admin("  GRACE  HOPPER ") == "admin:grace hopper"
src = open(os.path.join(repo, "users.py")).read()
assert src.count("strip().lower()") == 1, "duplication still present"
tree = ast.parse(src)
fns = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
assert "normalize_name" in fns, f"shared helper missing, found {fns}"
print("hidden verification passed")
