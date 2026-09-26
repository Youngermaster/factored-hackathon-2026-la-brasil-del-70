"""Policy repository port (phase 06 adds the filesystem adapter, phase 07 the bound lookup)."""

from collections.abc import Sequence
from typing import Protocol

from bank_agent.domain.actions import ActionKind
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.policy import ActionRequirement, PolicyClause
from bank_agent.domain.workflow import WorkflowId


class PolicyRepository(Protocol):
    """The synthetic policy pack: clauses, bindings per workflow state, and the action matrix.

    Preconditions: loaded and validated at startup; ``jurisdiction`` always comes from the verified customer
    profile, never from user text.
    Postconditions: ``pack_version`` is a stable hash of the pack stored in every execution record.
    ``get_bound`` returns the clauses bound to a state of one workflow (state names such as ``START`` repeat
    across workflows), for ``jurisdiction`` plus those marked ``ALL``, in binding order.
    Errors: ``PolicyClauseNotFoundError`` for an unknown clause or version; ``PolicyBindingMissingError`` for
    a state without a binding (a startup error in practice); ``PolicyPackInvalidError`` for a malformed pack.
    Isolation: the pack contains no customer data.
    """

    def pack_version(self) -> str:
        """Return the pack version hash."""
        ...

    def get_clause(self, clause_id: str, language: Language, version: int | None = None) -> PolicyClause:
        """Return a clause in ``language``; the current version when ``version`` is ``None``."""
        ...

    def get_bound(
        self, workflow: WorkflowId, state: str, jurisdiction: Country, language: Language
    ) -> Sequence[PolicyClause]:
        """Return the clauses bound to ``state`` of ``workflow``."""
        ...

    def list_clauses(
        self, language: Language | None = None, jurisdiction: Country | None = None
    ) -> Sequence[PolicyClause]:
        """Return every current clause, optionally filtered."""
        ...

    def action_requirements(self, action: ActionKind) -> ActionRequirement:
        """Return the matrix row for an action."""
        ...
