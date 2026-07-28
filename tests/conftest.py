"""Shared fixtures: small synthetic event logs written to disk."""

from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

# Three cases over a strictly sequential process, plus one case that skips a
# step -- enough for two variants without making the expected numbers hard to
# check by hand.
TRACES: list[list[str]] = [
    ["register", "check", "approve", "archive"],
    ["register", "check", "approve", "archive"],
    ["register", "check", "approve", "archive"],
    ["register", "approve", "archive"],
]

START = datetime(2026, 1, 1, 9, 0, tzinfo=UTC)


def _rows(case_col: str, activity_col: str, timestamp_col: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for case_index, trace in enumerate(TRACES):
        for step, activity in enumerate(trace):
            moment = START + timedelta(days=case_index, hours=step)
            rows.append(
                {
                    case_col: f"case-{case_index}",
                    activity_col: activity,
                    timestamp_col: moment.isoformat(),
                }
            )
    return rows


@pytest.fixture
def xes_log(tmp_path: Path) -> Path:
    """A minimal XES file using the standard concept:name / time:timestamp keys."""
    events = _rows("case", "concept:name", "time:timestamp")
    by_case: dict[str, list[dict[str, str]]] = {}
    for event in events:
        by_case.setdefault(event["case"], []).append(event)

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<log xes.version="1.0" xmlns="http://www.xes-standard.org/">',
    ]
    for case_id, case_events in by_case.items():
        parts.append("\t<trace>")
        parts.append(f'\t\t<string key="concept:name" value="{case_id}"/>')
        for event in case_events:
            parts.append("\t\t<event>")
            parts.append(
                f'\t\t\t<string key="concept:name" value="{event["concept:name"]}"/>'
            )
            parts.append(
                f'\t\t\t<date key="time:timestamp" value="{event["time:timestamp"]}"/>'
            )
            parts.append("\t\t</event>")
        parts.append("\t</trace>")
    parts.append("</log>")

    path = tmp_path / "sample.xes"
    path.write_text("\n".join(parts), encoding="utf-8")
    return path


@pytest.fixture
def csv_log(tmp_path: Path) -> Path:
    """A CSV log with non-standard column names, needing an explicit mapping."""
    rows = _rows("Case ID", "Activity", "Timestamp")
    path = tmp_path / "sample.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["Case ID", "Activity", "Timestamp"])
        writer.writeheader()
        writer.writerows(rows)
    return path
