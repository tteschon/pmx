"""Keeping only the most common variants, so a mined model stays readable.

`--noise-threshold` is the inductive miner's own complexity knob, but it works
*inside* the miner and cannot remove concurrency. On a log whose variants are
mostly re-orderings of the same activities it barely helps: pm4py's
`receipt.xes` goes from 74 transitions to 66 across the whole 0.0-0.6 range,
and the diagram stays unreadable.

Dropping rare variants from the log before mining is the blunter, more
effective tool -- the same log falls to 14 transitions at the top 10 variants,
which still covers 88% of its cases. The trade is honesty, not accuracy: the
result describes *frequent* behaviour, so every filter here reports exactly
what it kept and the CLI prints that alongside the model.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from pmx.logs import DEFAULT_CASE_ID, EventLog


@dataclass(frozen=True)
class FilterReport:
    """What a filter kept, for reporting to the user.

    Carries counts rather than a message so the caller decides the wording,
    and so tests can assert on numbers instead of prose.
    """

    kept_variants: int
    total_variants: int
    kept_cases: int
    total_cases: int

    @property
    def case_share(self) -> float:
        """Fraction of the original cases that survived, 0.0 on an empty log."""
        return self.kept_cases / self.total_cases if self.total_cases else 0.0

    @property
    def is_noop(self) -> bool:
        return self.kept_variants >= self.total_variants


def top_variants(log: EventLog, k: int) -> tuple[EventLog, FilterReport]:
    """Keep the `k` most frequent variants.

    Asking for more variants than the log has is a no-op rather than an error,
    so `--top-variants 50` is safe to apply to any log.
    """
    if k < 1:
        raise ValueError(f"k must be at least 1, got {k}")
    return _apply(log, k)


def variants_covering(log: EventLog, share: float) -> tuple[EventLog, FilterReport]:
    """Keep the fewest variants that together cover `share` of the cases.

    Note this is deliberately *not* `pm4py.filter_variants_by_coverage_percentage`,
    which keeps variants that each individually cover at least the given share
    -- a much harsher filter than the name suggests. On `receipt.xes` asking
    pm4py for 0.8 returns nothing at all, where "the variants making up 80% of
    my cases" is 6 of them.
    """
    if not 0.0 < share <= 1.0:
        raise ValueError(f"share must be in (0.0, 1.0], got {share}")

    counts = _variant_counts(log)
    if not counts:
        return _apply(log, 1)

    target = share * sum(counts)
    cumulative = 0
    needed = len(counts)
    for index, count in enumerate(counts, start=1):
        cumulative += count
        if cumulative >= target:
            needed = index
            break
    return _apply(log, needed)


def _apply(log: EventLog, k: int) -> tuple[EventLog, FilterReport]:
    import pm4py

    frame = log.frame
    total_variants = len(_variant_counts(log))
    total_cases = int(frame[DEFAULT_CASE_ID].nunique())

    if k >= total_variants:
        report = FilterReport(
            kept_variants=total_variants,
            total_variants=total_variants,
            kept_cases=total_cases,
            total_cases=total_cases,
        )
        return log, report

    filtered = pm4py.filter_variants_top_k(frame, k)
    report = FilterReport(
        kept_variants=len(pm4py.get_variants(filtered)),
        total_variants=total_variants,
        kept_cases=int(filtered[DEFAULT_CASE_ID].nunique()),
        total_cases=total_cases,
    )
    return replace(log, frame=filtered), report


def _variant_counts(log: EventLog) -> list[int]:
    """Case counts per variant, descending."""
    from pmx.stats import variant_case_counts

    return variant_case_counts(log.frame)
