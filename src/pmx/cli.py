"""Command line entry points for pmx."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from pmx import __version__, discovery
from pmx import dfg as dfg_mod
from pmx.discovery import Algorithm, DiscoveryError, Notation
from pmx.logs import (
    DEFAULT_ACTIVITY,
    DEFAULT_CASE_ID,
    DEFAULT_TIMESTAMP,
    ColumnMap,
    EventLog,
    LogError,
    read_log,
)
from pmx.stats import Summary, summarize

app = typer.Typer(
    name="pmx",
    help="Process discovery from event logs, built on pm4py.",
    no_args_is_help=True,
    add_completion=False,
)

# Progress and errors go to stderr so that `pmx inspect --json log.xes | jq`
# and `pmx discover log.xes | xargs open` both stay usable.
#
# Only human-facing tables go through Rich. Anything a caller might parse --
# JSON, file paths -- is written with plain `print`, because a Console wraps
# at the terminal width and will happily insert a newline into the middle of
# a long path.
out = Console()
err = Console(stderr=True)

LogPath = Annotated[
    Path,
    typer.Argument(
        metavar="LOG",
        help="Event log to read (.xes, .xes.gz, or delimited text).",
        show_default=False,
    ),
]
CaseIdOpt = Annotated[
    str,
    typer.Option("--case-id", help="Case id column, for delimited input."),
]
ActivityOpt = Annotated[
    str,
    typer.Option("--activity-key", help="Activity column, for delimited input."),
]
TimestampOpt = Annotated[
    str,
    typer.Option("--timestamp-key", help="Timestamp column, for delimited input."),
]
SeparatorOpt = Annotated[
    str,
    typer.Option("--separator", help="Field separator, for delimited input."),
]
BgColorOpt = Annotated[
    str,
    typer.Option(
        "--bgcolor",
        help="Image background. Use 'transparent' when embedding the image "
        "somewhere with its own background.",
    ),
]


def _version_callback(value: bool) -> None:
    if value:
        print(f"pmx {__version__}")
        raise typer.Exit


@app.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the version and exit.",
        ),
    ] = False,
) -> None:
    """Process discovery from event logs, built on pm4py."""


def _load(
    path: Path, case_id: str, activity: str, timestamp: str, separator: str
) -> EventLog:
    """Read a log, turning a `LogError` into a clean exit-1 with a message."""
    columns = ColumnMap(case_id=case_id, activity=activity, timestamp=timestamp)
    try:
        return read_log(path, columns=columns, separator=separator)
    except LogError as exc:
        err.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@app.command()
def inspect(
    log_path: LogPath,
    top: Annotated[
        int,
        typer.Option("--top", "-n", min=1, help="Entries to show per distribution."),
    ] = 10,
    as_json: Annotated[
        bool, typer.Option("--json", help="Emit JSON instead of tables.")
    ] = False,
    case_id: CaseIdOpt = DEFAULT_CASE_ID,
    activity_key: ActivityOpt = DEFAULT_ACTIVITY,
    timestamp_key: TimestampOpt = DEFAULT_TIMESTAMP,
    separator: SeparatorOpt = ",",
) -> None:
    """Profile an event log: cases, activities, variants, and time span."""
    log = _load(log_path, case_id, activity_key, timestamp_key, separator)
    summary = summarize(log, top=top)

    if as_json:
        print(json.dumps(summary.as_dict(), indent=2))
        return
    _print_summary(summary)


@app.command(name="discover")
def discover_command(
    log_path: LogPath,
    algorithm: Annotated[
        Algorithm, typer.Option("--algorithm", "-a", help="Discovery algorithm.")
    ] = Algorithm.INDUCTIVE,
    notation: Annotated[
        Notation, typer.Option("--notation", help="Model notation to produce.")
    ] = Notation.PETRI,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Write the model here. Defaults to the log path with a "
            ".pnml or .bpmn suffix.",
            show_default=False,
        ),
    ] = None,
    image: Annotated[
        Path | None,
        typer.Option(
            "--image",
            "-i",
            help="Also render the model here (.png/.svg/.pdf). Needs Graphviz.",
            show_default=False,
        ),
    ] = None,
    noise_threshold: Annotated[
        float,
        typer.Option(
            "--noise-threshold",
            min=0.0,
            max=1.0,
            help="Inductive miner: filter infrequent behaviour.",
        ),
    ] = 0.0,
    dependency_threshold: Annotated[
        float,
        typer.Option(
            "--dependency-threshold",
            min=0.0,
            max=1.0,
            help="Heuristics miner: minimum dependency to keep an edge.",
        ),
    ] = 0.5,
    bgcolor: BgColorOpt = "white",
    case_id: CaseIdOpt = DEFAULT_CASE_ID,
    activity_key: ActivityOpt = DEFAULT_ACTIVITY,
    timestamp_key: TimestampOpt = DEFAULT_TIMESTAMP,
    separator: SeparatorOpt = ",",
) -> None:
    """Discover a process model from an event log.

    Prints the path of every file written, one per line.
    """
    try:
        # Checked before any work, so a missing Graphviz does not leave a
        # written model behind on a command that then exits non-zero.
        if image is not None:
            discovery.require_graphviz()
    except DiscoveryError as exc:
        err.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    log = _load(log_path, case_id, activity_key, timestamp_key, separator)

    try:
        model = discovery.discover(
            log,
            algorithm=algorithm,
            notation=notation,
            noise_threshold=noise_threshold,
            dependency_threshold=dependency_threshold,
        )
        target = output or log_path.with_suffix(model.default_suffix)
        written = [discovery.write_model(model, target)]
        if image is not None:
            written.append(discovery.render_model(model, image, bgcolor=bgcolor))
    except DiscoveryError as exc:
        err.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    err.print(
        f"[green]discovered[/green] {notation.value} model "
        f"via the {algorithm.value} miner"
    )
    for path in written:
        print(path)


@app.command()
def dfg(
    log_path: LogPath,
    as_json: Annotated[
        bool, typer.Option("--json", help="Emit the graph as JSON on stdout.")
    ] = False,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Write the JSON here.", show_default=False),
    ] = None,
    image: Annotated[
        Path | None,
        typer.Option(
            "--image",
            "-i",
            help="Render the graph here (.png/.svg/.pdf). Needs Graphviz.",
            show_default=False,
        ),
    ] = None,
    max_edges: Annotated[
        int | None,
        typer.Option(
            "--max-edges",
            min=1,
            help="Keep only the heaviest N edges in the image. The JSON always "
            "carries every edge.",
            show_default=False,
        ),
    ] = None,
    rankdir: Annotated[
        str, typer.Option("--rankdir", help="Graph direction: LR or TB.")
    ] = "LR",
    bgcolor: BgColorOpt = "white",
    top: Annotated[
        int,
        typer.Option("--top", "-n", min=1, help="Edges to show in the table."),
    ] = 15,
    case_id: CaseIdOpt = DEFAULT_CASE_ID,
    activity_key: ActivityOpt = DEFAULT_ACTIVITY,
    timestamp_key: TimestampOpt = DEFAULT_TIMESTAMP,
    separator: SeparatorOpt = ",",
) -> None:
    """Count which activity directly follows which, across the whole log.

    Unlike `discover`, nothing is generalised or filtered: these are the
    transitions the log literally contains.
    """
    log = _load(log_path, case_id, activity_key, timestamp_key, separator)
    graph = dfg_mod.build(log)

    written: list[Path] = []
    try:
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(graph.as_dict(), indent=2) + "\n", encoding="utf-8"
            )
            written.append(output)
        if image is not None:
            written.append(
                dfg_mod.render(
                    graph,
                    image,
                    max_edges=max_edges,
                    rankdir=rankdir,
                    bgcolor=bgcolor,
                )
            )
    except DiscoveryError as exc:
        err.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    if as_json:
        print(json.dumps(graph.as_dict(), indent=2))
    elif not written:
        _print_dfg(graph, top)

    for path in written:
        print(path)


def _print_dfg(graph: dfg_mod.Dfg, top: int) -> None:
    out.print(
        f"[green]{len(graph.activities)}[/green] activities, "
        f"[green]{len(graph.edges)}[/green] transitions "
        f"across {graph.cases:,} cases"
    )
    table = Table(title="Transitions", title_justify="left")
    table.add_column("from", style="cyan", overflow="fold")
    table.add_column("to", style="cyan", overflow="fold")
    table.add_column("count", justify="right")
    for edge in graph.edges[:top]:
        label = f"{edge.target} (loop)" if edge.is_self_loop else edge.target
        table.add_row(edge.source, label, f"{edge.count:,}")
    out.print(table)
    if len(graph.edges) > top:
        err.print(f"[dim]{len(graph.edges) - top} further transitions not shown[/dim]")


def _print_summary(summary: Summary) -> None:
    overview = Table(title=f"Event log: {summary.source}", title_justify="left")
    overview.add_column("metric", style="cyan")
    overview.add_column("value", justify="right")
    overview.add_row("events", f"{summary.events:,}")
    overview.add_row("cases", f"{summary.cases:,}")
    overview.add_row("activities", f"{summary.activities:,}")
    overview.add_row("variants", f"{summary.variants:,}")
    overview.add_row("first event", summary.first_event or "-")
    overview.add_row("last event", summary.last_event or "-")
    out.print(overview)

    for title, label, counts in (
        ("Activities", "activity", summary.top_activities),
        ("Start activities", "activity", summary.start_activities),
        ("End activities", "activity", summary.end_activities),
        ("Variants", "variant", summary.top_variants),
    ):
        if counts:
            out.print(_counts_table(title, label, counts))


def _counts_table(title: str, label: str, counts: dict[str, int]) -> Table:
    table = Table(title=title, title_justify="left")
    table.add_column(label, style="cyan", overflow="fold")
    table.add_column("count", justify="right")
    for name, count in counts.items():
        table.add_row(name, f"{count:,}")
    return table


def main() -> None:
    app()
