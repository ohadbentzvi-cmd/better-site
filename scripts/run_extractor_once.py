"""Run the Information Extractor against a single URL — no DB, no Prefect.

QA driver for manually evaluating an extraction strategy against real
movers homepages before the Prefect flow + persistence layer land.
Renders the page in chromium, runs the configured strategy, prints the
``ExtractionResult`` as pretty JSON, and reports R2 upload status.

    python -m scripts.run_extractor_once https://acme-movers.com
    python -m scripts.run_extractor_once https://acme-movers.com --strategy html_only

Strategy defaults to ``EXTRACTION_STRATEGY`` from the environment, or
``html_only`` if unset.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from pipeline.agents.extractor import get_strategy, list_strategies
from pipeline.config import get_settings
from pipeline.utils.browser import BrowserFetchError, render_page
from pipeline.utils.ssrf import UnsafeUrlError, assert_safe_url
from pipeline.utils.url import InvalidURLError, canonicalize_url


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url", help="Movers homepage URL to extract")
    ap.add_argument(
        "--strategy",
        default=None,
        help=f"Strategy name (default: EXTRACTION_STRATEGY env). Registered: {list_strategies()}",
    )
    return ap.parse_args()


async def _main() -> int:
    args = _parse_args()

    try:
        canonical = canonicalize_url(args.url)
    except InvalidURLError as e:
        print(f"invalid URL: {e}", file=sys.stderr)
        return 2

    try:
        assert_safe_url(canonical)
    except UnsafeUrlError as e:
        print(f"unsafe URL: {e}", file=sys.stderr)
        return 2

    strategy_name = args.strategy or get_settings().EXTRACTION_STRATEGY
    strategy = get_strategy(strategy_name)

    print(f"# url:      {canonical}", file=sys.stderr)
    print(f"# strategy: {strategy_name}", file=sys.stderr)
    print("# rendering page...", file=sys.stderr)

    try:
        rendered = await render_page(canonical)
    except BrowserFetchError as e:
        print(f"render failed: {e}", file=sys.stderr)
        return 3

    print(
        f"# rendered: html={len(rendered.html)}B "
        f"desktop_png={len(rendered.desktop_png)}B "
        f"mobile_png={len(rendered.mobile_png)}B",
        file=sys.stderr,
    )
    print("# extracting...", file=sys.stderr)

    result = strategy.extract(
        url=canonical,
        html=rendered.html,
        screenshot_png=rendered.desktop_png,
    )

    print(result.model_dump_json(indent=2))

    print("", file=sys.stderr)
    print(f"# logo_r2_key: {result.logo_r2_key or '(none)'}", file=sys.stderr)
    print(f"# hero_r2_key: {result.hero_r2_key or '(none)'}", file=sys.stderr)
    print(f"# brand_colors: {result.brand_colors}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
