"""CARD_STATUS: status and expiry from ``get_product_status``, and recent declined purchases listed without
interpreting ``response_code`` (the data has no code table). The state keeps the chosen card, so a follow-up
("block it") continues here and a request for another workflow is confirmed before switching."""

import re

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.decide import evaluate
from bank_agent.application.engine.reply import Choices, Masked, Param, RecordText, Reply
from bank_agent.application.engine.shared import blocking_step, clause_ref
from bank_agent.application.engine.templates.labels import CARD_STATUSES, CARD_TYPES
from bank_agent.application.understanding import extraction
from bank_agent.application.understanding.text import fold
from bank_agent.application.workflows.card_support.data import INTENT_ACTIONS, load, save
from bank_agent.application.workflows.card_support.select import CONFIRM_BLOCK, absorb
from bank_agent.domain.cards import CardAction, CardStatusView
from bank_agent.domain.locale import Language
from bank_agent.domain.transaction import TransactionStatus
from bank_agent.domain.workflow import Intent, Outcome
from bank_agent.policy.facts import CardFacts
from bank_agent.ports.repositories.transactions import TransactionQuery

CARD_STATUS = "CARD_STATUS"
MAX_DECLINED = 5
_OTHER_CARD = re.compile(r"\b(?:otr[oa]s?|outr[oa]s?|other|another|demas|mais cartoes)\b")


async def card_status(ctx: TurnContext) -> Step:
    data = load(ctx)
    if ctx.reprompt:
        return Step(CARD_STATUS, Reply(template="card.anything_else"), Outcome.IN_PROGRESS)
    if data.answered:
        intent = ctx.prediction.intent if ctx.prediction is not None else None
        data = await absorb(ctx, data)
        if intent is Intent.CARD_BLOCK or data.action is CardAction.BLOCK:
            if extraction.card_type(ctx.text) is not None or extraction.card_last4(ctx.text) is not None:
                save(ctx, data.evolve(action=CardAction.BLOCK, product_id=None, answered=False, confirm_shown=False))
                return Step("SELECT_CARD")
            save(ctx, data.evolve(action=CardAction.BLOCK, confirm_shown=False))
            return Step(CONFIRM_BLOCK)
        named = extraction.card_type(ctx.text) is not None or extraction.card_last4(ctx.text) is not None
        if intent is Intent.CARD_STATUS and not named and not _OTHER_CARD.search(fold(ctx.text)):
            # "¿cuándo vence?" about the card just discussed: answer again for the same card (QA 2026-10-05, CRD-02).
            save(ctx, data.evolve(answered=False))
            return Step(CARD_STATUS)
        if intent in INTENT_ACTIONS or intent is Intent.CARD_STATUS:
            hints = {"hint_type": extraction.card_type(ctx.text), "hint_last4": extraction.card_last4(ctx.text)}
            save(ctx, data.evolve(product_id=None, answered=False, **(hints if named else {})))
            return Step("SELECT_CARD")
        save(ctx, data)
        return Step(CARD_STATUS, Reply(template="card.anything_else"), Outcome.IN_PROGRESS)
    if data.product_id is None:
        return Step("SELECT_CARD")
    view = await ctx.tools.get_product_status(data.product_id)
    if view is None:
        save(ctx, data.evolve(product_id=None))
        return Step("SELECT_CARD")
    facts = CardFacts(owned_by_session_customer=True, is_card=True, status=view.status)
    decision = evaluate(ctx, card=facts)
    stop = blocking_step(ctx, decision, state=CARD_STATUS)
    if stop is not None:
        return stop
    language = Language.ES if ctx.language is Language.EN else ctx.language
    params: dict[str, Param] = {
        "type": CARD_TYPES[view.product_type][language],
        "card": Masked(view.masked_number.last4),
        "status": CARD_STATUSES[view.status][language],
    }
    template = "card.status"
    if view.expires_on is not None:
        params["expires"] = view.expires_on
        template = "card.status_with_expiry"
    query = TransactionQuery(statuses=(TransactionStatus.DECLINED,), product_ids=(data.product_id,), limit=MAX_DECLINED)
    declined = await ctx.tools.list_recent_transactions(query)
    items: tuple[dict[str, Param], ...] = tuple(
        {"date": txn.occurred_at.astimezone(ctx.zone).date(), "merchant": RecordText(txn.merchant_name or "-"),
         "amount": txn.amount}
        for txn in declined
    )  # fmt: skip
    listing: dict[str, Param] = {"items": Choices("card.declined_item", items)}
    suffix: tuple[tuple[str, dict[str, Param]], ...] = (("card.declined", listing),) if items else ()
    card = CardStatusView(
        product_ref=view.product_ref,
        card_type=view.product_type,
        masked_number=view.masked_number,
        status=view.status,
        expires_on=view.expires_on,
    )
    save(ctx, data.evolve(answered=True, status=view.status))
    reply = Reply(
        template=template,
        params=params,
        suffix=suffix,
        explain=(clause_ref(ctx, "CRD-ALL-1"),),
        card_status=(card,),
    )
    return Step(CARD_STATUS, reply, Outcome.RESOLVED)
