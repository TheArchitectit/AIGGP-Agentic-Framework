import sys
repo = sys.argv[1]
sys.path.insert(0, repo)
from settings import resolve_settings
r = resolve_settings({"host": "file.example"}, {"host": "env.example"})
assert r["host"] == "env.example", f"env must win: {r}"
r = resolve_settings({"host": "file.example"}, {})
assert r["host"] == "file.example", "file wins over default"
r = resolve_settings({}, {"port": "9000"})
assert r["port"] == "9000", "env wins over default"
r = resolve_settings({"debug": "1"}, {"debug": ""})
assert r["debug"] == "", f"empty env value still counts as set: {r}"
r = resolve_settings({}, {})
assert r == {"host": "localhost", "port": "8080", "debug": "0"}, r
print("hidden verification passed")
