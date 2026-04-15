"""Lead Generator agent — source-pluggable ingestion for ``ops.leads``."""

from pipeline.agents.lead_generator.base import (
    LeadSource,
    RawLead,
)
from pipeline.agents.lead_generator.pipeline import ingest_raw_lead, run_source

__all__ = ["LeadSource", "RawLead", "ingest_raw_lead", "run_source"]
