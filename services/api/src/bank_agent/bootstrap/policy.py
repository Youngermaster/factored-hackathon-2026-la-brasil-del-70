"""The policy pack, the synthetic credit catalog, the eligibility service, and the tool parameters.

Everything loads once from ``POLICY_DIR`` at startup; a malformed pack or a catalog that disagrees with it is a
startup error. ``data_as_of`` is the reference date phase 09 passes to the evaluator as ``PolicyFacts.data_as_of``.
"""

from dataclasses import dataclass
from datetime import date

from bank_agent.adapters.policy.filesystem import FilesystemCreditCatalog, FilesystemPolicyRepository
from bank_agent.application.tools.context import ToolPolicy
from bank_agent.bootstrap.settings import PolicySettings
from bank_agent.domain.decision import Decision
from bank_agent.policy.eligibility import SyntheticEligibilityService
from bank_agent.policy.evaluator import evaluate
from bank_agent.policy.facts import EvaluationRequest
from bank_agent.policy.pack import PolicyPack
from bank_agent.ports.determinism import Clock, IdGenerator


@dataclass(frozen=True)
class PolicyServices:
    repository: FilesystemPolicyRepository
    catalog: FilesystemCreditCatalog
    eligibility: SyntheticEligibilityService
    tool_policy: ToolPolicy
    data_as_of: date

    @property
    def pack(self) -> PolicyPack:
        return self.repository.pack

    def evaluate(self, request: EvaluationRequest) -> Decision:
        """Evaluate a request against the loaded pack (pure; the request carries every fact)."""
        return evaluate(request, self.pack)


def build_policy(settings: PolicySettings, *, clock: Clock, ids: IdGenerator) -> PolicyServices:
    repository = FilesystemPolicyRepository.from_directory(settings.dir)
    return PolicyServices(
        repository=repository,
        catalog=FilesystemCreditCatalog.from_directory(settings.dir, repository.pack),
        eligibility=SyntheticEligibilityService(repository.pack, clock, ids),
        tool_policy=ToolPolicy.from_policy(repository),
        data_as_of=settings.data_as_of,
    )
