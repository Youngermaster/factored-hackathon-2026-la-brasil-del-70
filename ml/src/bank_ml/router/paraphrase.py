"""Language-model paraphrases of router seeds, generated offline through the ``bank_agent`` gateway.

Two prompts, so evaluation text never comes from the prompt that produced training text
(``docs/analysis/labeling-protocol.md``):

- ``train``: ``paraphrase_router_seed@1`` over canonical seeds of the train split; the items join training.
- ``eval``: ``paraphrase_router_eval@1`` over canonical seeds of the test split; the items form the paraphrase
  robustness set and never enter training.

The client is the full gateway stack (redaction, budget, tracing, retries) built from ``LLM_*`` settings, so the
cassette provider can replay recorded calls. With ``LLM_PROVIDER=fake`` (no provider chosen) the first call is
refused and generation stops with that reason; nothing is written and no cassette is invented. Every generated item
carries ``provenance: llm_paraphrased:<seed_id>``, the prompt, the model id, and ``review_status: pending``.
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from bank_agent.adapters.prompts.file_registry import FilePromptRegistry
from bank_agent.adapters.system.clock import SystemClock
from bank_agent.adapters.telemetry.noop import NoopTelemetry
from bank_agent.bootstrap.llm import build_llm_client
from bank_agent.bootstrap.settings import LLMSettings
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import LlmError, LlmProviderRejectedError
from bank_agent.domain.intelligence import LlmCallContext, PromptRef, PromptValue
from bank_agent.domain.llm_outputs import UtteranceParaphrases
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent
from bank_agent.ports.llm import LLMClient
from bank_ml.router.augment import Item, fill
from bank_ml.router.corpus import CORPUS_DIR, SLOT_PATTERN, SLOTS, Lexicon, Seed

Purpose = Literal["train", "eval"]
PROMPTS: dict[Purpose, PromptRef] = {
    "train": PromptRef.model_validate("paraphrase_router_seed@1"),
    "eval": PromptRef.model_validate("paraphrase_router_eval@1"),
}
SPLIT_OF: dict[Purpose, str] = {"train": "train", "eval": "test"}
PER_SEED = 3
DESCRIPTIONS: dict[Intent, str] = {
    Intent.DISPUTE_NEW: "The customer contests a specific charge on their own account or card and wants to claim it.",
    Intent.DISPUTE_STATUS: "The customer asks about the progress of a dispute they already filed.",
    Intent.CARD_BLOCK: "The customer wants a card blocked or frozen now.",
    Intent.CARD_STATUS: "The customer asks whether a card is active, blocked, or expired, or why it was declined.",
    Intent.CARD_UNBLOCK_REQUEST: "The customer wants a blocked card unblocked or reactivated.",
    Intent.CARD_REPLACEMENT_REQUEST: "The customer wants a new or replacement card.",
    Intent.BALANCE_INQUIRY: "The customer asks the balance of an account or card, or their available credit.",
    Intent.PAYMENT_STATUS: "The customer asks whether a payment or transfer they made went through or arrived.",
    Intent.STATEMENT_REQUEST: "The customer wants a summary of movements of an account or card for a period.",
    Intent.CREDIT_PRODUCT_INFO: "The customer asks what credit products exist or their general conditions.",
    Intent.CREDIT_ELIGIBILITY: "The customer asks whether they would qualify for a credit product.",
    Intent.CREDIT_APPLICATION: "The customer wants to apply for a credit product.",
    Intent.CREDIT_APPLICATION_STATUS: "The customer asks the status of a credit application they submitted.",
    Intent.INFORMATIONAL: "The customer asks how a bank policy or process works in general, not about their records.",
    Intent.HUMAN_REQUEST: "The customer asks to talk to a person.",
    Intent.GREETING_OR_OTHER: "The customer greets, thanks, says goodbye, or asks for help without saying what.",
    Intent.UNSUPPORTED: "The customer asks for something the assistant does not handle, inside or outside banking.",
}


@dataclass(frozen=True)
class GenerationResult:
    purpose: Purpose
    written: int
    failed: int
    stopped: str | None
    path: Path | None


def paraphrase_file(purpose: Purpose, corpus_dir: Path = CORPUS_DIR) -> Path:
    return corpus_dir / "paraphrases" / f"{PROMPTS[purpose]}.jsonl"


def build_client(settings: LLMSettings | None = None) -> LLMClient:
    return build_llm_client(
        settings or LLMSettings(),
        registry=FilePromptRegistry.from_package(),
        clock=SystemClock(),
        telemetry=NoopTelemetry(),
    )


async def generate(
    client: LLMClient, seeds: Sequence[Seed], purpose: Purpose, corpus_dir: Path = CORPUS_DIR
) -> GenerationResult:
    """Paraphrase ``seeds`` (already restricted to the purpose's split) and write the JSONL file."""
    prompt = PROMPTS[purpose]
    rows: list[dict[str, str]] = []
    failed = 0
    for seed in seeds:
        variables: dict[str, PromptValue] = {
            "seed_text": UntrustedText(seed.template),
            "locale": seed.locale,
            "intent_description": DESCRIPTIONS[seed.intent],
            "count": PER_SEED,
        }
        try:
            result = await client.generate_structured(
                prompt,
                variables,
                UtteranceParaphrases,
                language=Language.PT if seed.language == "pt" else Language.ES,
                max_output_tokens=400,
                temperature=0.7,
                call_context=LlmCallContext(),
            )
        except LlmProviderRejectedError as error:
            return GenerationResult(purpose, 0, failed, f"provider refused the call: {error}", None)
        except LlmError:
            failed += 1
            continue
        for text in dict.fromkeys(result.value.paraphrases):
            if text.strip().casefold() != seed.template.strip().casefold():
                rows.append(
                    {
                        "seed_id": seed.seed_id,
                        "text": text,
                        "provenance": f"llm_paraphrased:{seed.seed_id}",
                        "prompt": str(prompt),
                        "model_id": result.model_id,
                        "review_status": "pending",
                    }
                )
    path = paraphrase_file(purpose, corpus_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    return GenerationResult(purpose, len(rows), failed, None, path)


def load_paraphrases(
    purpose: Purpose, seeds: Sequence[Seed], lexicon: Lexicon, corpus_dir: Path = CORPUS_DIR
) -> list[Item]:
    """The stored paraphrases as items (slots filled canonically); an absent file means none were generated."""
    path = paraphrase_file(purpose, corpus_dir)
    if not path.is_file():
        return []
    by_id = {seed.seed_id: seed for seed in seeds}
    items: list[Item] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        row = json.loads(line)
        seed = by_id.get(row["seed_id"])
        if seed is None or row.get("prompt") != str(PROMPTS[purpose]) or set(SLOT_PATTERN.findall(row["text"])) - SLOTS:
            continue
        text = fill(Seed(seed.seed_id, seed.intent, seed.locale, row["text"], seed.scope), lexicon, None)
        items.append(
            Item(
                item_id=f"{seed.seed_id}#p{purpose[0]}{number:04d}",
                seed_id=seed.seed_id,
                intent=seed.intent,
                locale=seed.locale,
                text=text,
                provenance=row["provenance"],
                augmentation=f"paraphrase_{purpose}",
                scope=seed.scope,
            )
        )
    return items
