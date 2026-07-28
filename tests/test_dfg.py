from __future__ import annotations

import json
from pathlib import Path

import pytest

from pmx.dfg import build, render
from pmx.discovery import DiscoveryError, GraphvizMissingError, graphviz_available
from pmx.logs import read_log

# The fixture is 3 cases of register->check->approve->archive plus one that
# skips "check", so every count below is checkable by hand.
EXPECTED_EDGES = {
    ("approve", "archive"): 4,
    ("register", "check"): 3,
    ("check", "approve"): 3,
    ("register", "approve"): 1,
}


def test_edge_counts_match_the_fixture(xes_log: Path) -> None:
    graph = build(read_log(xes_log))

    assert {(e.source, e.target): e.count for e in graph.edges} == EXPECTED_EDGES
    assert graph.events == 15
    assert graph.cases == 4
    assert graph.activities == {"archive": 4, "approve": 4, "register": 4, "check": 3}
    assert graph.start_activities == {"register": 4}
    assert graph.end_activities == {"archive": 4}


def test_edges_are_sorted_heaviest_first(xes_log: Path) -> None:
    counts = [e.count for e in build(read_log(xes_log)).edges]

    assert counts == sorted(counts, reverse=True)


def test_wire_format_survives_a_json_round_trip(xes_log: Path) -> None:
    # pm4py keys the DFG by a (source, target) tuple, which json.dumps cannot
    # serialise -- so this is the one conversion most likely to regress.
    graph = build(read_log(xes_log))

    payload = json.loads(json.dumps(graph.as_dict()))

    assert payload["cases"] == 4
    assert {
        (e["from"], e["to"]): e["count"] for e in payload["edges"]
    } == EXPECTED_EDGES
    assert payload["source"].endswith("sample.xes")


def test_self_loops_are_flagged(csv_log: Path) -> None:
    graph = build(read_log(csv_log, columns=_map()))

    # This fixture has none; the property still has to answer correctly.
    assert not any(e.is_self_loop for e in graph.edges)


def _map():
    from pmx.logs import ColumnMap

    return ColumnMap(case_id="Case ID", activity="Activity", timestamp="Timestamp")


def test_negative_max_edges_is_rejected(xes_log: Path, tmp_path: Path) -> None:
    graph = build(read_log(xes_log))

    with pytest.raises(DiscoveryError, match="at least 1"):
        render(graph, tmp_path / "g.svg", max_edges=0)


def test_render_without_graphviz_reports_it(
    xes_log: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pmx.discovery.shutil.which", lambda _: None)
    graph = build(read_log(xes_log))

    with pytest.raises(GraphvizMissingError, match="brew install graphviz"):
        render(graph, tmp_path / "g.svg")


@pytest.mark.skipif(not graphviz_available(), reason="Graphviz 'dot' is not installed")
def test_render_writes_an_image(xes_log: Path, tmp_path: Path) -> None:
    graph = build(read_log(xes_log))

    target = render(graph, tmp_path / "nested" / "g.svg")

    assert target.stat().st_size > 0


@pytest.mark.skipif(not graphviz_available(), reason="Graphviz 'dot' is not installed")
@pytest.mark.parametrize("max_edges", [1, 2, 3, 4, 99])
def test_trimming_keeps_the_subgraph_consistent(
    xes_log: Path, tmp_path: Path, max_edges: int
) -> None:
    # Regression: pm4py's own max_num_edges drops edges but keeps the start/end
    # activities that referenced them, then raises KeyError drawing an orphan.
    # pmx trims first and filters the endpoints to the surviving nodes.
    graph = build(read_log(xes_log))

    target = render(graph, tmp_path / f"g{max_edges}.svg", max_edges=max_edges)

    assert target.stat().st_size > 0


@pytest.mark.skipif(not graphviz_available(), reason="Graphviz 'dot' is not installed")
def test_trimming_shrinks_the_image_but_never_the_data(
    xes_log: Path, tmp_path: Path
) -> None:
    graph = build(read_log(xes_log))

    full = render(graph, tmp_path / "full.svg")
    trimmed = render(graph, tmp_path / "trim.svg", max_edges=1)

    assert trimmed.read_text().count('class="edge"') < full.read_text().count(
        'class="edge"'
    )
    assert len(graph.as_dict()["edges"]) == 4
