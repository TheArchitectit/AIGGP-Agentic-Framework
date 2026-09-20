"""Configuration helpers."""


def parse_env_bool(value):
    """Parse a boolean-ish env string.

    Spec: trim whitespace, case-insensitive; true/1/yes -> True;
    false/0/no -> False; anything else (incl. None, empty) -> ValueError.
    NOT IMPLEMENTED YET.
    """
    raise NotImplementedError
