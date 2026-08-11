"""Command line entry points for pmx."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from pmx import __version__, discovery, filters
from pmx import dfg as dfg_mod
from pmx import ocel as ocel_mod
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
TopVariantsOpt = Annotated[
    int | None,
    typer.Option(
        "--top-variants",
        min=1,
        help="Keep only the N most frequent variants. The blunt fix for an "
        "unreadable model, and usually more effective than --noise-threshold.",
        show_default=False,
    ),
]
MinCoverageOpt = Annotated[
    float | None,
    typer.Option(
        "--min-coverage",
        min=0.0,
        max=1.0,
        help="Keep the fewest variants covering this share of cases, e.g. 0.8.",
        show_default=False,
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


def _filter_variants(
    log: EventLog, top_variants: int | None, min_coverage: float | None
) -> EventLog:
    """Apply the variant filter flags, reporting what was kept on stderr.

    A filtered model describes frequent behaviour, not the process, so the
    note is printed whenever a filter actually removes something -- never
    silently.
    """
    if top_variants is not None and min_coverage is not None:
        err.print(
            "[red]error:[/red] --top-variants and --min-coverage are mutually "
            "exclusive; pass one."
        )
        raise typer.Exit(code=1)
    if top_variants is None and min_coverage is None:
        return log

    if top_variants is not None:
        filtered, report = filters.top_variants(log, top_variants)
    else:
        assert min_coverage is not None
        filtered, report = filters.variants_covering(log, min_coverage)

    if report.is_noop:
        err.print(
            f"[dim]no filtering: the log has {report.total_variants:,} variants[/dim]"
        )
        return filtered

    err.print(
        f"[yellow]filtered[/yellow] to {report.kept_variants:,} of "
        f"{report.total_variants:,} variants "
        f"({report.kept_cases:,} of {report.total_cases:,} cases, "
        f"{report.case_share:.1%})"
    )
    return filtered


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
    top_variants: TopVariantsOpt = None,
    min_coverage: MinCoverageOpt = None,
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
    log = _filter_variants(log, top_variants, min_coverage)

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
    top_variants: TopVariantsOpt = None,
    min_coverage: MinCoverageOpt = None,
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

    Unlike `discover`, nothing is generalised: these are the transitions the
    log literally contains. `--top-variants`/`--min-coverage` narrow which
    cases are counted, and are reported on stderr when they do.
    """
    log = _load(log_path, case_id, activity_key, timestamp_key, separator)
    log = _filter_variants(log, top_variants, min_coverage)
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


ocel_app = typer.Typer(
    name="ocel",
    help="Object-centric mining, for processes with no single case id.",
    no_args_is_help=True,
)
app.add_typer(ocel_app)

OcelPath = Annotated[
    Path,
    typer.Argument(
        metavar="OCEL",
        help="Object-centric log (.json, .xml, .sqlite, .csv; OCEL 1.0 or 2.0).",
        show_default=False,
    ),
]


def _read_ocel(path: Path) -> Any:
    """Read an OCEL, turning an `OcelError` into a clean exit-1 with a message.

    Returns `Any` rather than pm4py's `OCEL`: importing that type at module
    scope would pull pm4py in on every `pmx --help`, which is the slow import
    the rest of the CLI is careful to defer.
    """
    try:
        return ocel_mod.read(path)
    except ocel_mod.OcelError as exc:
        err.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc


@ocel_app.command("inspect")
def ocel_inspect(
    log_path: OcelPath,
    top: Annotated[
        int, typer.Option("--top", "-n", min=1, help="Rows per distribution.")
    ] = 10,
    as_json: Annotated[
        bool, typer.Option("--json", help="Emit JSON instead of tables.")
    ] = False,
) -> None:
    """Profile an object-centric log, and price up flattening it.

    Convergence is what a chosen case id would double-count; divergence is
    what it would merge or split. Both are reasons a classic log would lie.
    """
    ocel = _read_ocel(log_path)
    summary = ocel_mod.summarize(ocel, source=str(log_path), top=top)

    if as_json:
        print(json.dumps(summary.as_dict(), indent=2))
        return
    _print_ocel_summary(summary, top)


