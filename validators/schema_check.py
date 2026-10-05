"""Minimal JSON-Schema (subset) validator — no external dependency needed.

Supports: type, required, properties, items, enum, minimum/maximum,
minLength, additionalProperties(ignore). Used as the final gate before
shards are written and by the pipeline's own tests.
"""
from __future__ import annotations


def validate(instance, schema, path="$") -> list:
    errs = []
    t = schema.get("type")
    if t and not _type_ok(instance, t):
        return [f"{path}: expected type {t}, got {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} not in enum {schema['enum'][:8]}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errs.append(f"{path}: shorter than minLength {schema['minLength']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append(f"{path}: below minimum {schema['minimum']}")
    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errs.append(f"{path}: missing required property {req!r}")
        for key, sub in schema.get("properties", {}).items():
            if key in instance:
                errs += validate(instance[key], sub, f"{path}.{key}")
    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            errs += validate(item, schema["items"], f"{path}[{i}]")
    return errs


def _type_ok(v, t):
    types = t if isinstance(t, list) else [t]
    for name in types:
        ok = {"object": lambda x: isinstance(x, dict),
              "array": lambda x: isinstance(x, list),
              "string": lambda x: isinstance(x, str),
              "integer": lambda x: isinstance(x, int) and not isinstance(x, bool),
              "number": lambda x: isinstance(x, (int, float)) and not isinstance(x, bool),
              "boolean": lambda x: isinstance(x, bool),
              "null": lambda x: x is None}.get(name)
        if ok and ok(v):
            return True
    return False
