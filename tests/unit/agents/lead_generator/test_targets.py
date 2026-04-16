"""Unit tests for the batch flow's CSV target loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from pipeline.agents.lead_generator.targets import (
    CityTarget,
    InvalidTargetsFileError,
    load_targets,
)


def _write_csv(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "targets.csv"
    path.write_text(content, encoding="utf-8")
    return path


class TestLoadTargets:
    def test_happy_path_parses_rows(self, tmp_path: Path) -> None:
        csv_path = _write_csv(
            tmp_path,
            "vertical,state,city\n"
            "movers,TX,Houston\n"
            "movers,GA,Atlanta\n",
        )
        targets = load_targets(csv_path)
        assert targets == [
            CityTarget(vertical="movers", state="TX", city="Houston"),
            CityTarget(vertical="movers", state="GA", city="Atlanta"),
        ]

    def test_strips_whitespace(self, tmp_path: Path) -> None:
        csv_path = _write_csv(
            tmp_path,
            "vertical,state,city\n"
            "  movers , TX , Houston  \n",
        )
        targets = load_targets(csv_path)
        assert targets == [CityTarget(vertical="movers", state="TX", city="Houston")]

    def test_dedupes_identical_triples(self, tmp_path: Path) -> None:
        csv_path = _write_csv(
            tmp_path,
            "vertical,state,city\n"
            "movers,TX,Houston\n"
            "movers,TX,Houston\n",
        )
        targets = load_targets(csv_path)
        assert targets == [CityTarget(vertical="movers", state="TX", city="Houston")]

    def test_skips_blank_rows(self, tmp_path: Path) -> None:
        csv_path = _write_csv(
            tmp_path,
            "vertical,state,city\n"
            "movers,TX,Houston\n"
            ",,\n"
            "movers,GA,Atlanta\n",
        )
        targets = load_targets(csv_path)
        assert len(targets) == 2

    def test_missing_column_raises(self, tmp_path: Path) -> None:
        csv_path = _write_csv(
            tmp_path,
            "vertical,city\n"
            "movers,Houston\n",
        )
        with pytest.raises(InvalidTargetsFileError, match="missing columns"):
            load_targets(csv_path)

    def test_partial_row_raises(self, tmp_path: Path) -> None:
        csv_path = _write_csv(
            tmp_path,
            "vertical,state,city\n"
            "movers,,Houston\n",
        )
        with pytest.raises(InvalidTargetsFileError, match="empty cell"):
            load_targets(csv_path)

    def test_empty_file_raises(self, tmp_path: Path) -> None:
        csv_path = _write_csv(tmp_path, "vertical,state,city\n")
        with pytest.raises(InvalidTargetsFileError, match="zero rows"):
            load_targets(csv_path)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(InvalidTargetsFileError, match="not found"):
            load_targets(tmp_path / "nope.csv")