@ocel_app.command("discover")
def ocel_discover(
    log_path: OcelPath,
    notation: Annotated[
        ocel_mod.Notation,
        typer.Option(
            "--notation", help="ocdfg (directly-follows) or ocpn (Petri net)."
        ),
    ] = ocel_mod.Notation.OCDFG,
    image: Annotated[
        Path | None,
        typer.Option(
            "--image", "-i", help="Render here (.png/.svg/.pdf).", show_default=False
        ),
    ] = None,
    annotation: Annotated[
        str, typer.Option("--annotation", help="ocdfg only: frequency or performance.")
    ] = "frequency",
    noise_threshold: Annotated[
        float,
        typer.Option(
            "--noise-threshold", min=0.0, max=1.0, help="ocpn only: filter noise."
        ),
    ] = 0.0,
    bgcolor: BgColorOpt = "white",
) -> None:
    """Mine a model that needs no case id.

    Every object type keeps its own flow through the shared activities, so a
    step touching several types shows up once rather than once per type.
    """
    ocel = _read_ocel(log_path)
    try:
        model = ocel_mod.discover(
            ocel, notation=notation, noise_threshold=noise_threshold
        )
        target = image or log_path.with_suffix(f".{notation.value}.svg")
        written = ocel_mod.render(
            model, target, notation=notation, annotation=annotation, bgcolor=bgcolor
        )
    except DiscoveryError as exc:
        err.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    err.print(
        f"[green]discovered[/green] {notation.value} over {len(ocel.objects):,} objects"
    )
    print(written)


@ocel_app.command("flatten")
def ocel_flatten(
    log_path: OcelPath,
    object_type: Annotated[
        str,
        typer.Option(
            "--object-type", "-t", help="Which object type becomes the case id."
        ),
    ],
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Write the classic log here (.xes/.csv)."),
    ],
) -> None:
    """Collapse an OCEL to a classic log, for `pmx inspect` and `pmx discover`.

    Check `pmx ocel inspect` first: if the chosen type shows convergence, the
    flattened log counts some events more than once.
    """
    import pm4py

    ocel = _read_ocel(log_path)
    try:
        flat = ocel_mod.flatten(ocel, object_type)
    except ocel_mod.OcelError as exc:
        err.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".csv":
        flat.to_csv(output, index=False)
    else:
        pm4py.write_xes(flat, str(output))

    # Compare against the events that actually touch this object type, not the
    # whole log: most events touch none of a given type, so the total would
    # never trip and the warning would be dead code.
    touching = ocel.relations[ocel.relations[ocel.object_type_column] == object_type]
    rows, events = len(flat), int(touching[ocel.event_id_column].nunique())
    if rows > events:
        err.print(
            f"[yellow]note:[/yellow] {rows:,} rows from {events:,} events that touch "
            f"{object_type} — {rows - events:,} counted more than once, because an "
            f"event can touch several {object_type} objects. Durations and counts "
            f"computed from this log are inflated."
        )
    print(output)


