"""Invariant tests for the ops/app schema split.

These are pure metadata tests — no DB connection. They guard against the
single biggest footgun in the schema-split design: a future model that
silently lands in ``public`` because someone forgot ``__table_args__``.
"""

from __future__ import annotations

import pytest

from pipeline import models  # noqa: F401  — ensures every model is registered
from pipeline.models.base import APP_SCHEMA, OPS_SCHEMA, Base

_ALLOWED_SCHEMAS = {OPS_SCHEMA, APP_SCHEMA}

# Hard-coded expected placement. Updating this list is a conscious decision,
# not an accident. If you add a table, also add it here.
_EXPECTED_SCHEMA_BY_TABLE = {
    "leads": OPS_SCHEMA,
    "scans": OPS_SCHEMA,
    "extractions": OPS_SCHEMA,
    "emails": OPS_SCHEMA,
    "suppression_list": OPS_SCHEMA,
    "events": OPS_SCHEMA,
    "analysts": OPS_SCHEMA,
    "login_attempts": OPS_SCHEMA,
    "lead_reviews": OPS_SCHEMA,
    "scan_reviews": OPS_SCHEMA,
    "sites": APP_SCHEMA,
    "payments": APP_SCHEMA,
}


def test_every_table_has_a_schema() -> None:
    """No table may default to ``public`` — every model sets an explicit schema."""
    unqualified = [t.name for t in Base.metadata.tables.values() if t.schema is None]
    assert not unqualified, (
        f"Tables without an explicit schema: {unqualified}. "
        "Add __table_args__ = (..., {'schema': OPS_SCHEMA}) or APP_SCHEMA."
    )


def test_every_schema_is_managed() -> None:
    """No table may live in a schema outside ops/app."""
    stray = [
        (t.name, t.schema) for t in Base.metadata.tables.values()
        if t.schema not in _ALLOWED_SCHEMAS
    ]
    assert not stray, f"Tables in unmanaged schemas: {stray}"


@pytest.mark.parametrize("table_name,expected_schema", _EXPECTED_SCHEMA_BY_TABLE.items())
def test_table_is_in_expected_schema(table_name: str, expected_schema: str) -> None:
    """Each known table lives in its documented schema."""
    matches = [t for t in Base.metadata.tables.values() if t.name == table_name]
    assert matches, f"Table {table_name!r} is not registered on Base.metadata"
    assert len(matches) == 1, f"Table {table_name!r} is registered multiple times"
    assert matches[0].schema == expected_schema, (
        f"Table {table_name!r} is in schema {matches[0].schema!r}, "
        f"expected {expected_schema!r}"
    )


def test_foreign_keys_reference_schema_qualified_tables() -> None:
    """FK ``target_fullname`` must always include a schema prefix."""
    violations = []
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            # target_fullname has the form "schema.table.column" when qualified.
            parts = fk.target_fullname.split(".")
            if len(parts) != 3:
                violations.append(
                    f"{table.fullname}.{fk.parent.name} -> {fk.target_fullname}"
                )
    assert not violations, (
        "Foreign keys missing schema prefix:\n  " + "\n  ".join(violations)
    )
