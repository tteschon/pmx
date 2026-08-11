from __future__ import annotations

from pathlib import Path

import pytest

from pmx.logs import read_log
from pmx.stats import summarize


def test_summary_counts_match_the_fixture(xes_log: Path) -> None:
    summary = summarize(read_log(xes_log))

    assert summary.events == 15
    assert summary.cases == 4
    assert summary.activities == 4
    # Three identical traces plus one that skips "check".
    assert summary.variants == 2
    assert summary.top_activities["register"] == 4
    assert summary.start_activities == {"register": 4}
    assert summary.end_activities == {"archive": 4}


def test_variant_labels_are_arrow_joined(xes_log: Path) -> None:
    summary = summarize(read_log(xes_log))

    assert "register -> check -> approve -> archive" in summary.top_variants


def test_top_truncates_each_distribution(xes_log: Path) -> None:
    summary = summarize(read_log(xes_log), top=2)

    assert len(summary.top_activities) == 2
    # The counts above it are still exact -- only the listings are truncated.
    assert summary.activities == 4


def test_summary_is_json_serialisable(xes_log: Path) -> None:
    import json

    payload = json.loads(json.dumps(summarize(read_log(xes_log)).as_dict()))

    assert payload["cases"] == 4
    assert payload["first_event"].startswith("2026-01-01")


def test_variant_concentration(wide_log: Path) -> None:
    summary = summarize(read_log(wide_log))

    assert summary.cases == 20
    assert summary.variants == 7
    assert summary.variants_for_50pct == 1
    assert summary.variants_for_80pct == 3
    assert summary.variants_for_95pct == 6
    assert summary.singleton_variants == 4


def test_concentration_uses_all_variants_not_just_the_top(wide_log: Path) -> None:
    """The percentiles must survive `--top` truncating the listing."""
    summary = summarize(read_log(wide_log), top=2)

    assert len(summary.top_variants) == 2
    assert summary.variants_for_95pct == 6
    assert summary.singleton_variants == 4


def test_reordered_variants_collapse_to_one_activity_set(wide_log: Path) -> None:
    """abcd and acbd are the same work concurrently, so they share a set."""
    summary = summarize(read_log(wide_log))

    assert summary.variants == 7
    assert summary.distinct_activity_sets == 6


def test_case_durations(wide_log: Path) -> None:
    summary = summarize(read_log(wide_log))

    # 20 cases sorting to 7200 x2, 10800 x14, 172800 x3, 345600 x1.
    assert summary.min_case_duration_seconds == 7200.0
    assert summary.median_case_duration_seconds == 10800.0
    assert summary.p90_case_duration_seconds == 172800.0
    assert summary.max_case_duration_seconds == 345600.0
    assert summary.mean_case_duration_seconds == pytest.approx(51480.0)


RECEIPT = Path(__file__).resolve().parents[1] / "examples" / "data" / "receipt.xes"


@pytest.mark.skipif(
    not RECEIPT.exists(), reason="run examples/fetch-sample-logs.sh to enable"
)
def test_receipt_log_statistics() -> None:
    """Pin the numbers the README and skill docs quote for the sample log.

    `examples/data/` is gitignored, so this is skipped rather than failing on a
    fresh clone -- but where the data is present it stops the documented
    figures drifting silently.
    """
    summary = summarize(read_log(RECEIPT))

    assert (summary.cases, summary.events, summary.variants) == (1434, 8577, 116)
    assert summary.variants_for_50pct == 2
    assert summary.variants_for_80pct == 6
    assert summary.variants_for_95pct == 45
    assert summary.singleton_variants == 86
    assert summary.distinct_activity_sets == 50


def test_single_event_cases_have_zero_duration(tmp_path: Path) -> None:
    """A case with one event lasted no time -- that is 0.0, not unknown."""
    path = tmp_path / "single.csv"
    path.write_text(
        "case:concept:name,concept:name,time:timestamp\n"
        "c1,only,2026-01-01T09:00:00+00:00\n",
        encoding="utf-8",
    )
    summary = summarize(read_log(path))

    assert summary.cases == 1
    assert summary.median_case_duration_seconds == 0.0
    assert summary.max_case_duration_seconds == 0.0
