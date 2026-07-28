"""Summary statistics for an event log -- what `pmx inspect` reports."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from pmx.logs import DEFAULT_ACTIVITY, DEFAULT_CASE_ID, DEFAULT_TIMESTAMP, EventLog


@dataclass(frozen=True)
class Summary:
    """A profile of one event log.

    Counts are exact; the `top_*` mappings are truncated to the size asked for
    at build time, so they describe the head of a distribution, not all of it.
    """

    source: str
    events: int
    cases: int
    activities: int
    variants: int
    first_event: str | None
    last_event: str | None
    top_activities: dict[str, int] = field(default_factory=dict)
    start_activities: dict[str, int] = field(default_factory=dict)
    end_activities: dict[str, int] = field(default_factory=dict)
    top_variants: dict[str, int] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def summarize(log: EventLog, top: int = 10) -> Summary:
    """Profile `log`, keeping the `top` most frequent entries per distribution."""
    import pm4py

    frame = log.frame
    activities = pm4py.get_event_attribute_values(frame, DEFAULT_ACTIVITY)
    variants = pm4py.get_variants(frame)
    timestamps = frame[DEFAULT_TIMESTAMP]

    return Summary(
        source=str(log.source),
        events=int(len(frame)),
        cases=int(frame[DEFAULT_CASE_ID].nunique()),
        activities=len(activities),
        variants=len(variants),
        first_event=_isoformat(timestamps.min()) if len(frame) else None,
        last_event=_isoformat(timestamps.max()) if len(frame) else None,
        top_activities=_top(activities, top),
        start_activities=_top(pm4py.get_start_activities(frame), top),
        end_activities=_top(pm4py.get_end_activities(frame), top),
        top_variants=_top({_variant_label(k): v for k, v in variants.items()}, top),
    )


def _variant_label(variant: Any) -> str:
    """Render a variant key as an arrow-joined path.

    pm4py returns tuples of activity names for dataframes and has historically
    returned pre-joined strings, so accept either.
    """
    if isinstance(variant, tuple):
        return " -> ".join(str(step) for step in variant)
    return str(variant)


def _top(counts: dict[Any, Any], n: int) -> dict[str, int]:
    ranked = sorted(counts.items(), key=lambda kv: (-_count(kv[1]), str(kv[0])))
    return {str(k): _count(v) for k, v in ranked[:n]}


def _count(value: Any) -> int:
    """Coerce a pm4py count to `int`.

    Variant values are sometimes a list of the matching cases rather than a
    number, depending on which pm4py path produced them.
    """
    if isinstance(value, (list, tuple, set)):
        return len(value)
    return int(value)


def _isoformat(value: Any) -> str:
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else str(value)
