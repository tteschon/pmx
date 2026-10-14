# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Removed

- The `dashboard/` web page. pmx is a command-line tool; the dashboard
  queried Salesforce directly from the browser and no longer used pmx or
  pm4py at all. It never shipped in the installed package. The last version
  is in the repository history: `git show v0.2.1:dashboard/index.html`.
- The `skills/` agent skill. It moved to
  [tteschon/skills](https://github.com/tteschon/skills) as the
  `process-mining` plugin, with its install instructions updated for the
  `pmx-cli` PyPI package. The copy as of 0.2.1 is at
  `git show v0.2.1:skills/pmx-process-mining/SKILL.md`.

## [0.2.1] - 2026-10-13

Makes `pmx discover --noise-threshold` reproducible. That is the only change
to how the installed package behaves; everything else here is CI, tests and
documentation.

### Changed

- CI now also tests against the newest pm4py, not just the version pinned in
  `uv.lock`. `uv tool install` ignores the lock, so the newest pm4py is what
  users actually run. The job runs on every push and pull request and weekly
  on its own, filing an issue when the weekly run fails.
- `DeprecationWarning` and `FutureWarning` now fail the test suite, so a
  pm4py call that is going away surfaces while it still works.
- The CI smoke test parses `pmx inspect --json` output, catching anything
  that writes to stdout outside the test runner's capture.
- Dependabot keeps `uv.lock` and the GitHub Actions versions current. It
  bumps the lock only; the `>=` floors in `pyproject.toml` stay put, and a
  new `lowest-direct` CI job tests every direct dependency at its floor on
  Python 3.11.
- Golden tests pin every figure the docs quote for pm4py's sample logs. CI
  fetches the logs and fails, not skips, if they are missing.
- `examples/fetch-sample-logs.sh` downloads from a pinned pm4py commit and
  checks each file's SHA-256, re-fetching a copy on disk that does not match.
- The release workflow builds without the uv cache, so a poisoned cache entry
  cannot end up in a package published to PyPI.

### Fixed

- `pmx discover --noise-threshold` could return a different model from one
  run to the next: pm4py's noise-filtering inductive miner depends on
  Python's per-process hash seed, and about one run in four differed (66
  transitions instead of 69 on `receipt.xes` at 0.2). The CLI now re-launches
  with `PYTHONHASHSEED=0` unless you set it yourself. Results without a noise
  threshold, and with `--top-variants`, were already stable.
- The docs quoted 66 as where `--noise-threshold` bottoms out on
  `receipt.xes`. With the seed pinned it gives 69 at 0.2, 42 at 0.3 and 57 at
  0.4 -- uneven, but well below 66.
- `roadtraffic100traces.xes` has 390 events, not 566 as the README said.

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

[Unreleased]: https://github.com/tteschon/pmx/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/tteschon/pmx/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/tteschon/pmx/releases/tag/v0.2.0
