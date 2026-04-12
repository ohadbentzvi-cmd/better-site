"""Strategy registry — strategies register themselves by name at import time."""

from __future__ import annotations

from pipeline.agents.extractor.base import ExtractionStrategy

_REGISTRY: dict[str, type[ExtractionStrategy]] = {}


def register(cls: type[ExtractionStrategy]) -> type[ExtractionStrategy]:
    """Decorator that registers a strategy class by its ``name`` attribute."""
    if not getattr(cls, "name", None):
        raise ValueError(f"{cls.__name__} must set a class-level ``name``")
    if cls.name in _REGISTRY:
        raise ValueError(f"duplicate strategy name: {cls.name!r}")
    _REGISTRY[cls.name] = cls
    return cls


def get_strategy(name: str) -> ExtractionStrategy:
    """Instantiate and return the strategy registered under ``name``.

    Raises KeyError if the strategy is not registered.
    """
    if name not in _REGISTRY:
        raise KeyError(
            f"unknown extraction strategy {name!r}; "
            f"registered: {sorted(_REGISTRY.keys())}"
        )
    return _REGISTRY[name]()


def list_strategies() -> list[str]:
    """Return the sorted list of registered strategy names."""
    return sorted(_REGISTRY.keys())
