# pmx command reference

Full flag list for both commands. Load this when a task needs a flag not
covered by the workflow in `SKILL.md`.

## Shared input flags

These apply to `inspect` and `discover` alike, and only matter for delimited
(non-XES) input.

| Flag | Default | Meaning |
|---|---|---|
| `--case-id` | `case:concept:name` | Column holding the case identifier |
| `--activity-key` | `concept:name` | Column holding the activity name |
| `--timestamp-key` | `time:timestamp` | Column holding the event timestamp |
| `--separator` | `,` | Field separator for delimited input |

The defaults are the XES standard names. A `.xes` or `.xes.gz` file always
uses them, so never pass these flags for XES input.

## `pmx inspect`

```bash
pmx inspect LOG [-n TOP] [--json]
```

| Flag | Default | Meaning |
|---|---|---|
| `-n`, `--top` | `10` | Entries shown per distribution |
| `--json` | off | Emit JSON on stdout instead of tables |

`--top` truncates only the listings. The headline counts (`events`, `cases`,
`activities`, `variants`) are always exact, so `-n 3` does not mean "only 3
activities exist".

### JSON shape

```json
{
  "source": "log.xes",
  "events": 42,
  "cases": 6,
  "activities": 8,
  "variants": 6,
  "first_event": "2010-12-30T11:02:00+00:00",
  "last_event":  "2011-01-24T14:56:00+00:00",
  "top_activities":   {"check ticket": 9},
  "start_activities": {"register request": 6},
  "end_activities":   {"pay compensation": 3},
  "top_variants":     {"register request -> check ticket -> decide": 1}
}
```

Variant keys are activity names joined with ` -> `. `first_event` and
`last_event` are ISO 8601, or `null` for an empty log.

## `pmx discover`

```bash
pmx discover LOG [-a ALGO] [--notation petri|bpmn] [-o FILE] [-i IMAGE]
                 [--noise-threshold F] [--dependency-threshold F]
```

| Flag | Default | Meaning |
|---|---|---|
| `-a`, `--algorithm` | `inductive` | `inductive`, `heuristics`, or `alpha` |
| `--notation` | `petri` | `petri` (PNML) or `bpmn` |
| `-o`, `--output` | log path with new suffix | Where to write the model |
| `-i`, `--image` | none | Also render here (`.png`/`.svg`/`.pdf`) |
| `--noise-threshold` | `0.0` | Inductive miner only, 0.0-1.0 |
| `--dependency-threshold` | `0.5` | Heuristics miner only, 0.0-1.0 |

### Algorithm and notation compatibility

| Algorithm | Tuning flag | `petri` | `bpmn` |
|---|---|---|---|
| `inductive` | `--noise-threshold` | yes | yes |
| `heuristics` | `--dependency-threshold` | yes | **no** |
| `alpha` | none | yes | **no** |

BPMN is only reachable through the inductive miner -- that is a pm4py
limitation, not a pmx one. Asking for `--notation bpmn -a alpha` exits 1.

A tuning flag that does not apply to the chosen algorithm is accepted and
ignored, so `-a alpha --noise-threshold 0.5` silently does nothing to the
result. Do not read that as the threshold having no effect in general.

Out-of-range thresholds are rejected by the CLI before any mining happens.

## `pmx dfg`

```bash
pmx dfg LOG [--json] [-o FILE] [-i IMAGE] [--max-edges N] [--rankdir LR|TB]
            [--bgcolor COLOR] [-n TOP]
```

| Flag | Default | Meaning |
|---|---|---|
| `--json` | off | Emit the graph as JSON on stdout |
| `-o`, `--output` | none | Write the JSON to a file |
| `-i`, `--image` | none | Render the graph (`.png`/`.svg`/`.pdf`) |
| `--max-edges` | all | Keep only the heaviest N edges **in the image** |
| `--rankdir` | `LR` | Graph direction |
| `--bgcolor` | `white` | Image background; `transparent` for embedding |
| `-n`, `--top` | `15` | Edges shown in the terminal table |

With no `--json`, `-o` or `-i` it prints a table. Every written path goes to
stdout, one per line, as `discover` does.

### Exact, unlike everything else here

`dfg` counts the whole log. This matters when comparing against a variant
list: `pmx inspect -n 25` on `receipt.xes` itemises paths covering 93% of
cases and mentioning 16 of 27 activities, while `pmx dfg` on the same log
reports all **27 activities and 99 transitions**. Do not present a
variant-derived transition count as though it were complete.

`--max-edges` trims the *picture* only -- the JSON always carries every edge.
Trimming is done by pmx rather than pm4py, because pm4py's own
`max_num_edges` drops edges while keeping the start/end activities that
referenced them and then raises `KeyError` on the orphan.

A real log makes a dense graph: 27 activities carrying 99 edges is a hairball
at full size. `--max-edges 20` is a sensible first look.

### Graphviz

`-i/--image` needs the Graphviz `dot` binary. It is checked *before* mining,
so a missing binary exits 1 without writing a model -- there is no partial
output to clean up.

BPMN *export* also uses Graphviz, for diagram layout only. Without it the
`.bpmn` file is still written and still valid; it just carries no coordinates,
so an editor opening it will lay the nodes out itself.

The Graphviz binary is a system package, not a Python one. `pip install
graphviz` will not provide it -- that package is a wrapper that shells out to
the binary, and pm4py already depends on it.

## `pmx ocel`

Object-centric logs: one row per (event, object) pair, no case id.

```bash
pmx ocel inspect  OCEL [--json] [-n TOP]
pmx ocel discover OCEL [--notation ocdfg|ocpn] [-i IMAGE] [--annotation frequency|performance]
                       [--noise-threshold F] [--bgcolor COLOR]
pmx ocel flatten  OCEL -t TYPE -o FILE
```

Reads OCEL 1.0 and 2.0 from `.json`, `.xml`, `.sqlite`, `.csv`. The reader is
picked from the suffix, 2.0 first, falling back to 1.0.

### Reading `inspect`

Two tables matter, and both answer "would a case id lie here?":

- **Convergence** — events a flattened log would count more than once. An event
  touching three objects of the chosen type becomes three rows.
- **Divergence** — one object spanning several of another type. Above 1 means
  the case id merges separate lifecycles or splits a single one.

Report both numbers when recommending an approach. If either is above 1 for
every candidate object type, say plainly that no case id is safe.

### Notations

| `--notation` | Produces | Tuning |
|---|---|---|
| `ocdfg` (default) | Directly-follows graph, one coloured flow per object type | `--annotation` |
| `ocpn` | One Petri net per object type, sharing transitions | `--noise-threshold` |

### `flatten` is a bridge, not an answer

It converts an OCEL to a classic log so `pmx inspect` and `pmx discover` can
read it. It prints a warning when the chosen type is convergent. Do not flatten
silently — the warning is the point.
