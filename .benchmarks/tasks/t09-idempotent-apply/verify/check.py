import sys
repo = sys.argv[1]
sys.path.insert(0, repo)
from pricing import apply_discounts
prices = {"a": 100.0, "b": 49.99}
d = {"a": 10}
# First application:
once, state = apply_discounts(prices, d)
assert once == {"a": 90.0, "b": 49.99}, once
assert state == {"a": 10}, state
# RETRY with the returned state: no compounding.
retried, state2 = apply_discounts(prices, d, state)
assert retried == once, f"retry compounded: {retried}"
assert state2 == state, "state must survive a retry unchanged"
# Input prices never mutated:
assert prices == {"a": 100.0, "b": 49.99}, "input mutated"
# A NEW discount set with fresh state applies on its own base:
other, other_state = apply_discounts({"b": 49.99}, {"b": 20})
assert other == {"b": 39.99} and other_state == {"b": 20}, (other, other_state)
print("hidden verification passed")
