# tools/analysis/truth/resolver.py

from typing import Any


def resolve_field(obj: Any, key: str, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def resolve_list_field(obj: Any, key: str, default=None):
    value = resolve_field(obj, key, default)

    if value is None:
        return default or []

    if isinstance(value, list):
        return value

    return list(value)