"""Structured outputs of the evaluation prompts."""

from typing import Annotated, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Score = Annotated[int, Field(ge=1, le=5)]


class EvalOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NaiveAgentStep(EvalOutput):
    """One step of baseline B1: call one tool, or reply to the customer and say how the turn ended."""

    action: Literal["call_tool", "reply"]
    tool: Annotated[str, StringConstraints(max_length=64)] | None
    arguments: dict[Annotated[str, StringConstraints(max_length=64)], Annotated[str, StringConstraints(max_length=500)]]
    reply: Annotated[str, StringConstraints(max_length=2000)] | None
    outcome: Literal["resolved", "clarified", "abstained", "escalated", "refused"] | None


class SimulatedCustomerTurn(EvalOutput):
    """The simulated customer's next message, and whether the conversation is over for them."""

    message: Annotated[str, StringConstraints(max_length=600)]
    done: bool


class JudgeRating(EvalOutput):
    """Tone, clarity, language, and politeness of one transcript (never task success or safety)."""

    language_correct: bool
    """Every assistant message is in the customer's language (and dialect where it matters)."""
    tone: Score
    clarity: Score
    politeness: Score
    language_quality: Score


EVAL_OUTPUT_MODELS: Final[dict[str, type[BaseModel]]] = {
    model.__name__: model for model in (NaiveAgentStep, SimulatedCustomerTurn, JudgeRating)
}
