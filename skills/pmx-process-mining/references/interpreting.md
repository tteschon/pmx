# Interpreting pmx output

Load this when deciding which miner to use, or when a discovered model needs
to be made readable.

## Reading an `inspect` profile

| What you see | What it means | What to do |
|---|---|---|
| `cases` ≈ `events` | One event per case -- no sequences | Nothing to mine; the case column is probably wrong |
| `variants` = 1 | Every case follows the same path | The model will be a straight line, which is correct |
| `variants` ≈ `cases` | Almost every case is unique | Expect a tangled model; plan on `--noise-threshold` |
| Many `end_activities` | Cases finish in many states | Often real (cancellations, rejections), sometimes truncated data |
| One `start_activity` | Clean, well-scoped log | Good sign |

Variant count is the single best predictor of model readability. Under ~20 and
the model is usually legible; in the hundreds it will not be without
filtering.

The `first_event`/`last_event` span is worth checking against what the user
expects. A log that ends months before today is often an extract, and any
conclusion about "current" behaviour would be wrong.

## Choosing a miner

**`inductive`** (default) is the right answer unless you have a reason. It
guarantees a *sound* model -- no deadlocks, every task reachable, always able
to reach completion. Its `--noise-threshold` is the only principled complexity
control the CLI offers.

**`heuristics`** tolerates noise and infrequent behaviour by looking at how
often one activity follows another. Reach for it on messy real-world logs
where the inductive model is dominated by silent transitions. It does not
guarantee soundness, and it cannot produce BPMN here.

**`alpha`** is the original 2004 algorithm, kept for teaching and baselines.
It cannot handle loops of length one or two, silent transitions, or noise, and
it produces unsound models on most real logs. Do not recommend it for
analysis -- only when the user explicitly wants the classic result.

## Making a model readable

Raise `--noise-threshold` and re-run. It filters infrequent behaviour, trading
completeness for legibility:

```bash
pmx discover receipt.xes --noise-threshold 0.0 -o full.pnml
pmx discover receipt.xes --noise-threshold 0.2 -o simpler.pnml
```

On pm4py's `receipt.xes` (1,434 cases) this drops the net from 74 transitions
to 66. The effect is real but gradual -- 0.2 is a reasonable first step, and
values above ~0.5 discard so much that the model stops describing the log.

Always tell the user which threshold produced a model. A filtered model is a
claim about *frequent* behaviour, not about the process, and presenting one
without that caveat overstates it.

For the heuristics miner the equivalent knob is `--dependency-threshold`:
raising it keeps only edges with stronger evidence, which also thins the
model.

## What the output files are

**PNML** (`.pnml`) is a Petri net: places, transitions, arcs, plus an initial
and final marking. Transitions with no label are *silent* -- routing
constructs the miner added, not real activities. A model full of them usually
means the log has more concurrency than the notation shows comfortably.

**BPMN** (`.bpmn`) is the business-facing notation, and the one to hand to
someone who is not a process-mining specialist. It opens in Camunda Modeler,
bpmn.io, and Signavio.

Both are XML and safe to read directly if you need to count elements, but do
not try to reason about process semantics by reading the raw XML -- render it
or report the `inspect` variants instead.

## Honest limits

`discover` tells you what a model *looks like*. It does not tell you how well
that model fits the log -- that is conformance checking, which this CLI does
not do. Never describe a discovered model as "accurate", "validated", or
"87% conformant". The defensible statement is that the model was mined from
the log with a named algorithm at a named threshold.
