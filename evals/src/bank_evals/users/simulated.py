"""The simulated user driver: a language model plays the customer (``simulate_customer@1``).

It sees only the scenario's goal, instructions, known and hidden facts, and what the assistant wrote, never
system internals. It stops when it says it is done, when the case is transferred, or after ``MAX_MESSAGES``.
When the model cannot answer the first message (``--llm off``, a missing cassette, an error), the scenario's
scripted fallback turns are played instead and the turns say so (``driver: scripted_fallback``).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from bank_agent.domain.errors import LlmError
from bank_agent.domain.intelligence import LlmCallContext, PromptRef
from bank_agent.ports.llm import LLMClient
from bank_evals.prompts.outputs import SimulatedCustomerTurn
from bank_evals.scenarios.model import Scenario
from bank_evals.systems.base import CaseSession, LlmCallView, TurnView
from bank_evals.users.scripted import TurnLog, play_scripted, send_with_session_events

SIMULATOR_PROMPT: Final = PromptRef(prompt_id="simulate_customer", version=1)
MAX_MESSAGES: Final = 6
TEMPERATURE: Final = 0.7
MAX_OUTPUT_TOKENS: Final = 200


def _facts(facts: dict[str, str]) -> str:
    return "; ".join(f"{key}: {value}" for key, value in facts.items()) or "(none)"


class SimulatedUser:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm
        self.calls: list[LlmCallView] = []

    async def _next(self, scenario: Scenario, log: TurnLog, run_index: int) -> SimulatedCustomerTurn | None:
        conversation = "\n".join(f"Customer: {t.customer_text}\nAssistant: {t.assistant_text}" for t in log.turns)
        try:
            generation = await self._llm.generate_structured(
                SIMULATOR_PROMPT,
                {
                    "dialect_hint": scenario.dialect.value,
                    "goal": scenario.goal,
                    "instructions": scenario.simulator_instructions or scenario.goal,
                    "known_facts": _facts(scenario.known_facts),
                    "hidden_facts": _facts(scenario.hidden_facts),
                    "conversation": conversation or "(empty)",
                    "conversation_seed": f"{scenario.id}#{run_index}",
                },
                SimulatedCustomerTurn,
                language=scenario.language,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                temperature=TEMPERATURE,
                call_context=LlmCallContext(),
            )
        except LlmError as error:
            self.calls.append(
                LlmCallView(prompt=str(SIMULATOR_PROMPT), model="unavailable", status=error.code, role="user")
            )
            return None
        self.calls.append(
            LlmCallView(
                prompt=str(SIMULATOR_PROMPT),
                model=generation.model_id,
                status="ok",
                role="user",
                input_tokens=generation.usage.input_tokens,
                output_tokens=generation.usage.output_tokens,
                cost_usd=generation.cost_usd or Decimal(0),
                latency_ms=generation.latency_ms,
            )
        )
        return generation.value

    async def play(self, case: CaseSession, scenario: Scenario, run_index: int) -> list[TurnView]:
        log = TurnLog()
        first = await self._next(scenario, log, run_index)
        if first is None or not first.message.strip():
            return await play_scripted(case, scenario, scenario.scripted_fallback, driver="scripted_fallback")
        message: SimulatedCustomerTurn | None = first
        while message is not None and message.message.strip() and len(log.turns) < MAX_MESSAGES:
            view = await send_with_session_events(
                case, log, message.message.strip()[:2000], scenario.language, driver="simulated", expired=False
            )
            if message.done or view.state == "ESCALATED" or view.outcome == "escalated":
                break
            message = await self._next(scenario, log, run_index)
        return log.turns
