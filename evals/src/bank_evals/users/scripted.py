"""The scripted user driver: plays a scenario's turns, and handles session events the way the web client does.

Customer actions become the words the chat's quick replies send (phase 13): a confirmation, a cancellation, an
option number. When a reply asks for step-up, the customer completes it and says so; when the session expired,
the customer signs in again, says so, and repeats the pending message. Every event is recorded on the turns.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from bank_agent.domain.locale import Language
from bank_evals.scenarios.model import Scenario, ScriptedTurn, SessionExpiresBeforeTurn, TurnAction
from bank_evals.systems.base import CaseSession, TurnView

CONFIRM: Final = {Language.ES: "Sí, confirmo", Language.PT: "Sim, confirmo"}
DECLINE: Final = {Language.ES: "No, cancelar", Language.PT: "Não, cancelar"}
OPTION: Final = {Language.ES: "Opción {n}", Language.PT: "Opção {n}"}
STEPPED_UP: Final = {
    Language.ES: "Listo, ya confirmé mi identidad",
    Language.PT: "Pronto, já confirmei minha identidade",
}
SIGNED_IN: Final = {Language.ES: "Listo, ya volví a iniciar sesión", Language.PT: "Pronto, já entrei de novo"}
PAUSE_STATES: Final = frozenset({"AUTH_REQUIRED"})
MAX_STEP_UPS: Final = 2
MAX_SIGN_INS: Final = 2


def render(turn: ScriptedTurn, language: Language) -> str:
    if turn.text is not None:
        return turn.text
    if turn.action is TurnAction.CONFIRM:
        return CONFIRM[language]
    if turn.action is TurnAction.DECLINE:
        return DECLINE[language]
    if turn.action is TurnAction.SELECT_OPTION:
        return OPTION[language].format(n=turn.option_index)
    return STEPPED_UP[language]


class TurnLog:
    """The turns of one case, with the session state the driver knew when it sent each one."""

    def __init__(self) -> None:
        self.turns: list[TurnView] = []

    def add(self, view: TurnView, *, driver: str, session_valid: bool) -> TurnView:
        view = view.model_copy(update={"driver": driver, "index": len(self.turns) + 1})
        view.notices = [*view.notices, *([] if session_valid else ["driver_session_expired"])]
        self.turns.append(view)
        return view


async def send_with_session_events(
    case: CaseSession, log: TurnLog, text: str, language: Language, *, driver: str, expired: bool
) -> TurnView:
    """Send ``text``; then complete step-up or sign in again as the replies ask, and repeat the pending text."""
    view = log.add(await case.send(text), driver=driver, session_valid=not expired)
    sign_ins = 0
    while view.state in PAUSE_STATES and sign_ins < MAX_SIGN_INS:
        sign_ins += 1
        await case.reauthenticate()
        log.add(await case.send(SIGNED_IN[language]), driver=driver, session_valid=True)
        view = log.add(await case.send(text), driver=driver, session_valid=True)
    step_ups = 0
    while view.step_up_required and step_ups < MAX_STEP_UPS:
        step_ups += 1
        await case.step_up()
        view = log.add(await case.send(STEPPED_UP[language]), driver=driver, session_valid=True)
    return view


OFFER_STATES: Final = frozenset({"OFFER_PROTECTIVE_BLOCK"})
ACCEPT_OFFER: Final = {Language.ES: "Sí, bloquéala también", Language.PT: "Sim, bloqueie também"}
DECLINE_OFFER: Final = {Language.ES: "No, gracias", Language.PT: "Não, obrigado"}
LANGUAGE_WORD: Final = {Language.ES: "español", Language.PT: "português"}
MAX_TURNS: Final = 16


async def play_scripted(
    case: CaseSession, scenario: Scenario, turns: Sequence[ScriptedTurn], *, driver: str = "scripted"
) -> list[TurnView]:
    """Play ``turns`` (the scenario's, or its scripted fallback) and return every turn of the conversation.

    The script holds what the customer says and decides; the driver answers what a script cannot know in advance
    and a real customer would: the language question, and the protective block offer (declined unless the scenario
    is tagged ``accepts_protective_block``). A transfer to a person ends the conversation.
    """
    expiring = {f.turn_index for f in scenario.fixtures if isinstance(f, SessionExpiresBeforeTurn)}
    language, log = scenario.language, TurnLog()
    accepts = "accepts_protective_block" in scenario.tags
    answered_language = answered_offer = False
    number = 0
    view: TurnView | None = None
    while len(log.turns) < MAX_TURNS:
        if view is not None and (view.state == "ESCALATED" or view.outcome == "escalated"):
            break
        if view is not None and "language_question" in view.notices and not answered_language:
            answered_language = True
            view = await send_with_session_events(
                case, log, LANGUAGE_WORD[language], language, driver=driver, expired=False
            )
            continue
        if view is not None and view.state in OFFER_STATES and not answered_offer:
            answered_offer = True
            text = (ACCEPT_OFFER if accepts else DECLINE_OFFER)[language]
            view = await send_with_session_events(case, log, text, language, driver=driver, expired=False)
            continue
        if number >= len(turns):
            break
        turn = turns[number]
        number += 1
        if turn.advance_clock_seconds:
            case.advance_clock(turn.advance_clock_seconds)
        expired = number in expiring
        if expired:
            case.expire_session()
        view = await send_with_session_events(
            case, log, render(turn, language), language, driver=driver, expired=expired
        )
    return log.turns
