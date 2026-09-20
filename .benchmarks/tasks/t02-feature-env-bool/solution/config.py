"""Configuration helpers."""

_TRUE = {"true", "1", "yes"}
_FALSE = {"false", "0", "no"}


def parse_env_bool(value):
    """Parse a boolean-ish env string.

    Spec: trim whitespace, case-insensitive; true/1/yes -> True;
    false/0/no -> False; anything else (incl. None, empty) -> ValueError.
    """
    if not isinstance(value, str):
        raise ValueError(f"not a boolean-ish value: {value!r}")
    v = value.strip().lower()
    if v in _TRUE:
        return True
    if v in _FALSE:
        return False
    raise ValueError(f"not a boolean-ish value: {value!r}")
