"""Seed list of US cities for Lead Generator runs.

Hardcoded for POC. Tweak freely. When the list grows or gets per-vertical,
promote to a config file or a DB table.

Run against all seeded cities:
    python -m scripts.seed_cities --vertical movers
"""

from __future__ import annotations

import argparse
import asyncio

from pipeline.flows.lead_generator import generate_leads

# (city, state) pairs — medium-to-large US metros, diversified regionally.
SEED_CITIES: list[tuple[str, str]] = [
    ("Houston", "TX"),
    ("Dallas", "TX"),
    ("Austin", "TX"),
    ("Phoenix", "AZ"),
    ("Denver", "CO"),
    ("Seattle", "WA"),
    ("Portland", "OR"),
    ("San Diego", "CA"),
    ("Sacramento", "CA"),
    ("Atlanta", "GA"),
    ("Charlotte", "NC"),
    ("Nashville", "TN"),
    ("Columbus", "OH"),
    ("Indianapolis", "IN"),
    ("Minneapolis", "MN"),
    ("Kansas City", "MO"),
    ("St. Louis", "MO"),
    ("Tampa", "FL"),
    ("Orlando", "FL"),
    ("Las Vegas", "NV"),
]


async def _run_all(vertical: str, source: str, max_pages: int | None) -> None:
    for city, state in SEED_CITIES:
        print(f"\n=== {source} / {vertical} / {city}, {state} ===")
        summary = await generate_leads(
            source=source, vertical=vertical, state=state, city=city, max_pages=max_pages
        )
        for k, v in summary.items():
            print(f"  {k:<32} {v}")


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="bbb")
    ap.add_argument("--vertical", default="movers")
    ap.add_argument("--max-pages", type=int, default=None)
    return ap.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(_run_all(args.vertical, args.source, args.max_pages))
