"""Baseline B1: a naive language-model agent (evaluation only; never wired into the API).

Each customer turn runs a loop of at most ``MAX_STEPS`` model steps (``naive_agent_step@1``): the model calls one
of its tools with the arguments it chooses, sees the result, and eventually replies and names the turn's outcome.
There is no kernel, no allowlist, no confirmation or step-up gate, no risk estimator or eligibility service, no
grounding verifier, and no read-back. A model error or an invalid step ends the turn with a fixed apology, which
the graders score like any other reply.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Final

from bank_agent.domain.errors import LlmError
from bank_agent.domain.intelligence import LlmCallContext, PromptRef
from bank_agent.domain.locale import Language
from bank_agent.ports.llm import LLMClient
from bank_evals.prompts.outputs import NaiveAgentStep
from bank_evals.scenarios.model import Scenario
from bank_evals.systems.base import EndState, LlmCallView, ToolCallView, TurnView
from bank_evals.systems.naive_agent.database import NaiveDatabase
from bank_evals.systems.naive_agent.tools import WRITES, NaiveTools, render_result
from bank_evals.systems.schedule import FailureSchedule
from bank_evals.world.fixtures import apply_fixtures
from bank_evals.world.model import World

STEP_PROMPT: Final = PromptRef(prompt_id="naive_agent_step", version=1)
MAX_STEPS: Final = 5
MAX_OUTPUT_TOKENS: Final = 600
APOLOGY: Final = {
    Language.ES: "Lo siento, tuve un problema para procesar tu solicitud. ¿Puedes intentarlo de nuevo?",
    Language.PT: "Desculpe, tive um problema para processar o seu pedido. Pode tentar de novo?",
}
WRITE_ACTIONS: Final = {
    "block_card": "block_card",
    "create_dispute": "create_dispute_case",
    "submit_credit_application": "submit_credit_application",
}


@dataclass
class NaiveCase:
    llm: LLMClient
    db: NaiveDatabase
    tools: NaiveTools
    scenario: Scenario
    customer_id: str
    first_name: str
    tag: str
    history: list[tuple[str, str]] = field(default_factory=list)
    turns: int = 0
    expired: bool = False

    async def send(self, text: str) -> TurnView:
        self.turns += 1
        started = time.perf_counter()
        tool_calls: list[ToolCallView] = []
        llm_calls: list[LlmCallView] = []
        results: list[str] = []
        step: NaiveAgentStep | None = None
        for _ in range(MAX_STEPS):
            step = await self._step(text, results, llm_calls)
            if step is None or step.action == "reply":
                break
            tool = step.tool or ""
            status, result = self.tools.call(tool, dict(step.arguments))
            tool_calls.append(
                ToolCallView(
                    tool=tool,
                    status=status,
                    arguments=dict(step.arguments),
                    customer_id=step.arguments.get("customer_id"),
                    verified=None,
                )
            )
            results.append(render_result(tool, status, result))
        reply = step.reply if step is not None and step.action == "reply" and step.reply else None
        outcome = step.outcome if reply is not None and step is not None and step.outcome else "in_progress"
        text_out = reply or APOLOGY[self.scenario.language]
        self.history.append((text, text_out))
        transferred = any(call.tool == "transfer_to_human" and call.status == "ok" for call in tool_calls)
        writes = [WRITE_ACTIONS[call.tool] for call in tool_calls if call.tool in WRITES and call.status == "ok"]
        return TurnView(
            index=self.turns,
            customer_text=text,
            assistant_text=text_out,
            outcome="escalated" if transferred else outcome,
            state="ESCALATED" if transferred else None,
            workflow=None,
            latency_ms=int((time.perf_counter() - started) * 1000),
            tool_calls=tool_calls,
            llm_calls=llm_calls,
            claimed_actions=writes,
        )

    async def _step(self, text: str, results: list[str], calls: list[LlmCallView]) -> NaiveAgentStep | None:
        conversation = "\n".join(f"Customer: {c}\nAssistant: {a}" for c, a in self.history) + f"\nCustomer: {text}"
        country = self.db.customer_country(self.customer_id) or ""
        started = time.perf_counter()
        try:
            generation = await self.llm.generate_structured(
                STEP_PROMPT,
                {
                    "customer_id": self.customer_id,
                    "country": country,
                    "dialect_hint": self.scenario.dialect.value,
                    "conversation": conversation.strip(),
                    "tool_results": "\n".join(results) or "(none)",
                },
                NaiveAgentStep,
                language=self.scenario.language,
                max_output_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.0,
                call_context=LlmCallContext(
                    conversation_id=f"conv-b1-{self.tag}",  # type: ignore[arg-type]
                    turn_id=f"turn-b1-{self.tag}-{self.turns}",  # type: ignore[arg-type]
                    sensitive_terms=(self.first_name,) if len(self.first_name) >= 2 else (),
                ),
            )
        except LlmError as error:
            calls.append(
                LlmCallView(
                    prompt=str(STEP_PROMPT),
                    model="unavailable",
                    status=error.code,
                    latency_ms=int((time.perf_counter() - started) * 1000),
                )
            )
            return None
        calls.append(
            LlmCallView(
                prompt=str(STEP_PROMPT),
                model=generation.model_id,
                status="ok",
                input_tokens=generation.usage.input_tokens,
                output_tokens=generation.usage.output_tokens,
                cost_usd=generation.cost_usd or Decimal(0),
                latency_ms=generation.latency_ms,
            )
        )
        return generation.value

    async def reauthenticate(self) -> None:
        self.expired = False

    async def step_up(self) -> None:
        """B1 has no step-up; the driver never asks it for one."""

    def expire_session(self) -> None:
        self.expired = True

    def advance_clock(self, seconds: int) -> None:
        """B1 has no clock-dependent session."""

    async def finish(self) -> EndState:
        world = self.db.world
        cases = [
            {
                "case_id": c.case_id,
                "transaction_id": c.transaction_id,
                "customer_id": c.customer_id,
                "reason": c.reason.value,
                "status": c.status.value,
            }
            for c in world.cases
        ] + self.db.new_cases
        apps = [
            {
                "application_id": a.application_id,
                "customer_id": a.customer_id,
                "product_code": a.product_code,
                "status": a.status.value,
            }
            for a in world.credit_applications
        ] + self.db.new_applications
        handoffs = [{"document": vars(h), "schema_valid": False} for h in self.db.handoffs]
        return EndState(
            product_statuses={p.product_id: p.status.value for p in world.products},
            cases=cases,
            applications=apps,
            handoffs=handoffs,
            writes=len(self.db.new_cases) + len(self.db.new_applications) + len(self.db.blocked),
        )


class NaiveAgentSystem:
    name = "b1"

    def __init__(self, llm: LLMClient, model_label: str) -> None:
        self._llm, self._label = llm, model_label

    @property
    def model_label(self) -> str:
        return self._label

    async def start(self, scenario: Scenario, world: World, *, run_index: int) -> NaiveCase:
        case_world = apply_fixtures(scenario, world.copy())
        customer = case_world.persona(scenario.persona_ref).customer
        db = NaiveDatabase(case_world)
        tag = hashlib.sha256(f"{scenario.id}:b1:{run_index}".encode()).hexdigest()[:10]
        tools = NaiveTools(db, FailureSchedule(scenario.tool_failure_plan))
        return NaiveCase(self._llm, db, tools, scenario, customer.customer_id, customer.first_name, tag)
