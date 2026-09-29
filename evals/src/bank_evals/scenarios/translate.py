"""A Portuguese translation helper for scenario authors, through the gateway (so through cassettes).

It proposes pt-BR phrasings for Spanish texts; each proposal carries ``review_status: pending_review`` and
``provenance: translated`` and must be read by a native speaker before it joins a family file. The committed
phrasings were written by the team directly; this helper is for adding more.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import LlmError
from bank_agent.domain.intelligence import LlmCallContext, PromptRef
from bank_agent.domain.locale import Language
from bank_agent.ports.llm import LLMClient
from bank_evals.scenarios.model import Provenance, ReviewStatus

TRANSLATE_PROMPT: Final = PromptRef(prompt_id="translate_to_portuguese", version=1)


async def propose_portuguese(llm: LLMClient, texts: Sequence[str]) -> list[dict[str, str | None]]:
    """One proposal per Spanish text; ``pt`` is ``None`` when the model could not answer."""
    proposals: list[dict[str, str | None]] = []
    for text in texts:
        try:
            generation = await llm.generate_text(
                TRANSLATE_PROMPT,
                {"spanish_text": UntrustedText(text)},
                language=Language.PT,
                max_output_tokens=200,
                temperature=0.0,
                call_context=LlmCallContext(),
            )
            translated: str | None = generation.text.strip() or None
        except LlmError:
            translated = None
        proposals.append({
            "es": text, "pt": translated, "provenance": Provenance.TRANSLATED.value,
            "review_status": ReviewStatus.PENDING_REVIEW.value,
        })  # fmt: skip
    return proposals
