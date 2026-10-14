"""Golden tests: pin every figure the docs quote for pm4py's sample logs.

README.md, CHANGELOG.md and the agent skill make concrete claims -- "74
transitions to 14", "87.9% of cases" -- about the logs that
`examples/fetch-sample-logs.sh` downloads. Nothing else checks those claims,
and they drift silently: when a pm4py release changes what a miner produces,
or when a figure was simply wrong. Each test here names where its numbers are
quoted, so a failure says which sentence to fix.

SKILL.md and references/*.md are the pmx-process-mining skill, which lives in
tteschon/skills (plugins/process-mining), not here. pmx CI cannot see it, so
when a figure in this file changes, edit the skill to match.

The logs are gitignored, so these skip on a fresh clone. CI fetches them and
sets PMX_REQUIRE_SAMPLE_LOGS=1, which turns a missing log into a failure --
otherwise a broken download would quietly skip every test in this file.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

import pytest

from pmx.dfg import build
from pmx.discovery import discover
from pmx.filters import top_variants
from pmx.logs import EventLog, read_log
from pmx.stats import summarize

DATA = Path(__file__).resolve().parents[1] / "examples" / "data"


def sample(name: str) -> EventLog:
    path = DATA / name
    if not path.exists():
        if os.environ.get("PMX_REQUIRE_SAMPLE_LOGS") == "1":
            pytest.fail(f"{name} is missing; run examples/fetch-sample-logs.sh")
        pytest.skip("run examples/fetch-sample-logs.sh to enable")
    return read_log(path)


def transitions(log: EventLog) -> int:
    """Transition count of the inductive miner's Petri net, silent ones included."""
    net, _initial, _final = discover(log).payload
    return len(net.transitions)


@pytest.fixture(scope="module")
def receipt() -> EventLog:
    return sample("receipt.xes")


# README.md, "Sample data" table.
@pytest.mark.parametrize(
    ("name", "cases", "events"),
    [
        ("running-example.xes", 6, 42),
        ("running-example.csv", 6, 42),
        ("receipt.xes", 1434, 8577),
        ("roadtraffic100traces.xes", 100, 390),
        ("helpdesk.xes.gz", 4580, 21348),
    ],
)
def test_sample_log_sizes(name: str, cases: int, events: int) -> None:
    summary = summarize(sample(name))

    assert (summary.cases, summary.events) == (cases, events)


def test_running_example_worked_example() -> None:
    """SKILL.md, "Worked example": 42 / 6 / 8 / 6, then a 10-transition net."""
    log = sample("running-example.xes")
    summary = summarize(log)

    assert (summary.events, summary.cases) == (42, 6)
    assert (summary.activities, summary.variants) == (8, 6)
    assert transitions(log) == 10


def test_receipt_variant_concentration(receipt: EventLog) -> None:
    """README.md's `inspect` excerpt and references/interpreting.md."""
    summary = summarize(receipt)

    assert (summary.cases, summary.events, summary.variants) == (1434, 8577, 116)
    assert summary.variants_for_50pct == 2
    assert summary.variants_for_80pct == 6
    assert summary.variants_for_95pct == 45
    assert summary.singleton_variants == 86
    assert summary.distinct_activity_sets == 50


def test_receipt_concurrency_claim(receipt: EventLog) -> None:
    """references/interpreting.md: 89% of cases use just six activities, in 21
    different orders."""
    variants = summarize(receipt, top=1_000).top_variants
    paths = {tuple(label.split(" -> ")): count for label, count in variants.items()}
    by_set: Counter[frozenset[str]] = Counter()
    for path, count in paths.items():
        by_set[frozenset(path)] += count
    six = max(by_set, key=by_set.__getitem__)
    within = {path: count for path, count in paths.items() if set(path) <= six}

    assert len(six) == 6
    assert round(sum(within.values()) / 1434, 2) == 0.89
    assert len(within) == 21


def test_receipt_model_sizes(receipt: EventLog) -> None:
    """README.md and references/interpreting.md, the Filter / Transitions table;
    SKILL.md step 4 and CHANGELOG.md quote the same 74 -> 14 at 88%."""
    assert transitions(receipt) == 74

    top10, report10 = top_variants(receipt, 10)
    assert transitions(top10) == 14
    assert (report10.kept_cases, round(report10.case_share * 100, 1)) == (1260, 87.9)

    top5, report5 = top_variants(receipt, 5)
    assert transitions(top5) == 9
    assert (report5.kept_cases, round(report5.case_share * 100, 1)) == (1142, 79.6)


@pytest.mark.parametrize(("threshold", "expected"), [(0.2, 69), (0.3, 42), (0.4, 57)])
def test_receipt_noise_threshold(
    receipt: EventLog, tmp_path: Path, threshold: float, expected: int
) -> None:
    """README.md, references/interpreting.md, SKILL.md and pmx.filters: the
    noise threshold shrinks the model unevenly, and never as far as
    --top-variants 10 does.

    In-process, these figures depend on the interpreter's hash seed -- about
    one run in four gives 66 / 39 / 54. The CLI pins the seed, so this goes
    through a real `pmx` process with PYTHONHASHSEED unset, the way a user
    runs it.
    """
    out = tmp_path / "model.pnml"
    env = {k: v for k, v in os.environ.items() if k != "PYTHONHASHSEED"}
    subprocess.run(
        [sys.executable, "-m", "pmx", "discover", str(receipt.source)]
        + ["--noise-threshold", str(threshold), "-o", str(out)],
        env=env,
        check=True,
        capture_output=True,
    )

    tree = ElementTree.parse(out)
    assert len(tree.findall(".//{*}transition")) == expected


def test_receipt_dfg_is_complete(receipt: EventLog) -> None:
    """references/commands.md: `inspect -n 25` itemises paths covering 93% of
    cases and 16 of 27 activities, where `dfg` reports all 27 activities and
    99 transitions."""
    dfg = build(receipt)
    assert (len(dfg.activities), len(dfg.edges)) == (27, 99)

    top25 = summarize(receipt, top=25).top_variants
    covered = sum(top25.values()) / 1434
    mentioned = {step for label in top25 for step in label.split(" -> ")}
    assert (round(covered * 100), len(mentioned)) == (93, 16)
