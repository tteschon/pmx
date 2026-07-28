from __future__ import annotations

from pathlib import Path

import pytest

from pmx.discovery import (
    Algorithm,
    DiscoveryError,
    GraphvizMissingError,
    Notation,
    discover,
    graphviz_available,
    render_model,
    write_model,
)
from pmx.logs import read_log

ALL_ALGORITHMS = [Algorithm.INDUCTIVE, Algorithm.HEURISTICS, Algorithm.ALPHA]


@pytest.mark.parametrize("algorithm", ALL_ALGORITHMS)
def test_every_algorithm_yields_a_petri_net(
    xes_log: Path, algorithm: Algorithm
) -> None:
    model = discover(read_log(xes_log), algorithm=algorithm)

    net, initial_marking, final_marking = model.payload
    assert model.notation is Notation.PETRI
    assert {t.label for t in net.transitions} >= {"register", "approve", "archive"}
    assert len(initial_marking) >= 1
    assert len(final_marking) >= 1


def test_bpmn_notation_uses_the_inductive_miner(xes_log: Path) -> None:
    model = discover(read_log(xes_log), notation=Notation.BPMN)

    assert model.default_suffix == ".bpmn"
    assert model.payload.get_nodes()


def test_bpmn_rejects_the_other_miners(xes_log: Path) -> None:
    with pytest.raises(DiscoveryError, match="only discover BPMN"):
        discover(read_log(xes_log), algorithm=Algorithm.ALPHA, notation=Notation.BPMN)


@pytest.mark.parametrize("threshold", [-0.1, 1.5])
def test_out_of_range_noise_threshold_is_rejected(
    xes_log: Path, threshold: float
) -> None:
    with pytest.raises(DiscoveryError, match=r"noise threshold must be in \[0, 1\]"):
        discover(read_log(xes_log), noise_threshold=threshold)


def test_write_model_produces_pnml(xes_log: Path, tmp_path: Path) -> None:
    model = discover(read_log(xes_log))
    target = tmp_path / "nested" / "model.pnml"

    written = write_model(model, target)

    assert written == target
    assert "<pnml" in target.read_text(encoding="utf-8")


def test_write_model_produces_bpmn(xes_log: Path, tmp_path: Path) -> None:
    model = discover(read_log(xes_log), notation=Notation.BPMN)
    target = tmp_path / "model.bpmn"

    write_model(model, target)

    assert "bpmn" in target.read_text(encoding="utf-8").lower()


def test_render_reports_a_missing_graphviz(
    xes_log: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pmx.discovery.shutil.which", lambda _: None)
    model = discover(read_log(xes_log))

    with pytest.raises(GraphvizMissingError, match="brew install graphviz"):
        render_model(model, tmp_path / "model.png")


@pytest.mark.skipif(not graphviz_available(), reason="Graphviz 'dot' is not installed")
def test_render_writes_an_image(xes_log: Path, tmp_path: Path) -> None:
    model = discover(read_log(xes_log))
    target = tmp_path / "model.png"

    render_model(model, target)

    assert target.stat().st_size > 0
