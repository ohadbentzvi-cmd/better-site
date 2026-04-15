"""Trigger a one-off ``site-scan`` flow run.

Two modes, mutually exclusive:

    python -m scripts.scan_urls --url https://westheimertransfer.com
    python -m scripts.scan_urls --urls-file urls.txt
    python -m scripts.scan_urls --from-leads --limit 20
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from pipeline.flows.scanner import scan_sites


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--url", action="append", help="Single URL (repeatable)")
    group.add_argument("--urls-file", type=Path, help="File with one URL per line")
    group.add_argument(
        "--from-leads",
        action="store_true",
        help="Pull unscanned leads from ops.leads",
    )
    ap.add_argument("--limit", type=int, default=50, help="Leads-mode cap (default 50)")
    return ap.parse_args()


async def _main() -> None:
    args = _parse_args()

    urls: list[str] | None
    if args.from_leads:
        urls = None
    elif args.urls_file:
        urls = [line.strip() for line in args.urls_file.read_text().splitlines() if line.strip()]
    else:
        urls = list(args.url or [])

    summary = await scan_sites(urls=urls, limit=args.limit)
    for k, v in summary.items():
        print(f"{k:<32} {v}")


if __name__ == "__main__":
    asyncio.run(_main())
