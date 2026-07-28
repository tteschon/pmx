"""Loading event logs from disk into the dataframe shape pm4py expects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

XES_SUFFIXES = frozenset({".xes", ".gz"})
CSV_SUFFIXES = frozenset({".csv", ".tsv"})

DEFAULT_CASE_ID = "case:concept:name"
DEFAULT_ACTIVITY = "concept:name"
DEFAULT_TIMESTAMP = "time:timestamp"


class LogError(Exception):
    """A log could not be read, or is missing the columns pm4py needs."""


@dataclass(frozen=True)
class ColumnMap:
    """Which columns in the source file carry case, activity, and timestamp.

    The defaults are the XES standard names, which is what a `.xes` file
    already uses and what every pm4py function expects by default.
    """

    case_id: str = DEFAULT_CASE_ID
    activity: str = DEFAULT_ACTIVITY
    timestamp: str = DEFAULT_TIMESTAMP

    @property
    def is_xes_standard(self) -> bool:
        return (
            self.case_id == DEFAULT_CASE_ID
            and self.activity == DEFAULT_ACTIVITY
            and self.timestamp == DEFAULT_TIMESTAMP
        )


@dataclass(frozen=True)
class EventLog:
    """An event log plus the column names to pass back into pm4py.

    After `read_log` the frame is always in XES-standard column naming, so
    `columns` is only kept around to report what the source file looked like.
    """

    frame: pd.DataFrame
    columns: ColumnMap
    source: Path


def read_log(
    path: Path,
    columns: ColumnMap | None = None,
    separator: str = ",",
) -> EventLog:
    """Read `path` as an event log and normalise it to XES column names.

    `.xes` and `.xes.gz` are read by pm4py directly. Anything else is treated
    as delimited text, where `columns` says which fields to use -- a CSV that
    already uses XES names needs no mapping.
    """
    import pandas as pd
    import pm4py

    columns = columns or ColumnMap()
    if not path.exists():
        raise LogError(f"no such file: {path}")

    if _is_xes(path):
        try:
            frame = pm4py.read_xes(str(path))
        except Exception as exc:  # pm4py raises a grab-bag of parser errors
            raise LogError(f"could not parse {path} as XES: {exc}") from exc
    else:
        try:
            frame = pd.read_csv(path, sep=separator)
        except Exception as exc:
            raise LogError(f"could not parse {path} as delimited text: {exc}") from exc
        _require_columns(frame, columns, path)
        frame = pm4py.format_dataframe(
            frame,
            case_id=columns.case_id,
            activity_key=columns.activity,
            timestamp_key=columns.timestamp,
        )

    if not isinstance(frame, pd.DataFrame):
        frame = pm4py.convert_to_dataframe(frame)

    _require_columns(frame, ColumnMap(), path)
    return EventLog(frame=frame, columns=columns, source=path)


def _is_xes(path: Path) -> bool:
    suffixes = [s.lower() for s in path.suffixes]
    return bool(suffixes) and (
        suffixes[-1] == ".xes" or suffixes[-2:] == [".xes", ".gz"]
    )


def _require_columns(frame: pd.DataFrame, columns: ColumnMap, path: Path) -> None:
    wanted = {
        "case id": columns.case_id,
        "activity": columns.activity,
        "timestamp": columns.timestamp,
    }
    missing = {role: name for role, name in wanted.items() if name not in frame.columns}
    if not missing:
        return
    detail = ", ".join(f"{role} column {name!r}" for role, name in missing.items())
    available = ", ".join(str(c) for c in frame.columns[:15])
    raise LogError(
        f"{path} is missing {detail}. Columns present: {available}. "
        "Pass --case-id/--activity-key/--timestamp-key to map them."
    )
