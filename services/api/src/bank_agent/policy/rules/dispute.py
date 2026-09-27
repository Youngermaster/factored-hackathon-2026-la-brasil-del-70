"""DSP and CRE rules: dispute intake, and credit product information."""

from bank_agent.domain.decision import DecisionKind
from bank_agent.domain.money import Money
from bank_agent.domain.transaction import TransactionStatus
from bank_agent.policy.facts import DisputeFacts, TransactionFacts
from bank_agent.policy.rules.context import CONVERSATION_RULES as RULES
from bank_agent.policy.rules.context import RuleContext
from bank_agent.policy.rules.registry import Verdict, fail, ok, str_list, typed_param

_MISSING_TRANSACTION = fail(DecisionKind.CLARIFY, "transaction_unknown", missing=("transaction",))


def _dispute(context: RuleContext) -> DisputeFacts:
    return context.facts.dispute or DisputeFacts()


def _transaction(context: RuleContext) -> TransactionFacts | None:
    return _dispute(context).transaction


@RULES.rule(
    "DSP.transaction_owned_by_session_customer",
    version=1,
    reasons=("transaction_owned", "transaction_unknown", "transaction_not_owned"),
    missing_facts=("transaction",),
)
def transaction_owned(context: RuleContext) -> Verdict:
    transaction = _transaction(context)
    if transaction is None:
        return _MISSING_TRANSACTION
    if not transaction.owned_by_session_customer:
        return fail(DecisionKind.REFUSE, "transaction_not_owned")
    return ok("transaction_owned")


@RULES.rule(
    "DSP.within_window",
    version=1,
    params={"dispute_window_days": int},
    reasons=("within_dispute_window", "transaction_unknown", "dispute_window_closed", "transaction_date_after_as_of"),
    missing_facts=("transaction",),
)
def within_window(context: RuleContext) -> Verdict:
    """Days from the transaction's local date to the data as-of date; day N of an N-day window still passes."""
    window = typed_param(context.params, "dispute_window_days", int)
    transaction = _transaction(context)
    if transaction is None:
        return _MISSING_TRANSACTION
    elapsed = (context.facts.data_as_of - transaction.occurred_on).days
    if elapsed < 0:
        return fail(DecisionKind.ESCALATE, "transaction_date_after_as_of", days_since_transaction=elapsed)
    if elapsed > window:
        return fail(
            DecisionKind.DENY, "dispute_window_closed", days_since_transaction=elapsed, dispute_window_days=window
        )
    return ok("within_dispute_window", days_since_transaction=elapsed, dispute_window_days=window)


@RULES.rule(
    "DSP.status_eligible",
    version=1,
    params={"eligible_statuses": list},
    reasons=("status_eligible", "transaction_unknown", "transaction_pending", "transaction_status_not_eligible"),
    missing_facts=("transaction",),
)
def status_eligible(context: RuleContext) -> Verdict:
    eligible = str_list(context.params, "eligible_statuses")
    transaction = _transaction(context)
    if transaction is None:
        return _MISSING_TRANSACTION
    status = transaction.status.value
    if status in eligible:
        return ok("status_eligible", status=status)
    if transaction.status is TransactionStatus.PENDING:
        return fail(DecisionKind.ABSTAIN, "transaction_pending", status=status)
    return fail(DecisionKind.DENY, "transaction_status_not_eligible", status=status)


@RULES.rule(
    "DSP.not_already_disputed",
    version=1,
    reasons=("not_disputed", "transaction_unknown", "already_disputed"),
    missing_facts=("transaction",),
)
def not_already_disputed(context: RuleContext) -> Verdict:
    transaction = _transaction(context)
    if transaction is None:
        return _MISSING_TRANSACTION
    if transaction.has_open_dispute:
        return fail(DecisionKind.DENY, "already_disputed")
    return ok("not_disputed")


@RULES.rule(
    "DSP.reason_supported",
    version=1,
    params={"supported_reasons": list},
    reasons=("reason_supported", "reason_unknown", "reason_needs_human"),
    missing_facts=("reason",),
)
def reason_supported(context: RuleContext) -> Verdict:
    supported = str_list(context.params, "supported_reasons")
    reason = _dispute(context).reason
    if reason is None:
        return fail(DecisionKind.CLARIFY, "reason_unknown", missing=("reason",))
    if reason.value in supported:
        return ok("reason_supported", reason=reason.value)
    return fail(DecisionKind.ESCALATE, "reason_needs_human", reason=reason.value)


def _disputed_amount(context: RuleContext) -> Money | None:
    dispute = _dispute(context)
    if dispute.disputed_amount is not None:
        return dispute.disputed_amount
    return dispute.transaction.amount if dispute.transaction is not None else None


@RULES.rule(
    "DSP.amount_within_auto_limit",
    version=1,
    params={"auto_intake_max_amount": Money},
    reasons=("amount_within_auto_limit", "amount_unknown", "amount_not_comparable", "amount_above_auto_limit"),
    missing_facts=("disputed_amount",),
)
def amount_within_auto_limit(context: RuleContext) -> Verdict:
    """Amounts exactly at the limit pass; a different currency cannot be compared, so a human decides."""
    limit = typed_param(context.params, "auto_intake_max_amount", Money)
    amount = _disputed_amount(context)
    if amount is None:
        return fail(DecisionKind.CLARIFY, "amount_unknown", missing=("disputed_amount",))
    if amount.currency is not limit.currency:
        return fail(DecisionKind.ESCALATE, "amount_not_comparable", auto_intake_max_amount=limit)
    if amount > limit:
        return fail(DecisionKind.ESCALATE, "amount_above_auto_limit", auto_intake_max_amount=limit)
    return ok("amount_within_auto_limit", auto_intake_max_amount=limit)


@RULES.rule(
    "DSP.required_fields_present",
    version=1,
    params={"required_fields": list},
    reasons=(
        "required_fields_present",
        "required_fields_missing",
        "disputed_amount_not_positive",
        "disputed_amount_exceeds_transaction",
    ),
    missing_facts=("transaction", "reason", "disputed_amount"),
)
def required_fields_present(context: RuleContext) -> Verdict:
    dispute = _dispute(context)
    values = {"transaction": dispute.transaction, "reason": dispute.reason, "disputed_amount": dispute.disputed_amount}
    missing = tuple(name for name in str_list(context.params, "required_fields") if values.get(name) is None)
    if missing:
        return fail(DecisionKind.CLARIFY, "required_fields_missing", missing=missing)
    amount, transaction = dispute.disputed_amount, dispute.transaction
    if amount is None or transaction is None:
        return ok("required_fields_present")
    if amount.amount <= 0:
        return fail(DecisionKind.CLARIFY, "disputed_amount_not_positive")
    if amount.currency is transaction.amount.currency and amount > transaction.amount:
        return fail(DecisionKind.CLARIFY, "disputed_amount_exceeds_transaction")
    return ok("required_fields_present")


@RULES.rule("DSP.case_within_sla", version=1, reasons=("case_within_sla", "case_sla_breached"))
def case_within_sla(context: RuleContext) -> Verdict:
    """An open case past its resolution SLA goes to a person (the ``DSP-<country>-2`` clause says so)."""
    if _dispute(context).case_sla_breached:
        return fail(DecisionKind.ESCALATE, "case_sla_breached")
    return ok("case_within_sla")
