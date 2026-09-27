"""EXECUTE and VERIFY for disputes: the optional protective block first, then the case; success only after read-back."""

from bank_agent.application.engine.context import Step, TurnContext
from bank_agent.application.engine.definition import RESOLVED
from bank_agent.application.engine.reply import Masked, Param, Reply
from bank_agent.application.engine.shared import clause_ref
from bank_agent.application.workflows.dispute.data import BlockOffer, load, save
from bank_agent.application.workflows.dispute.decide import (
    CONFIRM,
    block_request,
    card_facts,
    case_request,
    dispute_facts,
)
from bank_agent.application.workflows.shared.writes import PlannedWrite, ReadBack, execute_writes, verify_writes
from bank_agent.domain.actions import ActionKind, CreateDisputeArguments, ToolName
from bank_agent.domain.cards import CardBlockReason
from bank_agent.domain.conversation import ActionDisplayStatus, ActionStatusView
from bank_agent.domain.identifiers import CaseId, SourceRef, SourceTable
from bank_agent.domain.workflow import Outcome

VERIFY = "VERIFY"
EXECUTE = "EXECUTE"


async def execute(ctx: TurnContext) -> Step:
    data = load(ctx)
    found = await dispute_facts(ctx, data)
    if found is None or data.product_id is None:
        return Step(CONFIRM)
    facts, _ = found
    writes: list[PlannedWrite] = []
    blocking = data.block_offer is BlockOffer.ACCEPTED
    block = block_request(ctx, data, confirmed=True, state="EXECUTE_BLOCK") if blocking else None
    if block is not None:
        product_id = data.product_id

        async def run_block() -> SourceRef:
            product = await ctx.tools.block_card(
                product_id, block.idempotency_key, CardBlockReason.UNRECOGNIZED_ACTIVITY
            )
            return SourceRef.of(SourceTable.PRODUCTS, product.product_id)

        writes.append(PlannedWrite(block, "EXECUTE_BLOCK", run_block, card=card_facts(data)))
    case = case_request(ctx, data, confirmed=True, state="CREATE_CASE")
    if case is None:
        return Step(CONFIRM)
    arguments = case.arguments
    if not isinstance(arguments, CreateDisputeArguments):
        return Step(CONFIRM)

    async def run_case() -> SourceRef:
        created = await ctx.tools.create_dispute_case(arguments, case.idempotency_key)
        return SourceRef.of(SourceTable.DISPUTE_CASES, created.case_id)

    writes.append(PlannedWrite(case, "CREATE_CASE", run_case, dispute=facts))
    stop = await execute_writes(ctx, writes, state=EXECUTE)
    if stop is not None:
        return stop
    executed = ctx.engine.executed_for(case.idempotency_key)
    if executed is not None and executed.outcome_ref is not None:
        save(ctx, data.evolve(case_id=CaseId(executed.outcome_ref.key)))
    return Step(VERIFY)


async def verify(ctx: TurnContext) -> Step:
    data = load(ctx)
    verifier = ctx.write_verifier()
    reads: list[ReadBack] = []
    block = block_request(ctx, data, confirmed=True, state="EXECUTE_BLOCK")
    blocking = data.block_offer is BlockOffer.ACCEPTED and block is not None and data.product_id is not None
    if blocking and block is not None and data.product_id is not None:
        product_id = data.product_id
        reads.append(ReadBack(ToolName.BLOCK_CARD, block.idempotency_key, lambda: verifier.card_blocked(product_id)))
    case = case_request(ctx, data, confirmed=True, state="CREATE_CASE")
    if case is None or data.case_id is None or data.transaction_id is None or data.reason is None:
        return Step(CONFIRM)
    case_id, txn_id, reason = data.case_id, data.transaction_id, data.reason
    reads.append(
        ReadBack(
            ToolName.CREATE_DISPUTE_CASE,
            case.idempotency_key,
            lambda: verifier.dispute_case_recorded(case_id, transaction_id=txn_id, reason=reason),
        )
    )
    stop = await verify_writes(ctx, reads, case_ref=case_id)
    if stop is not None:
        return stop
    stored = await ctx.tools.get_case_status(case_id)
    due = stored.sla_due_at.astimezone(ctx.zone).date() if stored is not None else ctx.today
    ctx.recorder.case_refs.append(case_id)
    statuses = [
        ActionStatusView(
            action=ActionKind.CREATE_DISPUTE_CASE,
            status=ActionDisplayStatus.VERIFIED,
            reference=SourceRef.of(SourceTable.DISPUTE_CASES, case_id),
            evidence=SourceRef.of(SourceTable.DISPUTE_CASES, case_id),
        )
    ]
    params: dict[str, Param] = {"case": case_id, "due": due}
    explain = [clause_ref(ctx, "INF-ALL-1")]
    template = "dispute.case_created"
    if blocking and data.product_id is not None:
        evidence = SourceRef.of(SourceTable.PRODUCTS, data.product_id)
        statuses.insert(
            0, ActionStatusView(action=ActionKind.BLOCK_CARD, status=ActionDisplayStatus.VERIFIED, evidence=evidence)
        )
        params["card"] = Masked(data.product_last4 or "----")
        explain.append(clause_ref(ctx, "INF-ALL-2"))
        template = "dispute.case_created_and_blocked"
    save(ctx, data.evolve(summary_shown=False))
    reply = Reply(template=template, params=params, explain=tuple(explain), action_statuses=tuple(statuses))
    return Step(RESOLVED, reply, Outcome.RESOLVED)
