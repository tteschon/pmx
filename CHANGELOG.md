# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-09-28

First public release.

### Added

- `pmx inspect` — profile an event log: events, cases, activities, variants,
  start and end activities, and the most frequent variants with their share of
  cases and a running cumulative.
- Variant concentration statistics: how many variants cover 50%, 80% and 95%
  of cases, how many occur exactly once, and how many distinct activity *sets*
  the variants collapse to. A variant count far above the activity-set count
  means the log's apparent complexity is concurrency rather than genuinely
  different behaviour.
- Case duration statistics — median, mean, p90, min and max — reported in
  seconds in `--json` and humanised in the table.
- `pmx discover` — mine a process model with the inductive, heuristics, or
  alpha miner, as a Petri net (PNML) or BPMN, with optional Graphviz
  rendering.
- `--top-variants N` and `--min-coverage F` on `discover` and `dfg`, dropping
  rare variants before mining. On pm4py's `receipt.xes` this takes the model
  from 74 transitions to 14 while still covering 88% of cases, where
  `--noise-threshold` only reaches 66. Every filter reports what it kept on
  stderr, because a filtered model describes frequent behaviour rather than
  the whole process.
- `pmx dfg` — exact directly-follows counts, as JSON, an image, or a table.
- `pmx ocel` — object-centric mining: `inspect` (with convergence and
  divergence diagnostics), `discover` (OC-DFG and OC-PN), and `flatten`.
- A self-contained HTML dashboard, and a Claude Code agent skill under
  `skills/`. The dashboard reads `inspect --json` and `dfg --json` output,
  and can mine connected applications directly through a Salesforce
  capability, with an explicit consent step and configurable object
  mapping. Neither the dashboard nor the skill ships in the installed
  package -- both live in the repository.

### Notes

- The distribution is **`pmx-cli`** on PyPI, because `pmx` is held by an
  unrelated molecular-dynamics project. The command, the import package, and
  everything you type stay `pmx`. Installing both distributions into the same
  environment would collide; they have disjoint audiences, but it is worth
  knowing.
- Rendering images requires the Graphviz `dot` **system** binary, which pip
  cannot install. Everything else works without it, and `--image` fails with a
  message naming the install command for your platform.
- Licensed AGPL-3.0-or-later, which is not a free choice: pmx links pm4py,
  which is AGPL v3. See the Licensing section of the README before
  distributing this or putting it behind a network service.

[Unreleased]: https://github.com/tteschon/pmx/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/tteschon/pmx/releases/tag/v0.2.0
