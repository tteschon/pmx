from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pmx import __version__
from pmx.cli import app

runner = CliRunner()

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def plain(text: str) -> str:
    """Strip ANSI styling so assertions test content, not colour.

    Rich emits no escapes to a pipe, but honours FORCE_COLOR -- which CI sets
    -- and then auto-highlights numbers, so `1 of 7 variants` arrives with
    escapes around each digit and a plain substring check fails.
    """
    return _ANSI.sub("", text)


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


def test_ocel_inspect_json_is_parseable(prov_ocel: Path) -> None:
    result = runner.invoke(app, ["ocel", "inspect", str(prov_ocel), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["events"] == 8
    assert payload["convergence"][0]["duplicated"] == 1


def test_ocel_inspect_renders_tables(prov_ocel: Path) -> None:
    result = runner.invoke(app, ["ocel", "inspect", str(prov_ocel)])

    assert result.exit_code == 0
    assert "Convergence" in result.stdout
    assert "Divergence" in result.stdout


def test_ocel_inspect_on_a_missing_file_exits_nonzero(tmp_path: Path) -> None:
    result = runner.invoke(app, ["ocel", "inspect", str(tmp_path / "absent.json")])

    assert result.exit_code == 1


@pytest.mark.parametrize("notation", ["ocdfg", "ocpn"])
def test_ocel_discover_writes_an_image(
    prov_ocel: Path, tmp_path: Path, notation: str
) -> None:
    target = tmp_path / f"{notation}.svg"

    result = runner.invoke(
        app,
        ["ocel", "discover", str(prov_ocel), "--notation", notation, "-i", str(target)],
    )

    assert result.exit_code == 0
    assert target.exists()
    assert result.stdout.strip().endswith(str(target))


def test_ocel_flatten_bridges_to_the_classic_commands(
    prov_ocel: Path, tmp_path: Path
) -> None:
    target = tmp_path / "flat.xes"

    flat = runner.invoke(
        app, ["ocel", "flatten", str(prov_ocel), "-t", "opportunity", "-o", str(target)]
    )
    assert flat.exit_code == 0

    # the whole point of flatten: the existing commands accept the result
    onward = runner.invoke(app, ["inspect", str(target), "--json"])
    assert onward.exit_code == 0
    assert json.loads(onward.stdout)["cases"] == 1


def test_ocel_flatten_rejects_an_unknown_object_type(
    prov_ocel: Path, tmp_path: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "ocel",
            "flatten",
            str(prov_ocel),
            "-t",
            "widget",
            "-o",
            str(tmp_path / "x.xes"),
        ],
    )

    assert result.exit_code == 1


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


def test_discover_reports_the_filter_on_stderr_only(
    wide_log: Path, tmp_path: Path
) -> None:
    """A filtered model must never be mistakable for the whole process.

    The note has to reach the user, but stdout stays parseable, so it belongs
    on stderr alongside the existing "discovered ..." line.
    """
    target = tmp_path / "model.pnml"

    result = runner.invoke(
        app, ["discover", str(wide_log), "--top-variants", "1", "-o", str(target)]
    )

    assert result.exit_code == 0
    assert result.stdout.splitlines() == [str(target)]
    assert "filtered" in plain(result.stderr)
    assert "1 of 7 variants" in plain(result.stderr)
    assert "50.0%" in plain(result.stderr)


def test_discover_min_coverage_keeps_the_fewest_variants(
    wide_log: Path, tmp_path: Path
) -> None:
    result = runner.invoke(
        app,
        [
            "discover",
            str(wide_log),
            "--min-coverage",
            "0.8",
            "-o",
            str(tmp_path / "m.pnml"),
        ],
    )

    assert result.exit_code == 0
    assert "3 of 7 variants" in plain(result.stderr)


def test_variant_filters_are_mutually_exclusive(wide_log: Path, tmp_path: Path) -> None:
    target = tmp_path / "model.pnml"

    result = runner.invoke(
        app,
        [
            "discover",
            str(wide_log),
            "--top-variants",
            "2",
            "--min-coverage",
            "0.8",
            "-o",
            str(target),
        ],
    )

    assert result.exit_code == 1
    assert "mutually exclusive" in plain(result.stderr)
    assert not target.exists()


def test_filtering_shrinks_the_dfg(wide_log: Path) -> None:
    full = runner.invoke(app, ["dfg", str(wide_log), "--json"])
    trimmed = runner.invoke(
        app, ["dfg", str(wide_log), "--json", "--top-variants", "1"]
    )

    assert full.exit_code == trimmed.exit_code == 0
    assert len(json.loads(trimmed.stdout)["edges"]) < len(
        json.loads(full.stdout)["edges"]
    )


def test_inspect_shows_variant_coverage(wide_log: Path) -> None:
    result = runner.invoke(app, ["inspect", str(wide_log)])

    assert result.exit_code == 0
    assert "cum %" in plain(result.stdout)
    assert "3 cover 80%" in plain(result.stderr)


def test_inspect_json_carries_the_new_statistics(wide_log: Path) -> None:
    result = runner.invoke(app, ["inspect", str(wide_log), "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["variants_for_80pct"] == 3
    assert payload["singleton_variants"] == 4
    assert payload["distinct_activity_sets"] == 6
    assert payload["median_case_duration_seconds"] == 10800.0


def test_inspect_json_keeps_its_existing_shape(xes_log: Path) -> None:
    """The dashboard reads these keys; adding fields must not rename any."""
    payload = json.loads(runner.invoke(app, ["inspect", str(xes_log), "--json"]).stdout)

    assert {
        "source",
        "events",
        "cases",
        "activities",
        "variants",
        "first_event",
        "last_event",
        "top_activities",
        "start_activities",
        "end_activities",
        "top_variants",
    } <= set(payload)
    assert isinstance(payload["top_variants"], dict)
