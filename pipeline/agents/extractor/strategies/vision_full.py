"""Vision-first extraction strategy.

Uses Claude Sonnet 4.6 vision to identify logo, hero, and brand colors from
a screenshot. Text content still comes from BeautifulSoup. Highest
personalization ceiling, highest per-lead cost.

Prompt injection hardening: scraped content is wrapped in <UNTRUSTED_DATA>
tags before being passed to Claude.
"""

from __future__ import annotations

from pipeline.agents.extractor.base import ExtractionResult, ExtractionStrategy
from pipeline.agents.extractor.registry import register


@register
class VisionFullStrategy(ExtractionStrategy):
    name = "vision_full"

    def extract(
        self,
        url: str,
        html: str,
        screenshot_png: bytes,
    ) -> ExtractionResult:
        # TODO: implement in Phase 3
        # - BeautifulSoup parse for text fields
        # - Claude vision prompt (see pipeline/prompts/extractor/vision_full.py)
        #   with screenshot → logo region, hero region, brand colors
        # - Wrap scraped context in <UNTRUSTED_DATA> tags
        # - Enforce per-batch cost ceiling via pipeline.utils.cost_ceiling
        raise NotImplementedError("VisionFullStrategy.extract is not yet implemented")
