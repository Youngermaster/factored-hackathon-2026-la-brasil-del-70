"""Deterministic response templates in Spanish, Portuguese, and English (console preview), keyed by template id.

Placeholders are filled by the renderer from typed parameters; no template contains a figure of its own, so every
figure in a reply comes from a verified record or a bound clause parameter.
"""

from bank_agent.application.engine.templates.card import CARD
from bank_agent.application.engine.templates.common import COMMON
from bank_agent.application.engine.templates.dispute import DISPUTE
from bank_agent.domain.locale import Language

TEMPLATES: dict[str, dict[Language, str]] = {**COMMON, **DISPUTE, **CARD}


def register(extra: dict[str, dict[Language, str]]) -> None:
    """Add a workflow's templates (09b workflows and the baseline register theirs this way)."""
    clashes = sorted(set(extra) & set(TEMPLATES))
    if clashes:
        raise ValueError(f"template ids already registered: {clashes}")
    TEMPLATES.update(extra)
