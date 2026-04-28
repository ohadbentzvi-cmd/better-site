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

from pydantic import BaseModel, Field


class ServiceBlurb(BaseModel):
    """One service offered by the business."""

    name: str
    blurb: str | None = None


class Testimonial(BaseModel):
    """A single customer testimonial."""

    quote: str
    author: str | None = None
    source: str | None = None


class ExtractionResult(BaseModel):
    """Structured output from any ExtractionStrategy.

    The Builder maps this into the vertical template's ``content.schema.json``.
    Missing fields use ``None`` / empty collections — the template is
    responsible for graceful degradation (text wordmark, stock hero,
    template default colors).
    """

    # Identity
    business_name: str | None = None
    tagline: str | None = None
    cta_text: str | None = None

    # Trust
    years_in_business: int | None = None
    license_numbers: list[str] = Field(default_factory=list)

    # Contact
    phone: str | None = None
    email: str | None = None
    address: str | None = None
    hours: dict[str, str] = Field(default_factory=dict)

    # Copy
    about: str | None = None
    services: list[ServiceBlurb] = Field(default_factory=list)
    service_areas: list[str] = Field(default_factory=list)
    testimonials: list[Testimonial] = Field(default_factory=list)

    # Social
    social_links: dict[str, str] = Field(default_factory=dict)

    # Visual assets — R2 keys, not raw bytes
    logo_r2_key: str | None = None
    hero_r2_key: str | None = None
    brand_colors: list[str] = Field(default_factory=list)

    # Provenance
    strategy_name: str = ""
    vision_model_version: str | None = None
    prompt_version: str | None = None
    cost_usd: float = 0.0


class ExtractionStrategy(ABC):
    """Abstract base for all Extractor strategies."""

    name: str  # must be set on each concrete subclass

    @abstractmethod
    def extract(
        self,
        url: str,
        html: str,
        screenshot_png: bytes,
    ) -> ExtractionResult:
        """Produce an ExtractionResult from the given site inputs.

        Inputs are pre-fetched by the Extractor flow so every strategy sees
        identical raw materials — that makes the manual comparison fair.

        ``screenshot_png`` is the desktop full-page screenshot bytes;
        strategies that need a tempfile should write it themselves.

        Raises:
            ExtractionStrategyError: on any recoverable failure; the Extractor
                flow will log the error in the ``events`` table and either
                retry or fall back to GMB data.
        """


class ExtractionStrategyError(Exception):
    """Base class for strategy-specific failures."""
