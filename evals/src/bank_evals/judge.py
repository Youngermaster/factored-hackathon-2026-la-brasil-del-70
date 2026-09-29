"""The language model judge (tone, clarity, language, politeness; ``docs/evaluation/judge-rubric.md``) and its
validation against human ratings.

- ``stratified_sample``: 100 transcripts by default, spread over systems, workflows, and languages by a seeded
  hash, for the judge and for the human raters (one sample, rated by both).
- ``judge``: one ``judge_transcript@1`` call per transcript; a failed call leaves the rating pending.
- ``agreement``: Cohen's kappa and percent agreement per rubric item between judge and human ratings, with the
  1 to 5 scales read as acceptable (4 or 5) or not; "pending" while no human rating exists.

The judge never decides task success or safety: those come from the deterministic graders only.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Sequence
from typing import Any, Final

from bank_agent.domain.errors import LlmError
from bank_agent.domain.intelligence import LlmCallContext, PromptRef
from bank_agent.domain.locale import Language
from bank_agent.ports.llm import LLMClient
from bank_evals.graders.model import CaseResult, JudgeView
from bank_evals.prompts.outputs import JudgeRating

JUDGE_PROMPT: Final = PromptRef(prompt_id="judge_transcript", version=1)
ITEMS: Final = ("language_correct", "tone", "clarity", "politeness", "language_quality")
ACCEPTABLE: Final = 4


def transcript_text(result: CaseResult) -> str:
    return "\n".join(f"Customer: {t.customer_text}\nAssistant: {t.assistant_text}" for t in result.transcript.turns)


def stratified_sample(results: Sequence[CaseResult], size: int = 100, seed: str = "judge-v1") -> list[CaseResult]:
    """Round-robin over (system, workflow, language) strata, each ordered by a seeded hash of the case."""
    strata: dict[tuple[str, str, str], list[CaseResult]] = defaultdict(list)
    for result in results:
        if result.grade is not None and result.run_index == 1 and result.transcript.turns:
            strata[(result.system, str(result.workflow), result.language)].append(result)
    for items in strata.values():
        items.sort(key=lambda r: hashlib.sha256(f"{seed}:{r.system}:{r.scenario_id}".encode()).hexdigest())
    chosen: list[CaseResult] = []
    keys = sorted(strata)
    while len(chosen) < size and any(strata[k] for k in keys):
        for key in keys:
            if strata[key] and len(chosen) < size:
                chosen.append(strata[key].pop(0))
    return chosen


async def judge(llm: LLMClient, result: CaseResult) -> JudgeView | None:
    language = Language(result.language)
    try:
        generation = await llm.generate_structured(
            JUDGE_PROMPT,
            {"expected_language": result.dialect, "transcript": transcript_text(result)[:12000]},
            JudgeRating,
            language=language,
            max_output_tokens=200,
            temperature=0.0,
            call_context=LlmCallContext(),
        )
    except LlmError:
        return None
    rating = generation.value
    return JudgeView(model=generation.model_id, **rating.model_dump())


def _acceptable(item: str, value: Any) -> bool:
    return bool(value) if item == "language_correct" else int(value) >= ACCEPTABLE


def cohen_kappa(pairs: Sequence[tuple[bool, bool]]) -> float | None:
    """Cohen's kappa for two binary raters; ``None`` without pairs or when chance agreement is 1."""
    if not pairs:
        return None
    n = len(pairs)
    observed = sum(a == b for a, b in pairs) / n
    left, right = sum(a for a, _ in pairs) / n, sum(b for _, b in pairs) / n
    expected = left * right + (1 - left) * (1 - right)
    return None if expected == 1 else (observed - expected) / (1 - expected)


def agreement(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Per item: kappa and percent agreement over rows that carry both a ``judge`` and a ``human`` rating."""
    rated = [row for row in rows if row.get("judge") and row.get("human")]
    if not rated:
        return {"status": "pending", "rated": 0, "sample": len(rows)}
    out: dict[str, Any] = {"status": "computed", "rated": len(rated), "sample": len(rows)}
    for item in ITEMS:
        pairs = [(_acceptable(item, row["judge"][item]), _acceptable(item, row["human"][item])) for row in rated]
        out[item] = {"kappa": cohen_kappa(pairs), "percent_agreement": sum(a == b for a, b in pairs) / len(pairs)}
    return out
