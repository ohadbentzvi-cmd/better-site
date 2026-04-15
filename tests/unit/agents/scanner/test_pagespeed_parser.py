"""Parse a real PageSpeed response shape and confirm every field extracts."""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.agents.scanner.checks.pagespeed import parse_pagespeed_response

FIXTURES = Path(__file__).parents[3] / "fixtures" / "scanner"


def _read(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestParseMobile:
    def test_category_scores(self) -> None:
        r = parse_pagespeed_response(_read("pagespeed_mobile_response.json"), strategy="mobile")
        assert r.performance_score == 42
        assert r.seo_score == 78
        assert r.best_practices_score == 85

    def test_core_web_vitals(self) -> None:
        r = parse_pagespeed_response(_read("pagespeed_mobile_response.json"), strategy="mobile")
        assert r.lcp_ms == 4800.0
        assert r.fcp_ms == 2800.0
        assert r.cls == 0.31
        assert r.tbt_ms == 650.0
        assert r.ttfb_ms == 420.0
        assert r.speed_index_ms == 5200.0

    def test_page_weight_is_int(self) -> None:
        r = parse_pagespeed_response(_read("pagespeed_mobile_response.json"), strategy="mobile")
        assert r.page_weight_bytes == 3_400_000

    def test_strategy_recorded(self) -> None:
        r = parse_pagespeed_response(_read("pagespeed_mobile_response.json"), strategy="mobile")
        assert r.strategy == "mobile"


class TestParseDesktop:
    def test_different_scores_from_mobile(self) -> None:
        mobile = parse_pagespeed_response(_read("pagespeed_mobile_response.json"), strategy="mobile")
        desktop = parse_pagespeed_response(_read("pagespeed_desktop_response.json"), strategy="desktop")
        assert desktop.performance_score == 68
        assert desktop.performance_score > mobile.performance_score


class TestParseMissingFields:
    def test_missing_everything_returns_none_values(self) -> None:
        r = parse_pagespeed_response({}, strategy="mobile")
        assert r.performance_score is None
        assert r.lcp_ms is None
        assert r.page_weight_bytes is None

    def test_partial_response_survives(self) -> None:
        raw = {"lighthouseResult": {"categories": {"performance": {"score": 0.5}}}}
        r = parse_pagespeed_response(raw, strategy="mobile")
        assert r.performance_score == 50
        assert r.lcp_ms is None  # audit missing
        assert r.tbt_ms is None
