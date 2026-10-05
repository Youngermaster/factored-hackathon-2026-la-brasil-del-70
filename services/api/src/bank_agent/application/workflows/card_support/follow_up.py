"""Follow-ups to a card status answer: a message that only names another card by type or by its ending ("¿y la de
débito?", "e a de crédito?", "¿y la terminada en 3954?") asks for that card's status instead of getting an
off-topic abstention. The card is chosen from the text by SELECT_CARD, as for any status request."""

from bank_agent.application.engine.context import TurnContext
from bank_agent.application.understanding import extraction
from bank_agent.domain.workflow import Intent


def follow_up(ctx: TurnContext) -> Intent | None:
    """``card_status`` when the message names a card by type or ending, else ``None``."""
    if extraction.card_type(ctx.text) is not None or extraction.card_last4(ctx.text) is not None:
        return Intent.CARD_STATUS
    return None
