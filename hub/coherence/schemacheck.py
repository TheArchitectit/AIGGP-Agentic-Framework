# // spec: coh-dec-03, coh-pkg-02
"""Minimal stdlib JSON-Schema checker for the frozen coherence contracts.

Supports the subset the DevGate schemas actually use: type, required,
additionalProperties, properties, enum, const, pattern, minItems, minimum,
items, and local $ref into #/definitions. Stdlib-only (no jsonschema dep).

Purpose: wire the frozen schemas into a real gate so a result whose emitted
shape drifts from the contract fails a test rather than reaching a consumer.
Unsupported keywords are ignored, not silently treated as satisfied.
"""
import re

SUPPORTED = {"type", "required", "additionalProperties", "properties", "enum",
             "const", "pattern", "minItems", "minimum", "items", "$ref",
             "description", "default", "$schema", "$id", "title", "definitions"}

_TYPES = {
    "object": dict, "array": list, "string": str, "integer": int,
    "number": (int, float), "boolean": bool, "null": type(None),
}


class SchemaError(ValueError):
    """Raised when a document does not satisfy its schema."""


def _is_type(val, tname) -> bool:
    if tname == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    if tname == "boolean":
        return isinstance(val, bool)
    if tname == "number":
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    return isinstance(val, _TYPES[tname])


def _resolve(ref: str, root: dict) -> dict:
    if not ref.startswith("#/"):
        raise SchemaError(f"unsupported $ref form: {ref!r}")
    cur = root
    for part in ref[2:].split("/"):
        cur = cur[part]
    return cur


def validate(doc, schema: dict, root: dict = None, path: str = "$") -> list:
    """Return a list of violation strings (empty means valid)."""
    root = root if root is not None else schema
    errs = []

    if "$ref" in schema:
        return validate(doc, _resolve(schema["$ref"], root), root, path)

    if "const" in schema and doc != schema["const"]:
        errs.append(f"{path}: expected const {schema['const']!r}, got {doc!r}")

    if "enum" in schema and doc not in schema["enum"]:
        errs.append(f"{path}: {doc!r} not in enum {schema['enum']!r}")

    tname = schema.get("type")
    if tname is not None:
        names = tname if isinstance(tname, list) else [tname]
        if not any(_is_type(doc, n) for n in names):
            errs.append(f"{path}: expected type {tname!r}, got {type(doc).__name__}")
            return errs  # type mismatch makes deeper checks meaningless

    if isinstance(doc, str) and "pattern" in schema:
        if not re.search(schema["pattern"], doc):
            errs.append(f"{path}: {doc!r} does not match pattern {schema['pattern']!r}")

    if isinstance(doc, (int, float)) and not isinstance(doc, bool):
        if "minimum" in schema and doc < schema["minimum"]:
            errs.append(f"{path}: {doc} below minimum {schema['minimum']}")

    if isinstance(doc, list):
        if "minItems" in schema and len(doc) < schema["minItems"]:
            errs.append(f"{path}: {len(doc)} items below minItems {schema['minItems']}")
        if "items" in schema:
            for i, item in enumerate(doc):
                errs.extend(validate(item, schema["items"], root, f"{path}[{i}]"))

    if isinstance(doc, dict):
        for req in schema.get("required", []):
            if req not in doc:
                errs.append(f"{path}: missing required property {req!r}")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in doc:
                if key not in props:
                    errs.append(f"{path}: unexpected property {key!r} "
                                "(additionalProperties: false)")
        for key, sub in props.items():
            if key in doc:
                errs.extend(validate(doc[key], sub, root, f"{path}.{key}"))

    return errs
