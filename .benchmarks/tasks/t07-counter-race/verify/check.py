import sys, threading
repo = sys.argv[1]
sys.path.insert(0, repo)
from store import CounterStore
store = CounterStore()
sys.setswitchinterval(1e-6)
N_THREADS, N_INC = 8, 25
barrier = threading.Barrier(N_THREADS)
def worker():
    barrier.wait()
    for _ in range(N_INC):
        store.increment("hits")
threads = [threading.Thread(target=worker) for _ in range(N_THREADS)]
for t in threads: t.start()
for t in threads: t.join()
got = store.get("hits")
want = N_THREADS * N_INC
assert got == want, f"lost updates: {got} != {want}"
print("hidden verification passed")
