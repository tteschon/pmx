from __future__ import annotations

from pathlib import Path

import pytest

from pmx.logs import (
    DEFAULT_ACTIVITY,
    DEFAULT_CASE_ID,
    DEFAULT_TIMESTAMP,
    ColumnMap,
    LogError,
    read_log,
)


def test_reads_xes_with_standard_keys(xes_log: Path) -> None:
    log = read_log(xes_log)

    assert len(log.frame) == 15
    assert log.frame[DEFAULT_CASE_ID].nunique() == 4
    assert set(log.frame[DEFAULT_ACTIVITY]) == {
        "register",
        "check",
        "approve",
        "archive",
    }
    assert log.source == xes_log


def test_reads_csv_with_mapped_columns(csv_log: Path) -> None:
    log = read_log(
        csv_log,
        columns=ColumnMap(
            case_id="Case ID", activity="Activity", timestamp="Timestamp"
        ),
    )

    # format_dataframe renames into the XES standard, which is what every
    # downstream pm4py call assumes.
    for column in (DEFAULT_CASE_ID, DEFAULT_ACTIVITY, DEFAULT_TIMESTAMP):
        assert column in log.frame.columns
    assert len(log.frame) == 15


def test_missing_file_is_a_log_error(tmp_path: Path) -> None:
    with pytest.raises(LogError, match="no such file"):
        read_log(tmp_path / "absent.xes")


def test_wrong_column_mapping_names_the_missing_columns(csv_log: Path) -> None:
    with pytest.raises(LogError) as excinfo:
        read_log(csv_log, columns=ColumnMap(case_id="nope"))

    message = str(excinfo.value)
    assert "case id column 'nope'" in message
    assert "Case ID" in message  # the columns that are actually there


def test_column_map_knows_when_it_is_the_xes_default() -> None:
    assert ColumnMap().is_xes_standard
    assert not ColumnMap(case_id="Case ID").is_xes_standard
