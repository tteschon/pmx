# pmx

Process discovery from event logs, on the command line. A thin CLI over
[pm4py](https://github.com/process-intelligence-solutions/pm4py).

Profile a log with `inspect`, mine a model from it with `discover`, count
directly-follows transitions with `dfg`, and handle object-centric logs with
`pmx ocel`.

## Install

```bash
uv sync
```

Rendering models to images additionally needs the Graphviz `dot` binary:

```bash
brew install graphviz
```

Without it, `--image` fails with a clear message and BPMN export falls back to
writing a valid file with no diagram layout. Everything else works.

## Sample data

pm4py's own test logs make the quickest smoke test. Fetch them into
`examples/data/` (gitignored -- they belong to pm4py, and `receipt.xes` alone
is 4 MB):

```bash
./examples/fetch-sample-logs.sh
```

| Log | Cases | Events | Notes |
|---|---|---|---|
| `running-example.xes` | 6 | 42 | The canonical pm4py teaching log. Start here. |
| `running-example.csv` | 6 | 42 | Same log, CSV -- already uses XES column names. |
| `receipt.xes` | 1,434 | 8,577 | A real Dutch municipality permit process. |
| `roadtraffic100traces.xes` | 100 | 566 | Road-fine collection. |
| `helpdesk.xes.gz` | 4,580 | 21,348 | Gzipped, to exercise that path. |

## Usage

Profile a log -- events, cases, activities, variants, case durations, and how
concentrated the variants are:

```bash
uv run pmx inspect examples/data/running-example.xes
```

The variants table carries each variant's share of cases and a running
cumulative, and `inspect` says outright how many variants you need to account
for most of the log. On `receipt.xes`:

```
2 variants cover 50% of cases, 6 cover 80%, 45 cover 95%; 86 occur exactly once
116 variants use only 50 distinct activity sets -- much of this is concurrency; try --top-variants
```

That second line is the tell that a log's variant count overstates its
complexity: when variants collapse to far fewer activity *sets*, they are
re-orderings of the same work, and `--top-variants` will help where
`--noise-threshold` will not.

Machine-readable, for piping into `jq`:

```bash
uv run pmx inspect examples/data/receipt.xes --json | jq '{cases, variants}'
```

Mine a Petri net, writing `running-example.pnml` next to the log:

```bash
uv run pmx discover examples/data/running-example.xes
```

Mine BPMN and render it at the same time:

```bash
uv run pmx discover examples/data/receipt.xes --notation bpmn -o model.bpmn -i model.png
```

`discover` prints one written path per line on stdout and its progress on
stderr, so it composes:

```bash
uv run pmx discover examples/data/running-example.xes | xargs open
```

### Algorithms

`-a/--algorithm` picks the miner. `inductive` (the default) always produces a
sound model; `heuristics` copes better with noisy real-world logs; `alpha` is
the classic baseline and has no tuning knobs.

| Algorithm | Tuning flag | Notations |
|---|---|---|
| `inductive` | `--noise-threshold` (0.0-1.0) | `petri`, `bpmn` |
| `heuristics` | `--dependency-threshold` (0.0-1.0) | `petri` |
| `alpha` | none | `petri` |

Raising `--noise-threshold` filters infrequent behaviour from inside the miner.
On `receipt.xes` it takes the model from 74 transitions to 66:

```bash
uv run pmx discover examples/data/receipt.xes --noise-threshold 0.2 -o simpler.pnml
```

### Making an unreadable model readable

`--noise-threshold` is often not enough, because it cannot remove concurrency.
Where a log's variants are mostly re-orderings of the same activities, the
diagram stays wide however high you push it.

Dropping rare variants from the log before mining is the blunter and far more
effective tool. `--top-variants N` keeps the N most frequent variants;
`--min-coverage F` keeps the fewest variants covering that share of the cases.
Both work on `discover` and `dfg`, and they are mutually exclusive.

```bash
uv run pmx discover examples/data/receipt.xes --top-variants 10 -o model.bpmn --notation bpmn -i model.png
```

On `receipt.xes` that is the difference between an unreadable tangle and a
diagram you can actually read:

| Filter | Transitions | Cases kept |
|---|---|---|
| none | 74 | 100% |
| `--noise-threshold 0.2` | 66 | 100% |
| `--top-variants 10` | 14 | 87.9% |
| `--top-variants 5` | 9 | 79.6% |

The trade is coverage, not correctness, so pmx reports what it kept on stderr:

```
filtered to 10 of 116 variants (1,260 of 1,434 cases, 87.9%)
```

A filtered model is a claim about *frequent* behaviour, not about the whole
process. `pmx inspect` tells you where to set the threshold -- it reports how
many variants cover 50%, 80% and 95% of cases.

### Directly-follows counts

`discover` mines a model that generalises the log. `dfg` does the opposite --
it counts what the log literally contains, so nothing is smoothed away:

```bash
uv run pmx dfg examples/data/receipt.xes --json
```

27 activities, 99 transitions, exact. Useful as a cross-check: the top-25
variant list covers 93% of cases and mentions only 16 of those 27 activities.

`--max-edges` trims the rendered image (99 edges over 27 nodes is a hairball);
the JSON always carries every edge.

```bash
uv run pmx dfg examples/data/receipt.xes -i map.svg --max-edges 20
```

### Object-centric mining

Some processes have no single case. An order provisions several subscriptions;
a subscription outlives the order that created it. Any case id you pick
distorts the result, so `pmx ocel` works on
[OCEL](https://www.ocel-standard.org/) logs instead — one row per
(event, object) pair, no case id at all.

```bash
uv run pmx ocel inspect log.json      # object types, and what flattening costs
uv run pmx ocel discover log.json -i map.svg                 # OC-DFG
uv run pmx ocel discover log.json --notation ocpn -i net.svg # Petri net per type
```

`inspect` prices up the two distortions before you commit to a case id:

- **Convergence** — an event touching three objects of the chosen type becomes
  three rows, inflating every count and duration downstream.
- **Divergence** — one object's life spanning several of another type, so the
  case id merges lifecycles that are separate or splits ones that are not.

`flatten` is the bridge back to the case-centric commands, and warns when the
type you picked is convergent:

```bash
uv run pmx ocel flatten log.json -t subscription -o subs.xes
uv run pmx inspect subs.xes
```

Reads OCEL 1.0 and 2.0 in JSON, XML, SQLite, and CSV; the reader is chosen from
the suffix, newest format first.

### CSV input

`.xes` and `.xes.gz` are read directly. Any other file is treated as delimited
text, and needs its columns mapped to the three roles pm4py cares about:

```bash
uv run pmx inspect orders.csv \
  --case-id "Case ID" --activity-key "Activity" --timestamp-key "Timestamp"
```

Use `--separator` for anything that is not comma-delimited. A CSV that already
uses the XES names (`case:concept:name`, `concept:name`, `time:timestamp`)
needs no flags -- `examples/data/running-example.csv` is one of those. Get the
mapping wrong and the error lists the columns the file actually has.

## Agent skill

`skills/pmx-process-mining/` wraps this CLI as an
[Agent Skill](https://agentskills.io/specification), so an agent can drive it
without being told the flags each time.

```bash
mkdir -p ~/.claude/skills
ln -sfn "$PWD/skills/pmx-process-mining" ~/.claude/skills/pmx-process-mining
```

Symlinked rather than copied, so edits to the skill track the CLI it documents.
Validate after changing it:

```bash
uvx --from "git+https://github.com/agentskills/agentskills#subdirectory=skills-ref" \
  skills-ref validate ./skills/pmx-process-mining
```

## Development

```bash
uv run pytest         # tests
uv run ruff check .   # lint
uv run ruff format .  # format
uv run ty check       # types
uv add <package>      # dependencies
```

`uvx pre-commit install` wires lint, format, and types into every commit.

## Licensing

pmx is **AGPL-3.0-or-later**. Full text in [LICENSE](LICENSE).

That is not a free choice. pmx imports pm4py, which is AGPL v3, making the two
a combined work — so pmx cannot be distributed under a permissive licence such
as MIT while it depends on pm4py. AGPL is the only option that lets pmx be
distributed as it stands.

What this means in practice:

- **Running it locally**: no obligations. Private use is unrestricted.
- **Distributing it**, or **running it behind a network service** that users
  interact with: you must offer the complete corresponding source under the
  AGPL, including any changes you make. Section 13 is what makes the network
  case count, and it is the clause people miss.

If you need to ship pmx without open-sourcing what it is part of, the route is
a commercial pm4py licence from its authors — see
[processintelligence.solutions](https://processintelligence.solutions/pm4py#licensing).
Relicensing pmx alone does not help; the obligation comes from pm4py.

## Dashboard

`dashboard/index.html` is a self-contained page that reads the JSON from
`pmx inspect --json` — no build step, no server, no network.

```bash
pmx inspect examples/data/receipt.xes --json -n 25 | pbcopy
```

Open the page, hit **Load your own**, paste. It ships with four of pm4py's
logs already embedded so it is useful before you point it at anything.

The hero is variant coverage: how few distinct paths account for most of your
cases, and how long the tail is behind them. Everything is computed in the
browser, so a log you cannot upload anywhere is still fine to look at.

Two panels take extra input:

- **The mined model** shows the BPMN that `discover` mined from whichever log is
  selected — all four sample logs ship with theirs, so it is populated on open.
  To see your own, paste the SVG from `discover -i`; **Remove** drops the paste
  and falls back to the bundled one.

  ```bash
  pmx discover YOUR_LOG.xes --notation bpmn -o m.bpmn -i m.svg --bgcolor transparent
  ```

  `--bgcolor transparent` is what lets it sit on either theme: the page strips
  the Graphviz background and remaps its black ink to follow your theme, while
  leaving frequency-shaded nodes and their labels readable on their own fill.

- **Transitions** shows exact directly-follows counts. The same paste box takes
  either payload — it tells `inspect` and `dfg` output apart by shape.

  ```bash
  pmx dfg YOUR_LOG.xes --json | pbcopy
  ```

Pasted SVG is sanitised before it touches the DOM: scripts, event handlers,
`foreignObject`, and external references are stripped. The published artifact's
CSP would block inline script anyway, but the file also opens straight from
disk, where it would not.
