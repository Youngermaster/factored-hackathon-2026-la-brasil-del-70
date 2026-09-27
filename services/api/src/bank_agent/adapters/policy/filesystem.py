"""The policy repository and the credit catalog, loaded once from the pack directory.

``FilesystemPolicyRepository`` implements ``PolicyRepository`` and ``FilesystemCreditCatalog`` implements
``CreditProductCatalog``; both are thin: reading files is all they add to the pure loader in
``bank_agent.policy.loader``. A malformed pack is a startup error (``PolicyPackInvalidError``).
"""

from collections.abc import Mapping, Sequence
from pathlib import Path

from bank_agent.adapters.persistence.memory.credit_catalog import InMemoryCreditProductCatalog
from bank_agent.adapters.policy.files import read_pack_files
from bank_agent.domain.actions import ActionKind
from bank_agent.domain.credit import CreditProduct
from bank_agent.domain.errors import PolicyPackInvalidError
from bank_agent.domain.identifiers import CreditProductCode
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.policy import ActionRequirement, PolicyClause
from bank_agent.domain.workflow import WorkflowId
from bank_agent.policy.loader import load_pack
from bank_agent.policy.loader.catalog import CatalogEntry, ProductDisplay, check_catalog_against_pack, parse_catalog
from bank_agent.policy.pack import PolicyPack


class FilesystemPolicyRepository:
    """Implements ``PolicyRepository`` over a pack read from ``root``."""

    def __init__(self, pack: PolicyPack) -> None:
        self.pack = pack

    @classmethod
    def from_directory(cls, root: Path) -> "FilesystemPolicyRepository":
        return cls(load_pack(read_pack_files(root)))

    def pack_version(self) -> str:
        return self.pack.pack_version()

    def get_clause(self, clause_id: str, language: Language, version: int | None = None) -> PolicyClause:
        return self.pack.get_clause(clause_id, language, version)

    def get_bound(
        self, workflow: WorkflowId, state: str, jurisdiction: Country, language: Language
    ) -> Sequence[PolicyClause]:
        return self.pack.get_bound(workflow, state, jurisdiction, language)

    def list_clauses(
        self, language: Language | None = None, jurisdiction: Country | None = None
    ) -> Sequence[PolicyClause]:
        return self.pack.list_clauses(language, jurisdiction)

    def action_requirements(self, action: ActionKind) -> ActionRequirement:
        return self.pack.action_requirements(action)


class FilesystemCreditCatalog:
    """Implements ``CreditProductCatalog`` over ``policies/credit/``, checked against the pack, with display text."""

    def __init__(self, entries: tuple[CatalogEntry, ...]) -> None:
        if not entries:
            raise PolicyPackInvalidError("the credit catalog is empty")
        version = entries[0].product.catalog_version
        self._catalog = InMemoryCreditProductCatalog((entry.product for entry in entries), version)
        self._display: Mapping[str, Mapping[Language, ProductDisplay]] = {
            entry.product.product_code: entry.display for entry in entries
        }

    @classmethod
    def from_directory(cls, root: Path, pack: PolicyPack) -> "FilesystemCreditCatalog":
        entries = parse_catalog(read_pack_files(root))
        check_catalog_against_pack(entries, pack)
        return cls(entries)

    def catalog_version(self) -> str:
        return self._catalog.catalog_version()

    def list(self, jurisdiction: Country) -> Sequence[CreditProduct]:
        return self._catalog.list(jurisdiction)

    def get(self, code: CreditProductCode) -> CreditProduct | None:
        return self._catalog.get(code)

    def display(self, code: CreditProductCode, language: Language) -> ProductDisplay | None:
        """The product's name and summary in ``language``, or ``None`` for an unknown code."""
        texts = self._display.get(code)
        return texts[language] if texts is not None else None
