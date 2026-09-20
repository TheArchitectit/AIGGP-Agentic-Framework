import sys, os
sys.path.insert(0, os.path.join(sys.argv[1]))
from catalog import paginate
items = list(range(25))
assert paginate(items, 10, 0) == list(range(10)), paginate(items, 10, 0)
assert paginate(items, 10, 1) == list(range(10, 20))
assert paginate(items, 10, 2) == list(range(20, 25))
assert paginate(items, 10, 3) == []
assert paginate([], 10, 0) == []
print("hidden verification passed")
