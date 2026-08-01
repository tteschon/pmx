---
name: pmx-process-mining
description: Profile event logs and discover process models using the pmx CLI. Use when the user has an event log (.xes, .xes.gz, or CSV of case/activity/timestamp rows) and wants to know what their process actually looks like -- case, activity and variant counts, the most common paths, or a mined process model as a Petri net or BPMN diagram. Triggers on "event log", "process mining", "process discovery", "XES", "discover a process model", "what does my process look like", "most common paths", "process variants", "inductive miner", "heuristics miner", "Petri net", "BPMN from a log", or a mention of pm4py.
compatibility: Requires the pmx CLI (a uv project wrapping pm4py) and Python 3.11+. Rendering models to images additionally requires the Graphviz `dot` system binary.
license: AGPL-3.0-or-later
metadata:
  author: tteschon
  version: "1.0"
allowed-tools: Bash(uv:*) Bash(pmx:*) Read Glob
---

# Process mining with pmx

`pmx` is a CLI over [pm4py](https://github.com/process-intelligence-solutions/pm4py)
with two commands: `inspect` profiles an event log, `discover` mines a process
model from one.

## Scope

This skill covers **discovery only**. `pmx` can answer:

- What does this process look like? What are the common paths?
- How many cases, activities, variants? Over what time span?
- Give me a process model as a Petri net or BPMN diagram.
- How often does one activity directly follow another? (`dfg`)
- What does a process with no single case id look like? (`ocel`)

**If the log is object-centric, use `pmx ocel`, not `inspect`/`discover`.** A
process where one order yields many subscriptions, or one account spans many
orders, has no case id that is not a distortion. `pmx ocel inspect` quantifies
that distortion before anything is mined; use it to decide whether flattening
is defensible at all.

It **cannot** do conformance checking, bottleneck or waiting-time analysis,
social-network mining, or filtering. If the user asks for those, say so
plainly rather than approximating with `discover` -- the answer would be
misleading. `inspect` reports a time span, not per-activity durations, so it
is not a performance tool.

## Before running anything

Check the CLI is reachable, in this order:

```bash
pmx --version || uv run --project <path-to-pmx> pmx --version
```

If neither works, try `~/.local/bin/pmx --version` -- `uv tool install` puts
executables there, and that directory is frequently not on PATH. If it is
there, use that absolute path for the whole task and mention the one-time fix
(`uv tool update-shell`) once, at the end.

If it is genuinely not installed, `uv tool install <path-to-pmx>` installs it;
`uv run --project <path-to-pmx> pmx` works without installing anything.

Every example below writes plain `pmx`. Substitute whichever invocation the
check above found, and do not re-probe on every command.

## Workflow

Always `inspect` before `discover`. The profile tells you whether the log is
even well-formed, and the variant count predicts whether the model will be
readable.

1. **Inspect.** `pmx inspect LOG` -- confirm the counts look sane. A log where
   cases ≈ events means one event per case and nothing to mine. A log with
   one variant is a straight line.
2. **Report what you found** before mining: the four headline counts, the time
   span, and the top variants. State the variant count explicitly -- it is
   what justifies the threshold you pick in step 4.
3. **Discover, and render.**

   ```bash
   pmx discover LOG -o model.bpmn --notation bpmn -i model.png
   ```

   **Always pass `-i` when Graphviz is available.** A `.pnml` or `.bpmn` file
   is XML: it is the machine-readable artifact, not an answer. Someone who
   asked what their process looks like cannot read one. Render the image and
   show it to them; keep the model file as the by-product.

   Use `--notation bpmn` when a human is the audience and `petri` when the
   model feeds another tool. Check Graphviz once with `command -v dot`; if it
   is missing, still write the model, say the image needs
   `brew install graphviz`, and describe the process from the variant list
   instead.
4. **Iterate on complexity.** If the model is large, raise
   `--noise-threshold` and re-run. See
   [references/interpreting.md](references/interpreting.md).

## Commands

```bash
pmx inspect LOG [-n TOP] [--json]
pmx discover LOG [-a ALGO] [--notation petri|bpmn] [-o FILE] [-i IMAGE]
                 [--noise-threshold F] [--dependency-threshold F] [--bgcolor C]
pmx dfg LOG [--json] [-o FILE] [-i IMAGE] [--max-edges N] [--bgcolor C]

pmx ocel inspect  OCEL [--json] [-n TOP]
pmx ocel discover OCEL [--notation ocdfg|ocpn] [-i IMAGE]
pmx ocel flatten  OCEL -t TYPE -o FILE
```

`dfg` counts which activity directly follows which, across the whole log.
Reach for it when the question is "how often does X lead to Y" rather than
"what is the model" -- it generalises nothing and filters nothing, so its
counts are exact where a mined model's are not.

Both accept `--case-id`, `--activity-key`, `--timestamp-key`, `--separator`
for delimited input. Full flag reference:
[references/commands.md](references/commands.md).

Use `--json` whenever you need to read numbers back rather than show a table
to the user -- it is stable and parseable, the tables are not.

## Reading the input file

`.xes` and `.xes.gz` need no flags. Anything else is read as delimited text
and needs its three columns mapped:

```bash
pmx inspect orders.csv \
  --case-id "Case ID" --activity-key "Activity" --timestamp-key "Timestamp"
```

**Do not guess the column names.** Read the header row first (`head -1`), then
map. A CSV exported from a process-mining tool often *already* uses the XES
names (`case:concept:name`, `concept:name`, `time:timestamp`), in which case
passing flags is what breaks it -- run with no flags.

If a mapping is wrong, the error lists the columns the file actually has. Use
that list rather than guessing again.

## Output contract

`discover` prints **one written path per line on stdout** and its progress on
stderr, so its stdout can be piped or captured directly. `inspect --json`
prints only JSON on stdout. pm4py writes a progress bar and an occasional
warning to stderr; ignore both.

With no `-o`, `discover` writes next to the input log with a `.pnml` or
`.bpmn` suffix. Prefer passing `-o` explicitly so you know where the file
landed and do not litter the user's data directory.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `missing case id column '...'` | Wrong or unneeded `--case-id`/`--activity-key`/`--timestamp-key` | Read the column list in the error; re-map, or drop the flags entirely |
| `rendering needs the Graphviz 'dot' binary` | `-i/--image` without Graphviz | `brew install graphviz` / `apt install graphviz`, or drop `-i` |
| `can only discover BPMN with the inductive miner` | `--notation bpmn` plus `-a heuristics/alpha` | Drop `-a`, or switch to `--notation petri` |
| BPMN file has no diagram layout | Graphviz missing; export degrades on purpose | Valid BPMN either way -- install Graphviz only if you need coordinates |
| Model is an unreadable tangle | Real-world log with many rare paths | Raise `--noise-threshold`; see references/interpreting.md |
| `pmx: command not found` | `~/.local/bin` not on PATH | Use `~/.local/bin/pmx`, or `uv run --project <path> pmx` |

Every error exits 1 with a one-line message on stderr. Report the message to
the user rather than re-running blind.

## Worked example

```bash
pmx inspect examples/data/running-example.xes -n 5
pmx discover examples/data/running-example.xes -o /tmp/running.pnml
```

Yields 42 events / 6 cases / 8 activities / 6 variants, then a 10-transition
Petri net. pm4py's own test logs are a good source of sample data; the pmx
repo has `examples/fetch-sample-logs.sh` to download them.
