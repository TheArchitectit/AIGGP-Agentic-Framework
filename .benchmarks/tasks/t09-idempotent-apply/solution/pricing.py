def apply_discounts(prices, discounts, state=None):
    """Apply {sku: percent_off} discounts. Returns (discounted, state).

    Retry-safe by recompute: `prices` is the immutable base, `state`
    records the applied pct per sku. For every discounted sku the result
    is recomputed from the base with the RECORDED pct — a retry with the
    returned state reproduces byte-identical prices, never compounds.
    """
    out = dict(prices)
    applied = dict(state or {})
    for sku, pct in discounts.items():
        if sku not in out:
            continue
        effective = applied.get(sku, pct)
        out[sku] = round(out[sku] * (100 - effective) / 100, 2)
        applied[sku] = effective
    return out, applied
