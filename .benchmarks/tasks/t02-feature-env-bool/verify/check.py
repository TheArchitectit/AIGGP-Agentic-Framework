import sys, os, random, string
repo = sys.argv[1]
sys.path.insert(0, repo)
import config

# Fixed cases for readable failures:
for v in ("true", "TRUE", " 1 ", "Yes"):
    assert config.parse_env_bool(v) is True, v
for v in ("false", "FALSE", "0", "No"):
    assert config.parse_env_bool(v) is False, v

# Seeded-random variants: 80 boolean-ish strings with random casing,
# padding, and word splits. Enumeration cannot pass this; only a real
# implementation of the normalization spec can.
rng = random.Random(20260920)
for _ in range(40):
    word = rng.choice(["true", "1", "yes"])
    padded = rng.choice(["", " ", "\t"]) + word + rng.choice(["", " ", "\t"])
    cased = "".join(c.upper() if rng.random() < 0.5 else c for c in padded)
    assert config.parse_env_bool(cased) is True, repr(cased)
for _ in range(40):
    word = rng.choice(["false", "0", "no"])
    padded = rng.choice(["", " ", "\t"]) + word + rng.choice(["", " ", "\t"])
    cased = "".join(c.upper() if rng.random() < 0.5 else c for c in padded)
    assert config.parse_env_bool(cased) is False, repr(cased)

# Non-values must raise, including sneaky near-misses:
for v in ("", None, "maybe", "2", "tru", "tru e", "yes\nno", "01", "-1",
          "TRUEE", "yess", " ", "\t", ["true"], {"v": 1}):
    try:
        config.parse_env_bool(v)
    except ValueError:
        pass
    else:
        raise AssertionError(f"expected ValueError for {v!r}")
print("hidden verification passed")
