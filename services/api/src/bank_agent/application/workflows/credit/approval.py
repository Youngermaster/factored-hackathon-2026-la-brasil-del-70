"""Questions about approval ("¿me lo aprobaron?", "tô aprovado ou não?", "¿me garantizan que lo aprueban?"),
including injected text that tells the assistant to state an approval. No credit decision is made in a
conversation, so the answer is always the ``credit.no_decision`` text with ``CRE-ALL-3`` and ``CRE-ALL-1``; at a
pending question the question is asked again after the answer (QA 2026-10-05, CRE-09).

A question about the requirements ("¿qué necesito para que me aprueben?", "O que preciso para ter um empréstimo
aprovado?") is not an approval question: only a copula, a past "aprobaron", a guarantee, or a yes-or-no demand is.
"""

import re
from dataclasses import replace

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.definition import UnsupportedRequest
from bank_agent.application.engine.shared import clause_ref
from bank_agent.application.understanding.text import fold

_APPROVAL = re.compile(
    r"\b(?:esta|estoy|estas|estou|to|tou|fui|foi|fue|quede|queda|ya|ja|sera|vai ser|va a ser) "
    r"(?:pre[ -]?)?(?:aprobad|aprovad)[oa]s?\b|"
    r"\bme (?:lo |la )?(?:aprobaron|aprobo|aprovaram|aprovou)\b|"
    r"\bgarant\w*.{0,40}\b(?:aprob|aprov|aprueb)|"
    r"\b(?:puedes|podes|pode|voce pode) (?:aprobar|aprovar)\b|"
    r"\b(?:aprobad|aprovad)[oa]s? (?:o|ou) (?:no|nao)\b"
)
CLAUSES = ("CRE-ALL-3", "CRE-ALL-1")
APPROVAL_QUESTION = UnsupportedRequest(code="approval_question", clauses=CLAUSES, template="credit.no_decision")


def asks_approval(text: str) -> bool:
    return bool(_APPROVAL.search(fold(text)))


def answer_then_ask_again(ctx: TurnContext, step: Step) -> Step:
    """``step`` (the pending question asked again) preceded by the no-decision answer, with its clauses cited; the
    customer's question was answered, so the step is not an unanswered prompt."""
    if step.reply is None:
        return step
    refs = tuple(clause_ref(ctx, clause_id) for clause_id in CLAUSES)
    reply = replace(step.reply, prefix="credit.no_decision", explain=(*step.reply.explain, *refs))
    return replace(step, reply=reply, unanswered=False)
