"""Enumerates every leaf field path in HermclawConfig's pydantic schema.

Used two ways:
  1. As a one-off generator when drafting docs/CONFIG_REFERENCE.md.
  2. By tests/test_config_reference_coverage.py, which imports
     leaf_field_paths() directly and diffs it against the doc's table --
     the actual enforcement mechanism, not just a report you have to
     remember to run.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from hermclaw.config import HermclawConfig


def _is_model(tp: Any) -> bool:
    return isinstance(tp, type) and issubclass(tp, BaseModel)


def leaf_field_paths(model_cls: type[BaseModel] = HermclawConfig, prefix: str = "") -> list[str]:
    """Every dotted field path that should have its own row in
    CONFIG_REFERENCE.md -- i.e. every field that isn't itself a nested
    object (nested objects are expanded into their own leaves instead)."""
    paths: list[str] = []
    for name, field in model_cls.model_fields.items():
        key = field.alias or name
        full_key = f"{prefix}.{key}" if prefix else key
        annotation = field.annotation
        origin = getattr(annotation, "__origin__", None)
        inner = annotation.__args__[0] if origin is list else annotation
        if _is_model(inner) and origin is not list:
            paths.extend(leaf_field_paths(inner, full_key))
        else:
            paths.append(full_key)
    return paths


if __name__ == "__main__":
    for path in leaf_field_paths():
        print(path)
