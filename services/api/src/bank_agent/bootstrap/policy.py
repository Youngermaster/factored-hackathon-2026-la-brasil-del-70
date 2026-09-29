"""The policy pack, the synthetic credit catalog, the eligibility service, and the tool parameters.

Everything loads once from ``POLICY_DIR`` at startup; a malformed pack is a startup error. A credit catalog that
cannot load (missing, malformed, or disagreeing with the pack) disables the ``credit`` workflow when
``DEGRADATION_CREDIT_CATALOG_FALLBACK`` allows it (``credit_catalog_available`` is then false and the catalog is empty);
otherwise it stops startup too. ``data_as_of`` is the reference date phase 09 passes to the evaluator as
``PolicyFacts.data_as_of``.
"""

from dataclasses import dataclass
from datetime import date

import structlog

from bank_agent.adapters.policy.filesystem import FilesystemCreditCatalog, FilesystemPolicyRepository
from bank_agent.adapters.policy.unavailable import UnavailableCreditCatalog
from bank_agent.application.tools.context import ToolPolicy
from bank_agent.bootstrap.settings import PolicySettings
from bank_agent.domain.decision import Decision
from bank_agent.domain.errors import ConfigurationError
from bank_agent.policy.eligibility import SyntheticEligibilityService
from bank_agent.policy.evaluator import evaluate
from bank_agent.policy.facts import EvaluationRequest
from bank_agent.policy.pack import PolicyPack
from bank_agent.ports.determinism import Clock, IdGenerator

_log = structlog.get_logger(__name__)


@dataclass(frozen=True)
class PolicyServices:
    repository: FilesystemPolicyRepository
    catalog: FilesystemCreditCatalog | UnavailableCreditCatalog
    eligibility: SyntheticEligibilityService
    tool_policy: ToolPolicy
    data_as_of: date
    credit_catalog_available: bool = True

    @property
    def pack(self) -> PolicyPack:
        return self.repository.pack

    def evaluate(self, request: EvaluationRequest) -> Decision:
        """Evaluate a request against the loaded pack (pure; the request carries every fact)."""
        return evaluate(request, self.pack)


def build_policy(
    settings: PolicySettings, *, clock: Clock, ids: IdGenerator, catalog_fallback: bool = False
) -> PolicyServices:
    repository = FilesystemPolicyRepository.from_directory(settings.dir)
    catalog: FilesystemCreditCatalog | UnavailableCreditCatalog
    try:
        catalog = FilesystemCreditCatalog.from_directory(settings.dir, repository.pack)
        available = True
    except (ConfigurationError, OSError, ValueError) as error:
        if not catalog_fallback:
            raise
        _log.warning("credit_catalog_unavailable", error_type=type(error).__name__, served="credit workflow disabled")
        catalog, available = UnavailableCreditCatalog(), False
    return PolicyServices(
        repository=repository,
        catalog=catalog,
        eligibility=SyntheticEligibilityService(repository.pack, clock, ids),
        tool_policy=ToolPolicy.from_policy(repository),
        data_as_of=settings.data_as_of,
        credit_catalog_available=available,
    )
