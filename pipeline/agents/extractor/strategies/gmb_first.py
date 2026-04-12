"""GMB-first extraction strategy.

Google Business Profile is the primary source of truth (logo, photos, hours,
phone, address). Website scraping is the fallback for things GMB doesn't
have (service descriptions, testimonials, about copy). Claude vision is only
used when GMB has no color data — optional.
"""

from __future__ import annotations

from pipeline.agents.extractor.base import ExtractionResult, ExtractionStrategy
from pipeline.agents.extractor.registry import register


@register
class GmbFirstStrategy(ExtractionStrategy):
    name = "gmb_first"

    def extract(
        self,
        url: str,
        html: str,
        screenshot_path: str,
    ) -> ExtractionResult:
        # TODO: implement in Phase 3
        # 1. Google Places API lookup by canonical_domain or business_name + city
        # 2. Pull GMB logo, primary photo, phone, address, hours
        # 3. BeautifulSoup fallback for about copy, services
        # 4. colorthief from GMB primary photo (or screenshot fallback)
        raise NotImplementedError("GmbFirstStrategy.extract is not yet implemented")
