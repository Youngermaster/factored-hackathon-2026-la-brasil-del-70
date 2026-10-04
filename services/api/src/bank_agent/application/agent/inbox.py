"""The agent inbox: handoffs with their lifecycle, and the reviewable credit application intakes.

Every call runs under the agent's session, so the repositories and row-level security scope it. Claims,
resolutions, and credit review moves (into human review, then closed; never an approval) are audited in the same unit of
work as the change. Agents see handoffs, which carry the
verified facts and never a transcript; they never read a customer's conversation.
"""

from collections.abc import Sequence

from bank_agent.domain.access import Role
from bank_agent.domain.audit import AuditEvent, AuditOutcome
from bank_agent.domain.credit import ApplicationStatus, CreditApplicationIntake
from bank_agent.domain.errors import AccessContextError, CreditApplicationNotFoundError, HandoffNotFoundError
from bank_agent.domain.handoff import HandoffOutcomeCode, HandoffRecord
from bank_agent.domain.identifiers import ApplicationId, AuditEventId, HandoffId, IdKind, SourceRef, SourceTable
from bank_agent.domain.session import Session
from bank_agent.ports.determinism import Clock, IdGenerator
from bank_agent.ports.repositories.handoffs import HandoffQuery
from bank_agent.ports.unit_of_work import UnitOfWork, UnitOfWorkFactory


def _agent_only(session: Session) -> None:
    if session.role is not Role.AGENT:
        raise AccessContextError("the inbox is for agent sessions")


class AgentInbox:
    def __init__(self, uow_factory: UnitOfWorkFactory, clock: Clock, ids: IdGenerator) -> None:
        self._uow_factory, self._clock, self._ids = uow_factory, clock, ids

    async def _audit(
        self, uow: UnitOfWork, session: Session, action: str, target: str, table: SourceTable = SourceTable.HANDOFFS
    ) -> None:
        await uow.audit.append(
            AuditEvent(
                event_id=AuditEventId(self._ids.new(IdKind.AUDIT_EVENT)),
                occurred_at=self._clock.now(),
                actor_role=session.role,
                actor_ref=session.staff_id,
                action=action,
                target=SourceRef.of(table, target),
                outcome=AuditOutcome.SUCCESS,
                arguments={"session_id": session.session_id},
            )
        )

    async def list(self, session: Session, query: HandoffQuery) -> Sequence[HandoffRecord]:
        _agent_only(session)
        async with self._uow_factory(session.access_context()) as uow:
            return await uow.handoffs.list(query)

    async def get(self, session: Session, handoff_id: HandoffId) -> HandoffRecord:
        _agent_only(session)
        async with self._uow_factory(session.access_context()) as uow:
            record = await uow.handoffs.get(handoff_id)
        if record is None:
            raise HandoffNotFoundError()
        return record

    async def claim(self, session: Session, handoff_id: HandoffId) -> HandoffRecord:
        _agent_only(session)
        async with self._uow_factory(session.access_context()) as uow:
            record = await uow.handoffs.claim(handoff_id, at=self._clock.now())
            await self._audit(uow, session, "handoff_claimed", handoff_id)
            await uow.commit()
        return record

    async def resolve(
        self, session: Session, handoff_id: HandoffId, outcome: HandoffOutcomeCode, note: str
    ) -> HandoffRecord:
        _agent_only(session)
        async with self._uow_factory(session.access_context()) as uow:
            record = await uow.handoffs.resolve(handoff_id, outcome=outcome, note=note, at=self._clock.now())
            await self._audit(uow, session, "handoff_resolved", handoff_id)
            await uow.commit()
        return record

    async def credit_applications(
        self, session: Session, statuses: frozenset[ApplicationStatus] | None, limit: int
    ) -> Sequence[CreditApplicationIntake]:
        _agent_only(session)
        async with self._uow_factory(session.access_context()) as uow:
            return await uow.credit_applications.list_for_review(statuses, limit)

    async def credit_application(self, session: Session, application_id: ApplicationId) -> CreditApplicationIntake:
        _agent_only(session)
        async with self._uow_factory(session.access_context()) as uow:
            application = await uow.credit_applications.get(application_id)
        if application is None:
            raise CreditApplicationNotFoundError()
        return application

    async def review_credit_application(
        self, session: Session, application_id: ApplicationId, expected_version: int
    ) -> CreditApplicationIntake:
        """Take a submitted intake into human review (``under_human_review``)."""
        return await self._move(
            session, application_id, expected_version, ApplicationStatus.UNDER_HUMAN_REVIEW, "credit_review_started"
        )

    async def close_credit_application(
        self, session: Session, application_id: ApplicationId, expected_version: int
    ) -> CreditApplicationIntake:
        """Close an intake under human review (``closed``): the review is over, with no lending decision recorded."""
        return await self._move(
            session, application_id, expected_version, ApplicationStatus.CLOSED, "credit_review_closed"
        )

    async def _move(
        self,
        session: Session,
        application_id: ApplicationId,
        expected_version: int,
        status: ApplicationStatus,
        action: str,
    ) -> CreditApplicationIntake:
        _agent_only(session)
        async with self._uow_factory(session.access_context()) as uow:
            moved = await uow.credit_applications.transition(
                application_id, status, expected_version=expected_version, at=self._clock.now(), reason_code=action
            )
            await self._audit(uow, session, action, application_id, SourceTable.CREDIT_APPLICATIONS)
            await uow.commit()
        return moved
