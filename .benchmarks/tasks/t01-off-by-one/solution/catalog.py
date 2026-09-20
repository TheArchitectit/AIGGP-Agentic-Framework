"""Product catalog pagination."""

def paginate(items, size, index):
    """Return page `index` (0-based) of `size` items."""
    start = size * index
    end = start + size
    return items[start:end]
