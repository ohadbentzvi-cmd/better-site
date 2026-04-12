"""Sales agent backend registry."""

from __future__ import annotations

from pipeline.agents.sales.base import SalesAgentBackend

_REGISTRY: dict[str, type[SalesAgentBackend]] = {}


def register(cls: type[SalesAgentBackend]) -> type[SalesAgentBackend]:
    if not getattr(cls, "name", None):
        raise ValueError(f"{cls.__name__} must set a class-level ``name``")
    if cls.name in _REGISTRY:
        raise ValueError(f"duplicate backend name: {cls.name!r}")
    _REGISTRY[cls.name] = cls
    return cls


def get_backend(name: str) -> SalesAgentBackend:
    if name not in _REGISTRY:
        raise KeyError(
            f"unknown sales backend {name!r}; registered: {sorted(_REGISTRY.keys())}"
        )
    return _REGISTRY[name]()


def list_backends() -> list[str]:
    return sorted(_REGISTRY.keys())
