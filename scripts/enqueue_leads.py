"""Cold-email channel entrypoint — enqueue leads into the pipeline.

The POC has no public self-serve surface, so leads enter the pipeline via
this script. Called manually or on a cron.

Usage:
    python scripts/enqueue_leads.py --vertical movers --city "Austin, TX" --country US --limit 100

Phase 2 implementation TODO.
"""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Enqueue leads into the BetterSite pipeline")
    parser.add_argument("--vertical", required=True, help="Industry vertical (e.g. movers)")
    parser.add_argument("--city", required=True, help='City name (e.g. "Austin, TX")')
    parser.add_argument("--country", required=True, help="ISO alpha-2 country code")
    parser.add_argument("--limit", type=int, default=100, help="Max leads to enqueue")
    args = parser.parse_args()

    print(f"[TODO] would enqueue {args.limit} {args.vertical} leads in {args.city}, {args.country}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
