from __future__ import annotations

from pathlib import Path

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
