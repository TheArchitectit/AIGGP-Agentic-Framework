import sys, os, tempfile
repo = sys.argv[1]
sys.path.insert(0, repo)
from journal import load_journal
with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
    fh.write('{"a": 1}\n{"b": 2}\n{"b": 3')  # truncated trailing write
    path = fh.name
entries, recovered = load_journal(path)
os.unlink(path)
assert entries == [{"a": 1}, {"b": 2}], entries
assert recovered is True, recovered
with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as fh:
    fh.write('{"a": 1}\nNOT JSON\n{"b": 2}\n')
    path = fh.name
try:
    load_journal(path)
except ValueError:
    pass
else:
    raise AssertionError("mid-file corruption must raise")
os.unlink(path)
print("hidden verification passed")
