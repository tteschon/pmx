"""Directly-follows graphs: which activity actually follows which, and how often.

Where `pmx discover` mines a model that *generalises* the log, a DFG just counts
what the log literally contains. Both are useful and they disagree on purpose:
a miner adds routing constructs and drops infrequent behaviour, a DFG does
neither.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pmx.discovery import DiscoveryError, require_graphviz
from pmx.logs import DEFAULT_ACTIVITY, DEFAULT_CASE_ID, EventLog


@dataclass(frozen=True)
class Edge:
    """One directly-follows relation and the number of times it occurs."""

    source: str
    target: str
    count: int

    @property
    def is_self_loop(self) -> bool:
        return self.source == self.target


@dataclass(frozen=True)
class Dfg:
    """A directly-follows graph over one log, with the counts to weight it.

    Counts are exact and cover the whole log -- unlike a graph reconstructed
    from a truncated variant list, which only sees the paths that were itemised.
    """

    source: str
    events: int
    cases: int
    activities: dict[str, int]
    start_activities: dict[str, int]
    end_activities: dict[str, int]
    edges: list[Edge]

    def as_dict(self) -> dict[str, Any]:
        """The wire format, carrying enough context to compute shares alone."""
        return {
            "source": self.source,
            "events": self.events,
            "cases": self.cases,
            "activities": self.activities,
            "start_activities": self.start_activities,
            "end_activities": self.end_activities,
            "edges": [
                {"from": e.source, "to": e.target, "count": e.count} for e in self.edges
            ],
        }


def build(log: EventLog) -> Dfg:
    """Count the directly-follows relations in `log`."""
    import pm4py

    frame = log.frame
    raw, start_activities, end_activities = pm4py.discover_dfg(frame)

    # pm4py keys the DFG by a `(source, target)` tuple, which JSON cannot
    # represent as a key -- hence the flattening to records here rather than
    # at the serialisation boundary.
    edges = [
        Edge(source=str(pair[0]), target=str(pair[1]), count=int(count))
        for pair, count in raw.items()
    ]
    edges.sort(key=lambda e: (-e.count, e.source, e.target))

    return Dfg(
        source=str(log.source),
        events=int(len(frame)),
        cases=int(frame[DEFAULT_CASE_ID].nunique()),
        activities=_counts(pm4py.get_event_attribute_values(frame, DEFAULT_ACTIVITY)),
        start_activities=_counts(start_activities),
        end_activities=_counts(end_activities),
        edges=edges,
    )


def render(
    dfg: Dfg,
    path: Path,
    max_edges: int | None = None,
    rankdir: str = "LR",
    bgcolor: str = "white",
) -> Path:
    """Render `dfg` to an image, format taken from `path`'s suffix.

    A real log makes a dense graph -- 27 activities can carry 99 edges -- so
    `max_edges` is usually what makes the picture readable. It trims the render
    only; the JSON always carries every edge.
    """
    import pm4py

    require_graphviz()
    if max_edges is not None and max_edges < 1:
        raise DiscoveryError(f"--max-edges must be at least 1, got {max_edges}")

    # Trim here rather than through pm4py's own `max_num_edges`: that drops
    # edges without dropping the start/end activities which referenced them,
    # and then raises KeyError on the first orphan it tries to draw.
    kept = dfg.edges if max_edges is None else dfg.edges[:max_edges]
    nodes = {e.source for e in kept} | {e.target for e in kept}
    if not nodes:
        raise DiscoveryError("nothing to render: the graph has no edges")

    path.parent.mkdir(parents=True, exist_ok=True)
    pm4py.save_vis_dfg(
        {(e.source, e.target): e.count for e in kept},
        {a: n for a, n in dfg.start_activities.items() if a in nodes},
        {a: n for a, n in dfg.end_activities.items() if a in nodes},
        str(path),
        bgcolor=bgcolor,
        rankdir=rankdir,
    )
    return path


def _counts(raw: dict[Any, Any]) -> dict[str, int]:
    """Normalise a pm4py count mapping to plain `str -> int`, densest first."""
    items = sorted(raw.items(), key=lambda kv: (-int(kv[1]), str(kv[0])))
    return {str(k): int(v) for k, v in items}
