"""CSV-backed target list for batch lead generation.

The batch flow (``pipeline.flows.lead_generator_batch``) consumes a CSV of
``(vertical, state, city)`` rows and runs the single-city lead-gen loop for
each. Keeping the list in a repo CSV means it's editable in PRs, diffable,
and needs no schema migration.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


class InvalidTargetsFileError(Exception):
    """Raised when the targets CSV is malformed or empty."""


@dataclass(frozen=True)
class CityTarget:
    vertical: str
    state: str
    city: str

    def label(self) -> str:
        return f"{self.vertical} / {self.city}, {self.state}"


_REQUIRED_COLUMNS = {"vertical", "state", "city"}


def load_targets(path: Path | str) -> list[CityTarget]:
    """Load targets from a CSV with columns ``vertical,state,city``.

    - Empty rows are skipped.
    - Whitespace around cell values is stripped.
    - Duplicate ``(vertical, state, city)`` triples are collapsed.
    - Rows with any empty required cell raise ``InvalidTargetsFileError``.
    """
    p = Path(path)
    if not p.exists():
        raise InvalidTargetsFileError(f"targets file not found: {p}")

    with p.open("r", newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise InvalidTargetsFileError(f"targets file has no header: {p}")
        missing = _REQUIRED_COLUMNS - {c.strip() for c in reader.fieldnames}
        if missing:
            raise InvalidTargetsFileError(
                f"targets file {p} missing columns: {sorted(missing)}"
            )

        seen: set[tuple[str, str, str]] = set()
        targets: list[CityTarget] = []
        for row_num, row in enumerate(reader, start=2):
            vertical = (row.get("vertical") or "").strip()
            state = (row.get("state") or "").strip()
            city = (row.get("city") or "").strip()

            if not any((vertical, state, city)):
                continue
            if not (vertical and state and city):
                raise InvalidTargetsFileError(
                    f"{p}:{row_num} has an empty cell "
                    f"(vertical={vertical!r}, state={state!r}, city={city!r})"
                )

            key = (vertical, state, city)
            if key in seen:
                continue
            seen.add(key)
            targets.append(CityTarget(vertical=vertical, state=state, city=city))

    if not targets:
        raise InvalidTargetsFileError(f"targets file {p} yielded zero rows")

    return targets


__all__ = ["CityTarget", "InvalidTargetsFileError", "load_targets"]
