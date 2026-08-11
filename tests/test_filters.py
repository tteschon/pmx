"""Variant filtering: what gets kept, and what gets reported."""

from __future__ import annotations

from pathlib import Path

import pytest

from pmx.filters import top_variants, variants_covering
from pmx.logs import DEFAULT_CASE_ID, read_log


def test_top_variants_keeps_only_the_most_frequent(wide_log: Path) -> None:
    log = read_log(wide_log)
    filtered, report = top_variants(log, 1)

    assert report.kept_variants == 1
    assert report.total_variants == 7
    # The most frequent variant is 10 of the 20 cases.
    assert report.kept_cases == 10
    assert report.total_cases == 20
    assert report.case_share == 0.5
    assert filtered.frame[DEFAULT_CASE_ID].nunique() == 10


def test_top_variants_beyond_the_log_is_a_noop(wide_log: Path) -> None:
    log = read_log(wide_log)
    filtered, report = top_variants(log, 999)

    assert report.is_noop
    assert report.kept_cases == report.total_cases == 20
    assert filtered.frame is log.frame


def test_top_variants_rejects_zero(wide_log: Path) -> None:
    with pytest.raises(ValueError, match="at least 1"):
        top_variants(read_log(wide_log), 0)


@pytest.mark.parametrize(
    ("share", "expected_variants", "expected_cases"),
    [
        (0.5, 1, 10),  # the first variant alone reaches exactly 50%
        (0.8, 3, 16),  # 10 + 4 + 2, hitting 80% exactly on the third
        (0.95, 6, 19),
        (1.0, 7, 20),
    ],
)
def test_variants_covering_takes_the_fewest_needed(
    wide_log: Path, share: float, expected_variants: int, expected_cases: int
) -> None:
    """Covering X% means the smallest set of variants summing to X% of cases.

    Deliberately not pm4py's `filter_variants_by_coverage_percentage`, which
    keeps variants each individually above the share and would return nothing
    at 0.8 here.
    """
    _, report = variants_covering(read_log(wide_log), share)

    assert report.kept_variants == expected_variants
    assert report.kept_cases == expected_cases


def test_variants_covering_rejects_out_of_range(wide_log: Path) -> None:
    log = read_log(wide_log)
    for bad in (0.0, -0.1, 1.5):
        with pytest.raises(ValueError, match="share must be"):
            variants_covering(log, bad)


def test_filtering_shrinks_the_discovered_model(wide_log: Path) -> None:
    """The whole point of the feature: fewer variants, smaller model."""
    from pmx import discovery

    log = read_log(wide_log)
    full = discovery.discover(log)
    trimmed = discovery.discover(top_variants(log, 1)[0])

    assert isinstance(full.payload, tuple) and isinstance(trimmed.payload, tuple)
    assert len(trimmed.payload[0].transitions) < len(full.payload[0].transitions)
