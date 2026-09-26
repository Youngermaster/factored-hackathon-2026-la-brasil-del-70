"""Prompt registry port."""

from collections.abc import Mapping
from typing import Protocol

from bank_agent.domain.intelligence import PromptRef, PromptTemplate, PromptValue, RenderedPrompt


class PromptRegistry(Protocol):
    """Versioned prompt files, referenced by id and version (never "latest").

    Preconditions: loaded at startup; lookups are in memory.
    Postconditions: ``render`` wraps every variable the prompt declares as untrusted in data delimiters.
    Errors: ``PromptNotFoundError`` for an unknown reference; ``PromptVariablesError`` for unknown, missing,
    or mistyped variables.
    Isolation: rendered prompts contain only the variables passed in.
    """

    def get(self, prompt: PromptRef) -> PromptTemplate:
        """Return the prompt template."""
        ...

    def render(self, prompt: PromptRef, variables: Mapping[str, PromptValue]) -> RenderedPrompt:
        """Validate the variables and render the prompt's messages."""
        ...
