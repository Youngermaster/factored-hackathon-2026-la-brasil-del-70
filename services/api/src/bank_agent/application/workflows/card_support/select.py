"""UNDERSTAND, SELECT_CARD, and CLARIFY for card support: what the customer wants, and which of their own cards.

``extract_card_support_slots`` runs through the gateway with a deterministic fallback. SELECT_CARD uses only the
session customer's cards (``list_my_cards``); with more than one plausible card, CLARIFY offers masked options
(type and last four). Unblock and replacement requests are escalation-only: the kernel's CRD rules escalate them with
a ``card_request`` section, except that a lost or stolen card gets the protective block offer first.
"""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import evaluate
from bank_agent.application.engine.llm import EXTRACT_CARD, structured
from bank_agent.application.engine.reply import Choices, Masked, Param, Reply
from bank_agent.application.engine.shared import blocking_step, escalate_decision, spend_clarification
from bank_agent.application.engine.templates.labels import CARD_TYPES
from bank_agent.application.understanding import extraction
from bank_agent.application.understanding.answers import parse_choice
from bank_agent.application.workflows.card_support.data import INTENT_ACTIONS, CardData, load, save
from bank_agent.domain.cards import CardAction, CardBlockReason, CardRequest, CardStatusView
from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.identifiers import ProductId, SourceRef, SourceTable
from bank_agent.domain.llm_outputs import CardSupportSlotExtraction
from bank_agent.domain.locale import Language
from bank_agent.domain.product import ProductStatus
from bank_agent.domain.workflow import Intent, Outcome
from bank_agent.policy.facts import CardFacts

SELECT_CARD = "SELECT_CARD"
CLARIFY = "CLARIFY"
CARD_STATUS = "CARD_STATUS"
CONFIRM_BLOCK = "CONFIRM_BLOCK"
URGENT_REASONS = frozenset({CardBlockReason.LOST, CardBlockReason.STOLEN})
WHICH_CARD = ("Which card does the customer mean?",)


async def absorb(ctx: TurnContext, data: CardData) -> CardData:
    variables = {"customer_message": ctx.text, "dialect_hint": ctx.locale.value}
    model = await structured(ctx, EXTRACT_CARD, variables, CardSupportSlotExtraction)
    routed = ctx.prediction.intent if ctx.prediction is not None else None
    action = INTENT_ACTIONS.get(routed) if routed is not None else None
    if action is None:
        action = extraction.card_action(ctx.text) or (model.requested_action if model is not None else None)
    reason = extraction.block_reason(ctx.text)
    if reason is None and model is not None and model.block_reason_candidates:
        reason = model.block_reason_candidates[0]
    hint = model.card_hint if model is not None else None
    return data.evolve(
        action=action if routed is not None or action is not None else data.action,
        block_reason=reason or data.block_reason,
        hint_type=extraction.card_type(ctx.text) or (hint.card_type if hint else None) or data.hint_type,
        hint_last4=extraction.card_last4(ctx.text) or (hint.last4 if hint else None) or data.hint_last4,
    )


ACTION_INTENTS = {action: intent for intent, action in INTENT_ACTIONS.items()}


async def understand(ctx: TurnContext) -> Step:
    data = await absorb(ctx, load(ctx).evolve(product_id=None, answered=False, confirm_shown=False))
    intent = ACTION_INTENTS.get(data.action) if data.action is not None else Intent.CARD_STATUS
    ctx.engine = ctx.engine.evolve(intent=intent)
    save(ctx, data)
    return Step(SELECT_CARD)


def _label(ctx: TurnContext, card: CardStatusView) -> str:
    language = Language.ES if ctx.language is Language.EN else ctx.language
    return CARD_TYPES[card.card_type][language]


def _options_reply(ctx: TurnContext, cards: list[CardStatusView], *, unanswered: bool = False) -> Step:
    items: tuple[dict[str, Param], ...] = tuple(
        {"type": _label(ctx, card), "card": Masked(card.masked_number.last4)} for card in cards
    )
    reply = Reply(template="card.clarify_options", params={"options": Choices("card.option", items)})
    return Step(CLARIFY, reply, Outcome.CLARIFIED, unanswered=unanswered)


