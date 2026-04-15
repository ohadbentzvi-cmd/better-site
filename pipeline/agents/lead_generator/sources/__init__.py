"""Registry of available ``LeadSource`` implementations.

Adding a new source is:
    1. Implement ``LeadSource`` under this directory.
    2. Register it in ``SOURCES`` below.
Nothing else in the pipeline or the flow needs to change.
"""

from __future__ import annotations

from pipeline.agents.lead_generator.base import LeadSource
from pipeline.agents.lead_generator.sources.bbb import BBBSource

SOURCES: dict[str, type[LeadSource]] = {
    "bbb": BBBSource,
}


def get_source(name: str) -> LeadSource:
    try:
        cls = SOURCES[name]
    except KeyError as e:
        raise ValueError(
            f"unknown lead source {name!r}. Registered: {sorted(SOURCES)}"
        ) from e
    return cls()


__all__ = ["SOURCES", "get_source", "BBBSource"]
