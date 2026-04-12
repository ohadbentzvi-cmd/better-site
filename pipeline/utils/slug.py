"""Preview slug generation.

Slugs must be unguessable (not sequential). We use nanoid(12) which gives
~71 bits of entropy — collision probability is negligible for our volume.
"""

from __future__ import annotations

from nanoid import generate  # type: ignore[import-untyped]

SLUG_ALPHABET = "23456789abcdefghijkmnpqrstuvwxyz"  # no ambiguous chars (0/O, 1/l)
SLUG_SIZE = 12


def generate_slug() -> str:
    """Return a new random, unguessable preview slug."""
    return generate(SLUG_ALPHABET, SLUG_SIZE)