def _plausible(data: CardData, cards: list[CardStatusView]) -> list[CardStatusView]:
    narrowed = cards
    if data.hint_last4 is not None:
        narrowed = [card for card in narrowed if card.masked_number.last4 == data.hint_last4] or narrowed
    if data.hint_type is not None:
        narrowed = [card for card in narrowed if card.card_type is data.hint_type] or narrowed
    if data.action is CardAction.BLOCK and len(narrowed) > 1:
        narrowed = [card for card in narrowed if card.status is ProductStatus.ACTIVE] or narrowed
    return narrowed


async def _chosen(ctx: TurnContext, data: CardData, card: CardStatusView) -> Step:
    product = ProductId(card.product_ref.key)
    data = data.evolve(
        product_id=product, last4=card.masked_number.last4, card_type=card.card_type, status=card.status, option_ids=()
    )
    ctx.engine = ctx.engine.evolve(carried_card=card.product_ref).with_fact(
        f"card ending {card.masked_number.last4} ({card.card_type}) is {card.status}", card.product_ref
    )
    save(ctx, data)
    facts = CardFacts(owned_by_session_customer=True, is_card=True, status=card.status, request=data.action)
    urgent = data.block_reason in URGENT_REASONS and card.status is ProductStatus.ACTIVE
    if data.action is CardAction.REPLACEMENT_REQUEST and urgent and not data.block_first:
        save(ctx, data.evolve(block_first=True, action=CardAction.REPLACEMENT_REQUEST))
        return Step(CONFIRM_BLOCK)
    decision = evaluate(ctx, card=facts)
    if decision.kind is DecisionKind.ESCALATE and data.action in (
        CardAction.UNBLOCK_REQUEST,
        CardAction.REPLACEMENT_REQUEST,
    ):
        request = CardRequest(action=data.action, product_ref=card.product_ref)
        return escalate_decision(ctx, decision, card_request=request)
    stop = blocking_step(ctx, decision, state=SELECT_CARD)
    if stop is not None:
        return stop
    return Step(CONFIRM_BLOCK if data.action is CardAction.BLOCK else CARD_STATUS)


async def select_card(ctx: TurnContext) -> Step:
    data = load(ctx)
    cards = list(await ctx.tools.list_my_cards())
    if data.product_id is not None:
        current = next((card for card in cards if card.product_ref.key == data.product_id), None)
        if current is not None:
            return await _chosen(ctx, data, current)
    if not cards:
        return Step("RESOLVED", Reply(template="card.no_cards"), Outcome.RESOLVED)
    plausible = _plausible(data, cards)
    if len(plausible) == 1:
        return await _chosen(ctx, data, plausible[0])
    stop = spend_clarification(ctx, open_questions=WHICH_CARD)
    if stop is not None:
        return stop
    save(ctx, data.evolve(option_ids=tuple(ProductId(card.product_ref.key) for card in plausible)))
    return _options_reply(ctx, plausible)


async def clarify(ctx: TurnContext) -> Step:
    data = load(ctx)
    cards = {card.product_ref.key: card for card in await ctx.tools.list_my_cards()}
    options = [cards[key] for key in data.option_ids if key in cards]
    if ctx.reprompt:
        return _options_reply(ctx, options)

    def matches(folded: str, card: CardStatusView) -> bool:
        spoken = folded.split()
        type_word = "credito" if card.card_type.value == "credit_card" else "debito"
        return card.masked_number.last4 in spoken or type_word in spoken

    index = parse_choice(ctx.text, options, matches)
    if index is None:
        stop = spend_clarification(ctx, open_questions=WHICH_CARD)
        return stop or _options_reply(ctx, options, unanswered=True)
    return await _chosen(ctx, data, options[index])


def card_ref(data: CardData) -> SourceRef | None:
    return SourceRef.of(SourceTable.PRODUCTS, data.product_id) if data.product_id is not None else None
