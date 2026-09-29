"""Wiring for a run: the prompt registry (the application's prompts plus the evaluation prompts) and the parts
P and B0 share, built with the composition root's builders from settings."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files

from bank_agent.adapters.prompts.file_registry import FilePromptRegistry
from bank_agent.bootstrap.models import build_model_registry, build_resolver, build_router, default_embedder
from bank_agent.bootstrap.policy import build_policy
from bank_agent.bootstrap.retrieval import build_grounding
from bank_agent.bootstrap.settings import LLMSettings, PolicySettings, RetrievalSettings, WorkflowSettings
from bank_agent.testing.clock import FixedClock
from bank_agent.testing.ids import SequentialIdGenerator
from bank_evals.prompts.outputs import EVAL_OUTPUT_MODELS
from bank_evals.runner.llm import RunLlm
from bank_evals.systems.engine_system import EngineParts
from bank_evals.world.model import NOW


@cache
def evaluation_prompts() -> FilePromptRegistry:
    return FilePromptRegistry.from_directory(files("bank_evals.prompts"), output_models=EVAL_OUTPUT_MODELS)


@cache
def prompt_registry() -> FilePromptRegistry:
    """The application's prompts and the evaluation prompts (B1, the simulated user, the judge) in one registry."""
    return FilePromptRegistry([*FilePromptRegistry.from_package().templates, *evaluation_prompts().templates])


@dataclass(frozen=True)
class HarnessSettings:
    """The settings a run reads (from the environment by default, like the API): workflow, policy, retrieval,
    and the language model."""

    workflow: WorkflowSettings = field(default_factory=WorkflowSettings)
    policy: PolicySettings = field(default_factory=PolicySettings)
    retrieval: RetrievalSettings = field(default_factory=RetrievalSettings)
    llm: LLMSettings = field(default_factory=LLMSettings)


def build_engine_parts(settings: HarnessSettings, llm: RunLlm) -> EngineParts:
    """Everything P and B0 share across a run's cases, from the same builders the container uses."""
    policy = build_policy(settings.policy, clock=FixedClock(NOW), ids=SequentialIdGenerator())
    grounding = build_grounding(settings.retrieval, policy.repository)
    models = build_model_registry(settings.workflow.model_registry_dir)
    embedder = default_embedder(settings.retrieval)
    return EngineParts(
        settings=settings.workflow,
        policy=policy,
        grounding=grounding,
        llm=llm.client,
        models=models,
        router=build_router(settings.workflow, models, embedder),
        resolver=build_resolver(settings.workflow, models),
        embedder=embedder,
        model_label=llm.model_label,
    )
