"""The review notice after a refusal names the sign-in, not the chat (QA finding DSP-15): the raised risk tier
belongs to the session, so the next new conversation of the same sign-in also goes to a person."""

from bank_agent.application.engine.templates.common import COMMON
from bank_agent.domain.locale import Language


def test_review_notice_says_the_rest_of_the_session_goes_to_a_person() -> None:
    notice = COMMON["common.refused_review_notice"]
    assert "en esta sesión" in notice[Language.ES]
    assert "nesta sessão" in notice[Language.PT]
    assert "in this session" in notice[Language.EN]
    assert all("conversa" not in text and "conversation" not in text for text in notice.values())
