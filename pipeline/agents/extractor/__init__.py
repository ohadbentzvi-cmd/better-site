"""Information Extractor — pluggable strategy pattern.

Import side-effects register every strategy on the registry.
"""

from pipeline.agents.extractor.base import ExtractionResult, ExtractionStrategy
from pipeline.agents.extractor.registry import get_strategy, list_strategies
from pipeline.agents.extractor.strategies import (  # noqa: F401 — registration side-effects
    gmb_first,
    html_only,
    hybrid,
    vision_full,
)

__all__ = ["ExtractionResult", "ExtractionStrategy", "get_strategy", "list_strategies"]
