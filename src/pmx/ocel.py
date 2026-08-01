"""Object-centric event logs: processes where there is no single case.

A classic log forces every event into one case. Some processes do not have
one -- an order provisions several subscriptions, a subscription outlives the
order that created it -- and picking a case id for them silently distorts the
result. This module reads OCEL, measures how badly a given choice of case id
*would* distort it, and mines models that need no case id at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any

from pmx.discovery import DiscoveryError, require_graphviz


class OcelError(DiscoveryError):
    """An OCEL could not be read, or does not contain what was asked for."""


class Notation(StrEnum):
    """What to mine from an object-centric log."""

    OCDFG = "ocdfg"
    OCPN = "ocpn"


@dataclass(frozen=True)
class Convergence:
    """How many events a flattened log would count more than once.

    Flattening picks one object type as the case id. An event touching three
    objects of that type becomes three rows, so every count and duration
    computed downstream is inflated.
    """

    object_type: str
    events: int
    flattened_rows: int

    @property
    def duplicated(self) -> int:
        return self.flattened_rows - self.events

    @property
    def inflation(self) -> float:
        return (self.flattened_rows / self.events) if self.events else 1.0


@dataclass(frozen=True)
class Divergence:
    """How far one object's life spreads across objects of another type.

    A value above 1 means choosing `parent` as the case id merges several
    `child` lifecycles into one trace, and choosing `child` splits the
    `parent` across several.
    """

    parent: str
    child: str
    max_children: int
    example: str
    example_children: list[str]


@dataclass(frozen=True)
class Summary:
    """A profile of one object-centric log."""

    source: str
    events: int
    objects: int
    relations: int
    object_types: dict[str, int]
    activities: dict[str, int]
    type_activities: dict[str, list[str]] = field(default_factory=dict)
    convergence: list[Convergence] = field(default_factory=list)
    divergence: list[Divergence] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "events": self.events,
            "objects": self.objects,
            "relations": self.relations,
            "object_types": self.object_types,
            "activities": self.activities,
            "type_activities": self.type_activities,
            "convergence": [
                {
                    "object_type": c.object_type,
                    "events": c.events,
                    "flattened_rows": c.flattened_rows,
                    "duplicated": c.duplicated,
                    "inflation": round(c.inflation, 3),
                }
                for c in self.convergence
            ],
            "divergence": [
                {
                    "parent": d.parent,
                    "child": d.child,
                    "max_children": d.max_children,
                    "example": d.example,
                    "example_children": d.example_children,
                }
                for d in self.divergence
            ],
        }


def read(path: Path) -> Any:
    """Read an OCEL, trying the 2.0 readers before the legacy ones.

    pm4py has a separate reader per format and per OCEL version, and none of
    them sniff the file. Dispatching on the suffix and falling back keeps the
    CLI from asking the reader to be named on the command line.
    """
    import pm4py

    if not path.exists():
        raise OcelError(f"no such file: {path}")

    suffix = path.suffix.lower()
    readers = {
        ".json": ("read_ocel2_json", "read_ocel_json"),
        ".jsonocel": ("read_ocel2_json", "read_ocel_json"),
        ".xml": ("read_ocel2_xml", "read_ocel_xml"),
        ".xmlocel": ("read_ocel2_xml", "read_ocel_xml"),
        ".sqlite": ("read_ocel2_sqlite", "read_ocel_sqlite"),
        ".db": ("read_ocel2_sqlite", "read_ocel_sqlite"),
        ".csv": ("read_ocel2_csv",),
    }.get(suffix)

    if readers is None:
        raise OcelError(
            f"{path.suffix or 'that file'} is not a format pmx reads as OCEL. "
            "Use .json, .xml, .sqlite, or .csv (OCEL 1.0 or 2.0)."
        )

    failures = []
    for name in readers:
        try:
            ocel = getattr(pm4py, name)(str(path))
        except Exception as exc:  # each reader raises its own parser errors
            failures.append(f"{name}: {exc}")
            continue
        if len(ocel.events):
            return ocel
        failures.append(f"{name}: parsed but found no events")

    raise OcelError(f"could not read {path} as OCEL. Tried " + "; ".join(failures))


def summarize(ocel: Any, source: str, top: int = 10) -> Summary:
    """Profile `ocel`, including what flattening it would cost."""
    import pm4py

    relations = ocel.relations
    object_types = (
        ocel.objects.groupby(ocel.object_type_column)
        .size()
        .sort_values(ascending=False)
    )
    activities = (
        ocel.events.groupby(ocel.event_activity).size().sort_values(ascending=False)
    )

    return Summary(
        source=source,
        events=int(len(ocel.events)),
        objects=int(len(ocel.objects)),
        relations=int(len(relations)),
        object_types={str(k): int(v) for k, v in object_types.items()},
        activities={str(k): int(v) for k, v in activities.head(top).items()},
        type_activities={
            str(k): sorted(str(a) for a in v)
            for k, v in pm4py.ocel_object_type_activities(ocel).items()
        },
        convergence=_convergence(ocel),
        divergence=_divergence(ocel, top=top),
    )


def _convergence(ocel: Any) -> list[Convergence]:
    import pm4py

    out = []
    for otype in pm4py.ocel_get_object_types(ocel):
        touching = ocel.relations[ocel.relations[ocel.object_type_column] == otype]
        events = int(touching[ocel.event_id_column].nunique())
        rows = int(len(pm4py.ocel_flattening(ocel, otype)))
        out.append(Convergence(object_type=otype, events=events, flattened_rows=rows))
    out.sort(key=lambda c: (-c.duplicated, c.object_type))
    return out


def _divergence(ocel: Any, top: int = 10) -> list[Divergence]:
    """For every ordered pair of object types, how far one spreads over the other."""
    import pm4py

    eid, oid, otype = (
        ocel.event_id_column,
        ocel.object_id_column,
        ocel.object_type_column,
    )
    rel = ocel.relations[[eid, oid, otype]]
    by_type = {
        t: rel[rel[otype] == t][[eid, oid]] for t in pm4py.ocel_get_object_types(ocel)
    }

    out = []
    for parent, pframe in by_type.items():
        for child, cframe in by_type.items():
            if parent == child:
                continue
            joined = pframe.merge(cframe, on=eid, suffixes=("_p", "_c"))
            if joined.empty:
                continue
            spread = joined.groupby(f"{oid}_p")[f"{oid}_c"].nunique()
            best = int(spread.max())
            if best < 2:
                continue  # one-to-one carries no distortion
            example = str(spread.idxmax())
            children = sorted(
                str(v)
                for v in joined[joined[f"{oid}_p"] == example][f"{oid}_c"].unique()
            )
            out.append(
                Divergence(
                    parent=parent,
                    child=child,
                    max_children=best,
                    example=example,
                    example_children=children[:8],
                )
            )
    out.sort(key=lambda d: (-d.max_children, d.parent, d.child))
    return out[:top]


def discover(
    ocel: Any,
    notation: Notation = Notation.OCDFG,
    noise_threshold: float = 0.0,
) -> Any:
    """Mine an object-centric model. Neither notation needs a case id."""
    import pm4py

    if notation is Notation.OCDFG:
        return pm4py.discover_ocdfg(ocel)
    if not 0.0 <= noise_threshold <= 1.0:
        raise OcelError(f"noise threshold must be in [0, 1], got {noise_threshold}")
    return pm4py.discover_oc_petri_net(ocel, noise_threshold=noise_threshold)


def render(
    model: Any,
    path: Path,
    notation: Notation = Notation.OCDFG,
    annotation: str = "frequency",
    bgcolor: str = "white",
    rankdir: str = "LR",
) -> Path:
    """Render an object-centric model, format taken from `path`'s suffix."""
    import pm4py

    require_graphviz()
    path.parent.mkdir(parents=True, exist_ok=True)
    if notation is Notation.OCDFG:
        pm4py.save_vis_ocdfg(
            model, str(path), annotation=annotation, bgcolor=bgcolor, rankdir=rankdir
        )
    else:
        pm4py.save_vis_ocpn(model, str(path), bgcolor=bgcolor, rankdir=rankdir)
    return path


def flatten(ocel: Any, object_type: str) -> Any:
    """Collapse an OCEL to a classic log keyed on `object_type`.

    The bridge to `pmx inspect` and `pmx discover` -- and the operation whose
    cost `summarize` reports, so check the convergence figure before trusting
    anything mined from the result.
    """
    import pm4py

    available = pm4py.ocel_get_object_types(ocel)
    if object_type not in available:
        raise OcelError(
            f"no object type {object_type!r} in this log. "
            f"Available: {', '.join(sorted(available))}"
        )
    return pm4py.ocel_flattening(ocel, object_type)
