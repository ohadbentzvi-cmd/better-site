"""Fixture-based tests for the BBB parser.

If BBB changes their markup in production, the first signal is one of
these tests failing — not a silent zero-leads-scraped in the flow.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.agents.lead_generator.sources.bbb import (
    parse_profile_page,
    parse_search_page,
)

FIXTURES = Path(__file__).parents[3] / "fixtures" / "bbb"


def _read(name: str) -> str:
    return (FIXTURES / name).read_text()


class TestParseSearchPage:
    def test_extracts_expected_three_cards(self) -> None:
        stubs = list(parse_search_page(_read("search_houston_moving_p1.html")))
        names = [s.name for s in stubs]
        assert names == ["Westheimer Transfer", "Apple Moving", "Lone Star Movers"]

    def test_skips_ui_artifact_links(self) -> None:
        stubs = list(parse_search_page(_read("search_houston_moving_p1.html")))
        assert "Get a Quote" not in [s.name for s in stubs]

    def test_profile_urls_are_absolute(self) -> None:
        stubs = list(parse_search_page(_read("search_houston_moving_p1.html")))
        for s in stubs:
            assert s.profile_url.startswith("https://www.bbb.org/")

    def test_phones_extracted(self) -> None:
        stubs = list(parse_search_page(_read("search_houston_moving_p1.html")))
        phones = [s.phone for s in stubs]
        assert phones == ["(713) 555-0192", "(281) 555-7788", "(832) 555-0042"]

    def test_ratings_extracted(self) -> None:
        stubs = list(parse_search_page(_read("search_houston_moving_p1.html")))
        assert [s.bbb_rating for s in stubs] == ["A+", "A", "B+"]

    def test_accreditation_flag(self) -> None:
        stubs = list(parse_search_page(_read("search_houston_moving_p1.html")))
        assert [s.accredited for s in stubs] == [True, False, True]

    def test_addresses_extracted(self) -> None:
        stubs = list(parse_search_page(_read("search_houston_moving_p1.html")))
        assert stubs[0].address_raw is not None
        assert "Westheimer" in stubs[0].address_raw

    def test_empty_page_returns_no_stubs(self) -> None:
        stubs = list(parse_search_page(_read("search_empty.html")))
        assert stubs == []


class TestParseProfilePage:
    def test_website_from_json_ld(self) -> None:
        detail = parse_profile_page(_read("profile_westheimer_transfer.html"))
        assert detail.website_url == "https://www.westheimertransfer.com"

    def test_email_from_mailto(self) -> None:
        detail = parse_profile_page(_read("profile_westheimer_transfer.html"))
        assert detail.email == "hello@westheimertransfer.com"

    def test_years_in_business(self) -> None:
        detail = parse_profile_page(_read("profile_westheimer_transfer.html"))
        assert detail.years_in_business == "37"

    def test_no_website_returns_none(self) -> None:
        detail = parse_profile_page(_read("profile_no_website.html"))
        assert detail.website_url is None

    def test_bbb_links_are_filtered_out(self) -> None:
        # JSON-LD must point to the external site, not bbb.org.
        detail = parse_profile_page(_read("profile_westheimer_transfer.html"))
        assert "bbb.org" not in (detail.website_url or "")


class TestRawLeadAssembly:
    def test_end_to_end_shape(self) -> None:
        """Parse search → parse profile → assemble RawLead (no network)."""
        from pipeline.agents.lead_generator.sources.bbb import _to_raw_lead

        stubs = list(parse_search_page(_read("search_houston_moving_p1.html")))
        detail = parse_profile_page(_read("profile_westheimer_transfer.html"))
        raw = _to_raw_lead(
            vertical="movers",
            state="TX",
            city="Houston",
            stub=stubs[0],
            detail=detail,
        )
        assert raw.business_name == "Westheimer Transfer"
        assert raw.website_url == "https://www.westheimertransfer.com"
        assert raw.email == "hello@westheimertransfer.com"
        assert raw.email_source == "bbb"
        assert raw.source == "bbb"
        assert raw.state == "TX"
        assert raw.city == "Houston"
        assert raw.country == "US"
        assert raw.source_metadata["bbb_rating"] == "A+"
        assert raw.source_metadata["accredited"] is True
        assert raw.source_metadata["years_in_business"] == "37"
        assert raw.source_metadata["bbb_profile_url"].startswith("https://www.bbb.org/")


@pytest.mark.parametrize("fixture_name", ["search_houston_moving_p1.html", "search_empty.html"])
def test_search_parser_is_total(fixture_name: str) -> None:
    """Parser must never raise on any fixture — unexpected shapes yield 0, not exceptions."""
    list(parse_search_page(_read(fixture_name)))
