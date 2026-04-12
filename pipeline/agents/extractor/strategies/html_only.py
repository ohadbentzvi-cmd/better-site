"""HTML-only extraction strategy.

No Claude calls. Uses BeautifulSoup for text, colorthief for brand colors,
and simple heuristics for logo + hero image selection. Fully deterministic.
"""

from __future__ import annotations

from pipeline.agents.extractor.base import ExtractionResult, ExtractionStrategy
from pipeline.agents.extractor.registry import register


@register
class HtmlOnlyStrategy(ExtractionStrategy):
    name = "html_only"

    def extract(
        self,
        url: str,
        html: str,
        screenshot_path: str,
    ) -> ExtractionResult:
        # TODO: implement in Phase 3
        # - BeautifulSoup parse for business_name, phone, address, social_links, about, services
        # - colorthief palette extraction from screenshot_path
        # - Heuristic logo: first <img> in <header>/<nav>, or filename containing "logo"
        # - Heuristic hero: largest <img> in first viewport
        raise NotImplementedError("HtmlOnlyStrategy.extract is not yet implemented")
