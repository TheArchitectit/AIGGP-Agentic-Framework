def apply_discounts(prices, discounts, state=None):
    """Apply {sku: percent_off} discounts. Returns (discounted, state).

    Retry-safety contract: `prices` is the UNDISCOUNTED base on every call
    (callers keep it immutable); `state` records what was already applied
    (sku -> pct). A retried call passes the returned state back and MUST
    get byte-identical prices — recompute from the base using the recorded
    pct, never compound.

    BUG: this version mutates the caller's `prices` dict in place, so a
    retry compounds the discount (100 -> 90 -> 81).
    """
    applied = dict(state or {})
    for sku, pct in discounts.items():
        if sku in prices:
            prices[sku] = round(prices[sku] * (100 - pct) / 100, 2)  # BUG
            applied[sku] = pct
    return prices, applied