def _print_ocel_summary(summary: ocel_mod.Summary, top: int) -> None:
    overview = Table(
        title=f"Object-centric log: {summary.source}", title_justify="left"
    )
    overview.add_column("metric", style="cyan")
    overview.add_column("value", justify="right")
    overview.add_row("events", f"{summary.events:,}")
    overview.add_row("objects", f"{summary.objects:,}")
    overview.add_row("object types", f"{len(summary.object_types):,}")
    overview.add_row("event-to-object links", f"{summary.relations:,}")
    out.print(overview)

    types = Table(title="Object types", title_justify="left")
    types.add_column("type", style="cyan", overflow="fold")
    types.add_column("objects", justify="right")
    types.add_column("touched by", overflow="fold")
    for name, count in summary.object_types.items():
        acts = summary.type_activities.get(name, [])
        shown = ", ".join(acts[:3]) + ("…" if len(acts) > 3 else "")
        types.add_row(name, f"{count:,}", shown or "-")
    out.print(types)

    conv = Table(
        title="Convergence — what flattening would double-count",
        title_justify="left",
    )
    conv.add_column("case id would be", style="cyan", overflow="fold")
    conv.add_column("events", justify="right")
    conv.add_column("rows", justify="right")
    conv.add_column("inflated by", justify="right")
    for c in summary.convergence:
        conv.add_row(
            c.object_type,
            f"{c.events:,}",
            f"{c.flattened_rows:,}",
            f"{c.duplicated:+,}" if c.duplicated else "—",
        )
    out.print(conv)

    if summary.divergence:
        div = Table(
            title="Divergence — what flattening would merge or split",
            title_justify="left",
        )
        div.add_column("one", style="cyan", overflow="fold")
        div.add_column("spans", justify="right")
        div.add_column("of", style="cyan", overflow="fold")
        div.add_column("example", overflow="fold")
        for d in summary.divergence[:top]:
            div.add_row(
                d.parent,
                f"{d.max_children:,}",
                d.child,
                f"{d.example} → {', '.join(d.example_children[:4])}",
            )
        out.print(div)
        err.print(
            "[dim]A case id above 1 in either table distorts the result. "
            "That is the argument for staying object-centric.[/dim]"
        )


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
    if summary.distinct_activity_sets:
        overview.add_row(
            "distinct activity sets", f"{summary.distinct_activity_sets:,}"
        )
    overview.add_row("first event", summary.first_event or "-")
    overview.add_row("last event", summary.last_event or "-")
    overview.add_row(
        "median case duration", _duration(summary.median_case_duration_seconds)
    )
    overview.add_row(
        "mean case duration", _duration(summary.mean_case_duration_seconds)
    )
    overview.add_row("p90 case duration", _duration(summary.p90_case_duration_seconds))
    overview.add_row("max case duration", _duration(summary.max_case_duration_seconds))
    out.print(overview)
    _print_variant_concentration(summary)

    for title, label, counts, share_of in (
        ("Activities", "activity", summary.top_activities, None),
        ("Start activities", "activity", summary.start_activities, None),
        ("End activities", "activity", summary.end_activities, None),
        ("Variants", "variant", summary.top_variants, summary.cases),
    ):
        if counts:
            out.print(_counts_table(title, label, counts, share_of=share_of))


def _print_variant_concentration(summary: Summary) -> None:
    """One line saying how concentrated the log is, and what to do about it.

    This is the number that decides whether `discover` can produce anything
    readable, so it is worth stating outright rather than leaving the user to
    work it out from the variants table.
    """
    if summary.variants_for_80pct is None or summary.variants <= 1:
        return
    parts = [
        f"{summary.variants_for_50pct:,} variants cover 50% of cases, "
        f"{summary.variants_for_80pct:,} cover 80%, "
        f"{summary.variants_for_95pct:,} cover 95%"
    ]
    if summary.singleton_variants:
        parts.append(f"{summary.singleton_variants:,} occur exactly once")
    err.print(f"[dim]{'; '.join(parts)}[/dim]")

    # A big collapse means the variants are re-orderings of the same work, so
    # --noise-threshold will disappoint and --top-variants is the right knob.
    if (
        summary.distinct_activity_sets
        and summary.variants >= 2 * summary.distinct_activity_sets
    ):
        err.print(
            f"[dim]{summary.variants:,} variants use only "
            f"{summary.distinct_activity_sets:,} distinct activity sets -- much of "
            f"this is concurrency; try --top-variants[/dim]"
        )


def _counts_table(
    title: str, label: str, counts: dict[str, int], share_of: int | None = None
) -> Table:
    table = Table(title=title, title_justify="left")
    table.add_column(label, style="cyan", overflow="fold")
    table.add_column("count", justify="right")
    if share_of:
        table.add_column("%", justify="right")
        table.add_column("cum %", justify="right")

    cumulative = 0
    for name, count in counts.items():
        if share_of:
            cumulative += count
            table.add_row(
                name,
                f"{count:,}",
                f"{count / share_of:.1%}",
                f"{cumulative / share_of:.1%}",
            )
        else:
            table.add_row(name, f"{count:,}")
    return table


def _duration(seconds: float | None) -> str:
    """Render elapsed seconds compactly: '3d 4h', '12m', '0s'.

    Two units is enough to judge a process by, and keeps the overview table
    narrow.
    """
    if seconds is None:
        return "-"
    if seconds < 1:
        return "0s"

    remaining = int(seconds)
    units = (("d", 86400), ("h", 3600), ("m", 60), ("s", 1))
    parts = []
    for suffix, size in units:
        value, remaining = divmod(remaining, size)
        if value:
            parts.append(f"{value}{suffix}")
        if len(parts) == 2:
            break
    return " ".join(parts) or "0s"


def main() -> None:
    app()
