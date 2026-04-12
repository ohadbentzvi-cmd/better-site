"""Extractor strategy protocol + shared result type.

Every strategy implements the same ``extract()`` signature. The runtime
choice is controlled by the ``EXTRACTION_STRATEGY`` env var.

Adding a new strategy:
1. Create a module in ``strategies/``
2. Define a class inheriting ``ExtractionStrategy``
3. Import it in ``strategies/__init__.py`` so the registry picks it up
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExtractionResult:
    """Structured output from any ExtractionStrategy.

    The Builder maps this into the vertical template's ``content.schema.json``.
    Missing fields use ``None`` — the template is responsible for graceful
    degradation (text wordmark, stock hero, template default colors).
    """

    # Identity
    business_name: str | None = None
    tagline: str | None = None

    # Contact
    phone: str | None = None
    email: str | None = None
    address: str | None = None

    # Copy
    about: str | None = None
    services: list[str] = field(default_factory=list)

    # Social
    social_links: dict[str, str] = field(default_factory=dict)

    # Visual assets — R2 keys, not raw bytes
    logo_r2_key: str | None = None
    hero_r2_key: str | None = None
    brand_colors: list[str] = field(default_factory=list)  # hex strings

    # Provenance
    strategy_name: str = ""
    vision_model_version: str | None = None
    cost_usd: float = 0.0


class ExtractionStrategy(ABC):
    """Abstract base for all Extractor strategies."""

    name: str  # must be set on each concrete subclass

    @abstractmethod
    def extract(
        self,
        url: str,
        html: str,
        screenshot_path: str,
    ) -> ExtractionResult:
        """Produce an ExtractionResult from the given site inputs.

        Inputs are pre-fetched by the Extractor flow so every strategy sees
        identical raw materials — that makes the manual comparison fair.

        Raises:
            ExtractionStrategyError: on any recoverable failure; the Extractor
                flow will log the error in the ``events`` table and either
                retry or fall back to GMB data.
        """


class ExtractionStrategyError(Exception):
    """Base class for strategy-specific failures."""
