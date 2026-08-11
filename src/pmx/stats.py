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

    Field names are the `--json` contract, since `as_dict` is a plain
    `dataclasses.asdict`.
    """

    source: str
    events: int
    cases: int
    activities: int
    variants: int
    first_event: str | None
    last_event: str | None

    # How concentrated the variants are. `variants_for_*` is the fewest
    # variants needed to account for that share of cases -- the number that
    # says whether a readable model is even possible, and what to pass to
    # `--top-variants`.
    variants_for_50pct: int | None = None
    variants_for_80pct: int | None = None
    variants_for_95pct: int | None = None
    singleton_variants: int = 0

    # Variants that are re-orderings of each other collapse to one activity
    # set. A count far below `variants` means the log's apparent complexity is
    # concurrency, which variant filtering fixes and `--noise-threshold` does
    # not.
    distinct_activity_sets: int = 0

    # Seconds, so the JSON carries no unit ambiguity. `None` only when there
    # are no cases at all; a single-event case is a real duration of 0.0.
    median_case_duration_seconds: float | None = None
    mean_case_duration_seconds: float | None = None
    p90_case_duration_seconds: float | None = None
    min_case_duration_seconds: float | None = None
    max_case_duration_seconds: float | None = None

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

    # Computed from the full variant mapping, before `_top` truncates it.
    counts = sorted((_count(v) for v in variants.values()), reverse=True)
    durations = _case_durations(frame)

    return Summary(
        source=str(log.source),
        events=int(len(frame)),
        cases=int(frame[DEFAULT_CASE_ID].nunique()),
        activities=len(activities),
        variants=len(variants),
        first_event=_isoformat(timestamps.min()) if len(frame) else None,
        last_event=_isoformat(timestamps.max()) if len(frame) else None,
        variants_for_50pct=_variants_for(counts, 0.5),
        variants_for_80pct=_variants_for(counts, 0.8),
        variants_for_95pct=_variants_for(counts, 0.95),
        singleton_variants=sum(1 for c in counts if c == 1),
        distinct_activity_sets=len({_activity_set(k) for k in variants}),
        median_case_duration_seconds=_percentile(durations, 0.5),
        mean_case_duration_seconds=(
            sum(durations) / len(durations) if durations else None
        ),
        p90_case_duration_seconds=_percentile(durations, 0.9),
        min_case_duration_seconds=durations[0] if durations else None,
        max_case_duration_seconds=durations[-1] if durations else None,
        top_activities=_top(activities, top),
        start_activities=_top(pm4py.get_start_activities(frame), top),
        end_activities=_top(pm4py.get_end_activities(frame), top),
        top_variants=_top({_variant_label(k): v for k, v in variants.items()}, top),
    )


def variant_case_counts(frame: Any) -> list[int]:
    """Case count per variant, descending. Shared with `pmx.filters`."""
    import pm4py

    return sorted((_count(v) for v in pm4py.get_variants(frame).values()), reverse=True)


def _variants_for(counts: list[int], share: float) -> int | None:
    """Fewest variants, taken most-frequent first, covering `share` of cases."""
    total = sum(counts)
    if not total:
        return None
    target = share * total
    cumulative = 0
    for index, count in enumerate(counts, start=1):
        cumulative += count
        if cumulative >= target:
            return index
    return len(counts)


def _activity_set(variant: Any) -> frozenset[str]:
    steps = variant if isinstance(variant, tuple) else str(variant).split(" -> ")
    return frozenset(str(step) for step in steps)


def _case_durations(frame: Any) -> list[float]:
    """Per-case elapsed seconds, ascending. Empty when the log has no rows."""
    if not len(frame):
        return []
    spans = frame.groupby(DEFAULT_CASE_ID)[DEFAULT_TIMESTAMP].agg(["min", "max"])
    seconds = (spans["max"] - spans["min"]).dt.total_seconds()
    return sorted(float(s) for s in seconds.dropna())


def _percentile(values: list[float], q: float) -> float | None:
    """Nearest-rank percentile over an already-sorted list."""
    if not values:
        return None
    index = min(len(values) - 1, max(0, round(q * (len(values) - 1))))
    return values[index]


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
