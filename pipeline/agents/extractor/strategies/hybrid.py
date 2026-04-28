"""Hybrid extraction strategy.

BS4 + colorthief for everything first. Claude vision is called ONLY as a
fallback for logo detection when the HTML heuristic returns low confidence
(no <header> image, no "logo" filename match, no SVG inline). Should hit
vision on ~20-30% of leads.
"""

from __future__ import annotations

from pipeline.agents.extractor.base import ExtractionResult, ExtractionStrategy
from pipeline.agents.extractor.registry import register


@register
class HybridStrategy(ExtractionStrategy):
    name = "hybrid"

    def extract(
        self,
        url: str,
        html: str,
        screenshot_png: bytes,
    ) -> ExtractionResult:
        # TODO: implement in Phase 3
        # 1. Run HtmlOnlyStrategy-equivalent logic
        # 2. If logo confidence is low, call Claude vision with a focused
        #    prompt ("which region of this screenshot is the logo?")
        # 3. Return the merged result
        raise NotImplementedError("HybridStrategy.extract is not yet implemented")
