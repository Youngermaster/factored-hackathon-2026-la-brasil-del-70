"""The context a conversation rule receives, and the registry of conversation rules."""

from collections.abc import Mapping
from dataclasses import dataclass

from bank_agent.domain.access import AuthLevel
from bank_agent.domain.decision import ParamValue
from bank_agent.domain.policy import ActionRequirement
from bank_agent.policy.facts import EvaluationRequest, PolicyFacts
from bank_agent.policy.rules.registry import RuleRegistry


@dataclass(frozen=True)
class RuleContext:
    """One rule's view of an evaluation: the request, its merged clause parameters, and the matrix row."""

    request: EvaluationRequest
    params: Mapping[str, ParamValue]
    state_auth: AuthLevel
    """The authentication level the state's binding requires."""
    requirement: ActionRequirement | None
    """The matrix row of the requested action, or ``None`` when no action is requested."""

    @property
    def facts(self) -> PolicyFacts:
        return self.request.facts


CONVERSATION_RULES: RuleRegistry[RuleContext] = RuleRegistry(
    prefixes=("AUTH.", "PRV.", "SCOPE.", "ACC.", "CRD.", "DSP.", "CRE.", "ESC.")
)
