"""The pre-registered rule for switching production retrieval from BM25 to the Qdrant hybrid (ADR 0047).

Registered on 2026-10-05, before the hosted embeddings were recorded: production switches to ``qdrant_hybrid`` only
if, on the test split of the relevance judgments,

1. it beats BM25: a higher mean reciprocal rank over the in-scope queries, and
2. it loses no recall in either language: for Spanish and for Portuguese, recall at 1, 3, and 5 each at least
   BM25's, and
3. (a safety guard added at registration) it abstains on at least as many out-of-scope queries as BM25.

Every check must pass. The rule reads only the generated metrics, so the report states its outcome mechanically;
the judgments are still pending human review, so a pass is provisional evidence, not proof.
"""

from dataclasses import dataclass

from bank_evals.retrieval.evaluation import RetrievalEvaluation
from bank_evals.retrieval.runner import RetrieverReport, SliceMetrics

CANDIDATE = "qdrant_hybrid"
BASELINE = "bm25"
LANGUAGES = ("es", "pt")


@dataclass(frozen=True)
class Check:
    name: str
    candidate: float | None
    baseline: float | None
    passed: bool


@dataclass(frozen=True)
class SwitchDecision:
    candidate: str
    baseline: str
    checks: tuple[Check, ...]

    @property
    def switch(self) -> bool:
        return all(check.passed for check in self.checks)


def _report(evaluation: RetrievalEvaluation, name: str) -> RetrieverReport | None:
    return next((report for report in evaluation.reports if report.name == name), None)


def _slice(report: RetrieverReport, name: str) -> SliceMetrics | None:
    return next((item for item in report.slices if item.name == name), None)


def _at_least(name: str, candidate: float | None, baseline: float | None, *, strictly: bool = False) -> Check:
    if candidate is None or baseline is None:
        return Check(name, candidate, baseline, passed=False)
    passed = candidate > baseline if strictly else candidate >= baseline
    return Check(name, candidate, baseline, passed=passed)


def decide(evaluation: RetrievalEvaluation) -> SwitchDecision | None:
    """The rule's checks, or ``None`` when the candidate was not evaluated (no recorded embeddings)."""
    candidate, baseline = _report(evaluation, CANDIDATE), _report(evaluation, BASELINE)
    if candidate is None or baseline is None:
        return None
    checks = [_at_least("test MRR is higher", candidate.test.mrr, baseline.test.mrr, strictly=True)]
    for language in LANGUAGES:
        mine, theirs = _slice(candidate, f"language={language}"), _slice(baseline, f"language={language}")
        for k in (1, 3, 5):
            field = f"recall_at_{k}"
            checks.append(
                _at_least(
                    f"{language} recall@{k} is not lower",
                    getattr(mine, field) if mine is not None else None,
                    getattr(theirs, field) if theirs is not None else None,
                )
            )
    checks.append(
        _at_least(
            "out-of-scope abstention recall is not lower",
            candidate.test.abstention_recall,
            baseline.test.abstention_recall,
        )
    )
    return SwitchDecision(candidate=CANDIDATE, baseline=BASELINE, checks=tuple(checks))
