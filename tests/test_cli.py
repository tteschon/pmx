from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pmx import __version__
from pmx.cli import app

runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_inspect_json_is_parseable(xes_log: Path) -> None:
    result = runner.invoke(app, ["inspect", str(xes_log), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["events"] == 15
    assert payload["cases"] == 4


def test_inspect_renders_tables_by_default(xes_log: Path) -> None:
    result = runner.invoke(app, ["inspect", str(xes_log)])

    assert result.exit_code == 0
    assert "events" in result.stdout
    assert "Start activities" in result.stdout


def test_inspect_maps_csv_columns(csv_log: Path) -> None:
    result = runner.invoke(
        app,
        [
            "inspect",
            str(csv_log),
            "--json",
            "--case-id",
            "Case ID",
            "--activity-key",
            "Activity",
            "--timestamp-key",
            "Timestamp",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout)["cases"] == 4


def test_missing_log_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(app, ["inspect", str(tmp_path / "absent.xes")])

    assert result.exit_code == 1


def test_discover_defaults_output_next_to_the_log(xes_log: Path) -> None:
    result = runner.invoke(app, ["discover", str(xes_log)])

    assert result.exit_code == 0
    expected = xes_log.with_suffix(".pnml")
    assert expected.exists()
    assert result.stdout.strip().endswith(str(expected))


def test_discover_honours_explicit_output(xes_log: Path, tmp_path: Path) -> None:
    target = tmp_path / "out" / "model.bpmn"

    result = runner.invoke(
        app,
        ["discover", str(xes_log), "--notation", "bpmn", "--output", str(target)],
    )

    assert result.exit_code == 0
    assert target.exists()


@pytest.mark.parametrize("algorithm", ["inductive", "heuristics", "alpha"])
def test_discover_accepts_each_algorithm(
    xes_log: Path, tmp_path: Path, algorithm: str
) -> None:
    target = tmp_path / f"{algorithm}.pnml"

    result = runner.invoke(
        app, ["discover", str(xes_log), "-a", algorithm, "-o", str(target)]
    )

    assert result.exit_code == 0
    assert target.exists()


def test_discover_prints_long_paths_unwrapped(xes_log: Path, tmp_path: Path) -> None:
    # Regression: paths printed through a rich Console get word-wrapped at the
    # terminal width, which silently corrupts `pmx discover ... | xargs`.
    target = tmp_path.joinpath(*[f"directory-segment-{i}" for i in range(8)])
    target = target / "model.pnml"

    result = runner.invoke(app, ["discover", str(xes_log), "-o", str(target)])

    assert result.exit_code == 0
    assert len(str(target)) > 120  # long enough that wrapping would show
    assert result.stdout.splitlines() == [str(target)]


def test_inspect_json_survives_a_narrow_terminal(
    xes_log: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLUMNS", "40")

    result = runner.invoke(app, ["inspect", str(xes_log), "--json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout)["events"] == 15


def test_image_without_graphviz_writes_nothing(
    xes_log: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pmx.discovery.shutil.which", lambda _: None)
    target = tmp_path / "model.pnml"

    result = runner.invoke(
        app,
        ["discover", str(xes_log), "-o", str(target), "-i", str(tmp_path / "m.png")],
    )

    assert result.exit_code == 1
    # Fail fast: a command that exits non-zero should not leave a model behind.
    assert not target.exists()


def test_dfg_json_is_parseable(xes_log: Path) -> None:
    result = runner.invoke(app, ["dfg", str(xes_log), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["cases"] == 4
    assert len(payload["edges"]) == 4


def test_dfg_renders_a_table_by_default(xes_log: Path) -> None:
    result = runner.invoke(app, ["dfg", str(xes_log)])

    assert result.exit_code == 0
    assert "transitions" in result.stdout
    assert "approve" in result.stdout


def test_dfg_writes_json_to_a_file(xes_log: Path, tmp_path: Path) -> None:
    target = tmp_path / "out" / "graph.json"

    result = runner.invoke(app, ["dfg", str(xes_log), "-o", str(target)])

    assert result.exit_code == 0
    assert json.loads(target.read_text())["events"] == 15
    assert result.stdout.strip().endswith(str(target))


def test_dfg_prints_long_paths_unwrapped(xes_log: Path, tmp_path: Path) -> None:
    target = tmp_path.joinpath(*[f"directory-segment-{i}" for i in range(8)])
    target = target / "graph.json"

    result = runner.invoke(app, ["dfg", str(xes_log), "-o", str(target)])

    assert result.exit_code == 0
    assert len(str(target)) > 120
    assert result.stdout.splitlines() == [str(target)]


def test_dfg_image_without_graphviz_exits_nonzero(
    xes_log: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("pmx.discovery.shutil.which", lambda _: None)

    result = runner.invoke(
        app, ["dfg", str(xes_log), "-i", str(tmp_path / "graph.svg")]
    )

    assert result.exit_code == 1


def test_dfg_rejects_max_edges_below_one(xes_log: Path, tmp_path: Path) -> None:
    result = runner.invoke(
        app, ["dfg", str(xes_log), "-i", str(tmp_path / "g.svg"), "--max-edges", "0"]
    )

    assert result.exit_code != 0


def test_discover_rejects_an_unknown_algorithm(xes_log: Path) -> None:
    result = runner.invoke(app, ["discover", str(xes_log), "-a", "petrinet-magic"])

    assert result.exit_code != 0


def test_discover_rejects_bpmn_with_the_alpha_miner(xes_log: Path) -> None:
    result = runner.invoke(
        app, ["discover", str(xes_log), "--notation", "bpmn", "-a", "alpha"]
    )

    assert result.exit_code == 1


def test_discover_rejects_an_out_of_range_threshold(xes_log: Path) -> None:
    result = runner.invoke(app, ["discover", str(xes_log), "--noise-threshold", "2"])

    assert result.exit_code != 0
