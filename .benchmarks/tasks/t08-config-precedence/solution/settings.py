DEFAULTS = {"host": "localhost", "port": "8080", "debug": "0"}


def resolve_settings(file_settings=None, env_settings=None):
    """Merge settings: defaults < file < environment."""
    merged = dict(DEFAULTS)
    for k, v in (file_settings or {}).items():
        if v is not None:
            merged[k] = v
    for k, v in (env_settings or {}).items():
        if v is not None:
            merged[k] = v
    return merged
