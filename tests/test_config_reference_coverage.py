"""Enforces that docs/CONFIG_REFERENCE.md documents exactly the fields
HermclawConfig's pydantic schema actually has -- no more, no less. This
is the "small script that diffs the model's field names against the
doc's table" the build spec asks for, wired up as a real test rather
than a report someone has to remember to run.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts.list_config_fields import leaf_field_paths

DOC_PATH = Path(__file__).parent.parent / "docs" / "CONFIG_REFERENCE.md"

# Matches the first `code span` on a markdown table row, e.g.
# "| `body.gateway.port` | int | ... |" -> "body.gateway.port"
_ROW_FIELD_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|")


def _documented_field_paths() -> set[str]:
    text = DOC_PATH.read_text(encoding="utf-8")
    return {m.group(1) for line in text.splitlines() if (m := _ROW_FIELD_RE.match(line))}


def test_every_schema_field_is_documented() -> None:
    schema_fields = set(leaf_field_paths())
    documented = _documented_field_paths()
    missing = schema_fields - documented
    assert not missing, f"CONFIG_REFERENCE.md is missing rows for: {sorted(missing)}"


def test_doc_does_not_document_nonexistent_fields() -> None:
    schema_fields = set(leaf_field_paths())
    documented = _documented_field_paths()
    stale = documented - schema_fields
    assert not stale, f"CONFIG_REFERENCE.md documents fields that no longer exist in the schema: {sorted(stale)}"
