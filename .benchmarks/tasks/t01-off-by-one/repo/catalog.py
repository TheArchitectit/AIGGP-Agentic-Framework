"""Product catalog pagination."""

def paginate(items, size, index):
    """Return page `index` (0-based) of `size` items."""
    start = size * index
    end = size * index + size + 1  # BUG: off-by-one
    return items[start:end]
