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
    # Card selection needs evidence in the customer's text. A model hint alone may invent a type or ending
    # and silently choose one of several cards; leave unsupported hints unset so SELECT_CARD asks instead.
    hint_type = extraction.card_type(ctx.text)
    hint_last4 = extraction.card_last4(ctx.text)
    explicit_card = hint_type is not None or hint_last4 is not None
    return data.evolve(
        action=action if routed is not None or action is not None else data.action,
        block_reason=reason or data.block_reason,
        hint_type=hint_type if explicit_card else data.hint_type,
        hint_last4=hint_last4 if explicit_card else data.hint_last4,
    )


ACTION_INTENTS = {action: intent for intent, action in INTENT_ACTIONS.items()}


def absorb_words(ctx: TurnContext, data: CardData) -> CardData:
    """The deterministic part of ``absorb`` (no model call): a request, a reason, or a card named in an answer."""
    action = extraction.card_action(ctx.text)
    reason = extraction.block_reason(ctx.text)
    hint_type = extraction.card_type(ctx.text)
    hint_last4 = extraction.card_last4(ctx.text)
    explicit_card = hint_type is not None or hint_last4 is not None
    return data.evolve(
        action=action or data.action,
        block_reason=reason or data.block_reason,
        hint_type=hint_type if explicit_card else data.hint_type,
        hint_last4=hint_last4 if explicit_card else data.hint_last4,
    )


async def understand(ctx: TurnContext) -> Step:
    data = await absorb(ctx, CardData())
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
        narrowed = [card for card in narrowed if card.masked_number.last4 == data.hint_last4]
    if data.hint_type is not None:
        narrowed = [card for card in narrowed if card.card_type is data.hint_type]
    if data.action is CardAction.BLOCK and len(narrowed) > 1:
        narrowed = [card for card in narrowed if card.status is ProductStatus.ACTIVE] or narrowed
    return narrowed


async def _chosen(ctx: TurnContext, data: CardData, card: CardStatusView) -> Step:
    product = ProductId(card.product_ref.key)
    data = data.evolve(
        product_id=product, last4=card.masked_number.last4, card_type=card.card_type, status=card.status, option_ids=()
    )
    ctx.engine = ctx.engine.evolve(carried_card=card.product_ref).with_fact(
        f"card ending {card.masked_number.last4} ({card.card_type.value}) is {card.status.value}", card.product_ref
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
    # An ending the customer stated that none of their cards has is asked about with every card listed; it is never
    # replaced by a guess from other hints (phase 14b: the model's card type hint picked a card for "terminada en
    # 9999" when the customer has no such card).
    unknown_ending = data.hint_last4 is not None and all(c.masked_number.last4 != data.hint_last4 for c in cards)
    plausible = [] if unknown_ending else _plausible(data, cards)
    if len(plausible) == 1:
        return await _chosen(ctx, data, plausible[0])
    # Missing or contradictory hints do not identify a card. Offer all owned cards for an explicit choice.
    plausible = plausible or cards
    stop = spend_clarification(ctx, open_questions=WHICH_CARD)
    if stop is not None:
        return stop
    options = tuple(ProductId(card.product_ref.key) for card in plausible)
    save(ctx, data.evolve(option_ids=options, hint_type=None, hint_last4=None))
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
        # "ok bloquéala porfa, creo que la perdí" while choosing: the request and the reason are kept, and a card
        # they identify among the options is chosen (QA 2026-10-05, CRD-02); otherwise the options are asked again.
        updated = absorb_words(ctx, data)
        if updated != data:
            save(ctx, updated)
            if updated.action is not None and updated.action is not data.action:
                ctx.engine = ctx.engine.evolve(intent=ACTION_INTENTS.get(updated.action, Intent.CARD_STATUS))
            narrowed = _plausible(updated, options)
            if len(narrowed) == 1:
                return await _chosen(ctx, updated, narrowed[0])
        stop = spend_clarification(ctx, open_questions=WHICH_CARD)
        return stop or _options_reply(ctx, options, unanswered=True)
    return await _chosen(ctx, data, options[index])


def card_ref(data: CardData) -> SourceRef | None:
    return SourceRef.of(SourceTable.PRODUCTS, data.product_id) if data.product_id is not None else None
