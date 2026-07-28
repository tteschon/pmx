# Testing the pmx-process-mining skill

Three things can break independently. Test them separately -- a skill that
validates cleanly can still never fire, and one that fires reliably can still
give bad answers.

## 1. Format

```bash
uvx --from "git+https://github.com/agentskills/agentskills#subdirectory=skills-ref" \
  skills-ref validate ./skills/pmx-process-mining
```

Catches frontmatter and naming violations only. It says nothing about whether
the skill is any good. Run it after every edit; it takes a second.

## 2. Triggering

The failure mode here is silent: the skill simply never activates, and the
agent free-solos with raw `pm4py` or refuses. Load the skill first
(`/reload-skills`, or restart the session), then start a **fresh** session for
each prompt -- once a skill is active in a conversation the test is worthless.

### Should activate

| Prompt | Why it should fire |
|---|---|
| "What does the process in `receipt.xes` actually look like?" | Core phrasing, named XES file |
| "I have an event log, can you find the most common paths?" | "event log" + "common paths" |
| "Mine a BPMN model from this log" | Notation keyword |
| "Do some process mining on `orders.csv`" | Domain name, CSV input |
| "How many variants are in `helpdesk.xes.gz`?" | Variant question, gzipped input |
| "Run the inductive miner on this" | Algorithm name, no other context |
| "How often does one step lead to another in this log?" | Should reach for `dfg`, not `discover` |
| "Can pm4py tell me what my process looks like?" | Names the library, not the CLI |

### Should NOT activate

| Prompt | Why a false positive matters |
|---|---|
| "Check whether our process follows the documented standard" | Conformance checking -- out of scope, and a wrong answer looks plausible |
| "Where are the bottlenecks in this process?" | Performance analysis -- `inspect` reports a span, not durations |
| "Summarise this CSV of sales figures" | Ordinary tabular data with no case/activity/timestamp structure |
| "Refactor the discovery module" | Editing the pmx source, not using the CLI |

The two out-of-scope process-mining prompts matter most. If the skill fires
there, check that it still refuses per its Scope section -- firing and then
declining cleanly is acceptable; firing and improvising is the failure.

## 3. Execution

Give the agent a real task in a fresh session and check the transcript against
these criteria.

**Task A -- "What does the process in `examples/data/roadtraffic100traces.xes`
look like?"**

- [ ] Runs `inspect` **before** `discover`
- [ ] Reports the counts (390 events, 100 cases, 10 activities, 10 variants)
      and the top variants
- [ ] Renders an image with `-i` and shows it -- **not** just a `.pnml` path
- [ ] Does not claim the model is "accurate" or "validated"

**Task B -- "Profile `examples/data/running-example.csv`."**

- [ ] Reads the header row before choosing flags
- [ ] Passes **no** column flags (that file already uses XES names)
- [ ] Gets 42 events / 6 cases / 8 activities / 6 variants

Task B is the trap. An agent that guesses `--case-id case_id` gets an error;
the test is whether it recovers by reading the column list in the message
rather than guessing a second time.

**Task C -- "Does our process conform to the reference model?"**

- [ ] Says plainly that pmx cannot do conformance checking
- [ ] Does not substitute a discovered model as if it answered the question

**Task D -- "How often does each step lead to the next in
`examples/data/receipt.xes`?"**

- [ ] Uses `pmx dfg`, not `discover` or `inspect`
- [ ] Reports 27 activities and 99 transitions
- [ ] Does not present the variant list as a complete transition count

## Automated evals

The `skill-creator` skill can generate and run evals against a skill, with
variance analysis across repeated runs. Worth reaching for once the prompt
lists above stop changing -- a hand-run checklist is fine for one skill, but
it does not catch regressions after an edit.

## Regression log

Defects found by running the checks above, so they are not reintroduced:

- **2026-07-28** -- Workflow step 3 wrote a `.pnml` and stopped, leaving the
  user an XML file they could not read. Fixed by requiring `-i` whenever
  Graphviz is available. Found by executing the workflow literally rather than
  reading it.
- **2026-07-28** -- `pmx dfg --max-edges` crashed with `KeyError` from inside
  pm4py: its `max_num_edges` drops edges but keeps the start/end activities
  pointing at them. pmx now trims first and filters the endpoints to the
  surviving nodes. Covered by `tests/test_dfg.py`.
