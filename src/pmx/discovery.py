"""Process discovery: mine a model from a log, then export or render it."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pmx.logs import EventLog


class Algorithm(StrEnum):
    """Discovery algorithms exposed by the CLI."""

    INDUCTIVE = "inductive"
    HEURISTICS = "heuristics"
    ALPHA = "alpha"


class Notation(StrEnum):
    """Target notation for the discovered model."""

    PETRI = "petri"
    BPMN = "bpmn"


class DiscoveryError(Exception):
    """Discovery ran but the requested combination cannot be produced."""


class GraphvizMissingError(DiscoveryError):
    """Rendering was requested but the Graphviz `dot` binary is not on PATH."""


@dataclass(frozen=True)
class Model:
    """A discovered model, kept in whichever pm4py object shape it was mined as.

    `payload` is a `(net, initial_marking, final_marking)` triple for
    `Notation.PETRI` and a single `BPMN` object for `Notation.BPMN`.
    """

    notation: Notation
    algorithm: Algorithm
    payload: Any

    @property
    def default_suffix(self) -> str:
        return ".pnml" if self.notation is Notation.PETRI else ".bpmn"


def discover(
    log: EventLog,
    algorithm: Algorithm = Algorithm.INDUCTIVE,
    notation: Notation = Notation.PETRI,
    noise_threshold: float = 0.0,
    dependency_threshold: float = 0.5,
) -> Model:
    """Mine a model from `log`.

    `noise_threshold` applies to the inductive miner (0.0 keeps every
    behaviour; higher values filter infrequent paths). `dependency_threshold`
    applies to the heuristics miner. Both are ignored by the alpha miner,
    which has no tuning knobs.
    """
    import pm4py

    if not 0.0 <= noise_threshold <= 1.0:
        raise DiscoveryError(
            f"noise threshold must be in [0, 1], got {noise_threshold}"
        )
    if not 0.0 <= dependency_threshold <= 1.0:
        raise DiscoveryError(
            f"dependency threshold must be in [0, 1], got {dependency_threshold}"
        )

    frame = log.frame
    if notation is Notation.BPMN:
        if algorithm is not Algorithm.INDUCTIVE:
            raise DiscoveryError(
                f"pm4py can only discover BPMN with the inductive miner, "
                f"not {algorithm.value}"
            )
        payload = pm4py.discover_bpmn_inductive(frame, noise_threshold=noise_threshold)
    elif algorithm is Algorithm.INDUCTIVE:
        payload = pm4py.discover_petri_net_inductive(
            frame, noise_threshold=noise_threshold
        )
    elif algorithm is Algorithm.HEURISTICS:
        payload = pm4py.discover_petri_net_heuristics(
            frame, dependency_threshold=dependency_threshold
        )
    else:
        payload = pm4py.discover_petri_net_alpha(frame)

    return Model(notation=notation, algorithm=algorithm, payload=payload)


def write_model(model: Model, path: Path) -> Path:
    """Serialise `model` to `path` as PNML or BPMN XML.

    BPMN diagram coordinates come from pm4py's auto-layout, which shells out
    to Graphviz. Without it the file is still valid BPMN and still carries the
    full process semantics -- it just has no layout, so an editor that opens
    it will place the nodes itself.
    """
    import pm4py

    path.parent.mkdir(parents=True, exist_ok=True)
    if model.notation is Notation.PETRI:
        net, initial_marking, final_marking = model.payload
        pm4py.write_pnml(net, initial_marking, final_marking, str(path))
    else:
        pm4py.write_bpmn(model.payload, str(path), auto_layout=graphviz_available())
    return path


def render_model(model: Model, path: Path, bgcolor: str = "white") -> Path:
    """Render `model` to an image file, whose format follows `path`'s suffix.

    pm4py shells out to Graphviz for this, so a missing `dot` binary is
    reported up front rather than as a subprocess traceback.

    `bgcolor` defaults to Graphviz's own white. Pass `transparent` when the
    image is going to be embedded somewhere with its own background -- a dark
    page, say -- rather than viewed on its own.
    """
    import pm4py

    require_graphviz()
    path.parent.mkdir(parents=True, exist_ok=True)
    if model.notation is Notation.PETRI:
        net, initial_marking, final_marking = model.payload
        pm4py.save_vis_petri_net(
            net, initial_marking, final_marking, str(path), bgcolor=bgcolor
        )
    else:
        pm4py.save_vis_bpmn(model.payload, str(path), bgcolor=bgcolor)
    return path


def graphviz_available() -> bool:
    return shutil.which("dot") is not None


def require_graphviz() -> None:
    if graphviz_available():
        return
    raise GraphvizMissingError(
        "rendering needs the Graphviz 'dot' binary, which is not on PATH. "
        "Install it with 'brew install graphviz' (macOS) or "
        "'apt install graphviz' (Debian/Ubuntu), or drop --image."
    )
