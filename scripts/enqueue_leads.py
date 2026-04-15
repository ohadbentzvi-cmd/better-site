"""Trigger a one-off ``lead-generation`` flow run.

Useful while scheduled flows aren't live yet. Invokes the flow directly
in-process against the configured Prefect server.

    python -m scripts.enqueue_leads --source bbb --vertical movers \\
        --state TX --city Houston [--max-pages 5]
"""

from __future__ import annotations

import argparse
import asyncio

from pipeline.flows.lead_generator import generate_leads


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", default="bbb", help="Registered lead source (default: bbb)")
    ap.add_argument("--vertical", default="movers", help="Internal vertical tag (default: movers)")
    ap.add_argument("--state", required=True, help="ISO 3166-2 subdivision, e.g. TX")
    ap.add_argument("--city", required=True, help="City name, e.g. Houston")
    ap.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional cap on search-result pages (default: walk until empty)",
    )
    return ap.parse_args()


async def _main() -> None:
    args = _parse_args()
    summary = await generate_leads(
        source=args.source,
        vertical=args.vertical,
        state=args.state,
        city=args.city,
        max_pages=args.max_pages,
    )
    for k, v in summary.items():
        print(f"{k:<32} {v}")


if __name__ == "__main__":
    asyncio.run(_main())
