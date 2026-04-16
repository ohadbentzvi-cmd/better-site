"""CLI wrapper for the batch lead-generation flow.

The target list lives in ``pipeline/targets/movers_us.csv``. Edit the CSV to
change what gets scraped. For large runs, split into smaller CSVs (~50 rows
each) so a crash only forfeits one chunk of work.

Run with defaults:
    python -m scripts.seed_cities

Run with a different targets file:
    python -m scripts.seed_cities --targets pipeline/targets/movers_small.csv
"""

from __future__ import annotations

import argparse
import asyncio

from pipeline.flows.lead_generator_batch import generate_leads_batch


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="bbb")
    ap.add_argument(
        "--targets",
        default="pipeline/targets/movers_us.csv",
        help="Path to the targets CSV (columns: vertical,state,city).",
    )
    ap.add_argument(
        "--max-pages-per-city",
        type=int,
        default=None,
        help="Cap search pages per city. Default: walk until exhausted.",
    )
    ap.add_argument(
        "--abort-on-repeated-block",
        type=int,
        default=2,
        help="Halt the batch after this many BBB 403s in one run.",
    )
    return ap.parse_args()


async def _run(args: argparse.Namespace) -> None:
    result = await generate_leads_batch(
        source=args.source,
        targets_csv=args.targets,
        max_pages_per_city=args.max_pages_per_city,
        abort_on_repeated_block=args.abort_on_repeated_block,
    )
    print("\n=== Batch complete ===")
    print(f"  cities:           {result['city_count']}")
    print(f"  completed:        {result['cities_completed']}")
    print(f"  failed:           {result['cities_failed']}")
    print(f"  blocked:          {result['cities_blocked']}")
    print(f"  aborted:          {result['cities_aborted']}")
    for k, v in result["totals"].items():
        print(f"  {k:<32} {v}")


if __name__ == "__main__":
    asyncio.run(_run(_parse_args()))
