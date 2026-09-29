"""B1's tools: the same capabilities as the application's tool set, but every tool takes ``customer_id`` from the
model, and nothing checks policy, asks for confirmation, or reads a write back.

Each call returns a JSON-able result or an error string, never raises. Scheduled failures from the scenario's
plan apply through the application tool each B1 tool stands for (``APP_TOOL``).
"""

from __future__ import annotations

import json
from datetime import timedelta
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from bank_agent.domain.actions import ToolFailureMode, ToolName
from bank_evals.systems.naive_agent.database import NaiveDatabase, NaiveHandoff
from bank_evals.systems.schedule import FailureSchedule
from bank_evals.world.model import AS_OF, NOW

CATALOG_DIR = Path(__file__).resolve().parents[5] / "policies" / "credit"
WRITES = frozenset({"block_card", "create_dispute", "submit_credit_application"})
APP_TOOL: dict[str, ToolName] = {
    "get_balances": ToolName.LIST_MY_BALANCES,
    "list_transactions": ToolName.LIST_RECENT_TRANSACTIONS,
    "get_payment_status": ToolName.GET_PAYMENT_STATUS,
    "get_statement": ToolName.GET_STATEMENT_SUMMARY,
    "list_cards": ToolName.LIST_MY_CARDS,
    "block_card": ToolName.BLOCK_CARD,
    "list_cases": ToolName.LIST_MY_CASES,
    "create_dispute": ToolName.CREATE_DISPUTE_CASE,
    "list_credit_products": ToolName.LIST_CREDIT_PRODUCTS,
    "get_credit_profile": ToolName.GET_MY_CREDIT_PROFILE,
    "submit_credit_application": ToolName.SUBMIT_CREDIT_APPLICATION,
    "list_credit_applications": ToolName.LIST_MY_CREDIT_APPLICATIONS,
}
TOOLS = frozenset({*APP_TOOL, "transfer_to_human"})


@cache
def catalog() -> list[dict[str, Any]]:
    entries = []
    for path in sorted(CATALOG_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        entries.append(
            {
                key: raw[key]
                for key in (
                    "product_code",
                    "product_type",
                    "jurisdiction",
                    "currency",
                    "min_amount",
                    "max_amount",
                    "min_term_months",
                    "max_term_months",
                    "max_annual_rate",
                )
            }
        )
    return entries


def _money(value: Any) -> str:
    return f"{value.amount} {value.currency.value}" if value is not None else "none"


class NaiveTools:
    def __init__(self, db: NaiveDatabase, schedule: FailureSchedule) -> None:
        self.db, self.schedule = db, schedule

    def call(self, tool: str, arguments: dict[str, str]) -> tuple[str, Any]:
        """Run ``tool``; return ``(status, result)`` where status is ok, error, or not_found."""
        if tool not in TOOLS:
            return "error", f"unknown tool {tool}"
        mode = self.schedule.next_mode(APP_TOOL[tool].value) if tool in APP_TOOL else None
        if mode in {ToolFailureMode.TIMEOUT, ToolFailureMode.TRANSIENT_ERROR, ToolFailureMode.PERMANENT_ERROR}:
            return "error", f"{tool} failed: {mode.value if mode else ''}"
        try:
            result = getattr(self, f"_{tool}")(arguments, dry_run=mode is ToolFailureMode.PARTIAL_WRITE)
        except (KeyError, ValueError) as error:
            return "error", f"{tool}: invalid arguments ({error})"
        return ("not_found", result) if result is None else ("ok", result)

    def _customer(self, arguments: dict[str, str]) -> str:
        return arguments["customer_id"]

    def _get_balances(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        products = self.db.products(self._customer(arguments))
        return [
            {
                "product_id": p.product_id,
                "type": p.product_type.value,
                "number": str(p.masked_number),
                "balance": _money(p.current_balance),
                "limit": _money(p.credit_limit),
                "as_of": AS_OF.date().isoformat(),
            }
            for p in products
            if p.current_balance is not None
        ] or None

    def _list_transactions(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        rows = self.db.transactions(self._customer(arguments))[:30]
        return [
            {
                "transaction_id": t.transaction_id,
                "date": t.occurred_at.date().isoformat(),
                "merchant": str(t.merchant_name or ""),
                "amount": _money(t.amount),
                "status": t.status.value,
                "type": t.transaction_type.value,
                "product_id": t.product_id,
            }
            for t in rows
        ] or None

    def _get_payment_status(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        rows = [
            t
            for t in self.db.transactions(self._customer(arguments))
            if t.transaction_id == arguments["transaction_id"]
        ]
        return {"status": rows[0].status.value, "as_of": AS_OF.date().isoformat()} if rows else None

    def _get_statement(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        month = arguments["month"]
        rows = [t for t in self.db.transactions(self._customer(arguments)) if t.occurred_at.strftime("%Y-%m") == month]
        return [
            {
                "date": t.occurred_at.date().isoformat(),
                "merchant": str(t.merchant_name or ""),
                "amount": _money(t.amount),
                "status": t.status.value,
            }
            for t in rows
        ] or None

    def _list_cards(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        cards = [p for p in self.db.products(self._customer(arguments)) if "card" in p.product_type.value]
        return [
            {
                "product_id": p.product_id,
                "type": p.product_type.value,
                "number": str(p.masked_number),
                "status": p.status.value,
                "expires_on": str(p.expires_on),
            }
            for p in cards
        ] or None

    def _block_card(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        if dry_run:
            return {"blocked": True, "product_id": arguments["product_id"]}
        return (
            {"blocked": True, "product_id": arguments["product_id"]} if self.db.block(arguments["product_id"]) else None
        )

    def _list_cases(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        customer = self._customer(arguments)
        cases = [c for c in self.db.world.cases if c.customer_id == customer]
        return [
            {
                "case_id": c.case_id,
                "transaction_id": c.transaction_id,
                "status": c.status.value,
                "opened_at": c.opened_at.date().isoformat(),
                "sla_due_at": c.sla_due_at.date().isoformat(),
            }
            for c in cases
        ] + [dict(c) for c in self.db.new_cases if c["customer_id"] == customer] or None

    def _create_dispute(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        case = {
            "case_id": f"case-naive-{len(self.db.new_cases) + 1:04d}",
            "customer_id": self._customer(arguments),
            "transaction_id": arguments["transaction_id"],
            "reason": arguments.get("reason", "other"),
            "status": "open",
            "sla_due_at": (NOW + timedelta(days=30)).date().isoformat(),
        }
        if not dry_run:
            self.db.new_cases.append(case)
        return case

    def _list_credit_products(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        return [entry for entry in catalog() if entry["jurisdiction"] == arguments.get("country")] or None

    def _get_credit_profile(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        customer = self._customer(arguments)
        profile = next((p for p in self.db.world.credit_profiles if p.customer_id == customer), None)
        if profile is None:
            return None
        return {
            "credit_score": profile.credit_score,
            "monthly_income": _money(profile.estimated_monthly_income),
            "days_past_due": profile.max_days_past_due,
            "tenure_months": profile.tenure_months,
        }

    def _submit_credit_application(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        application = {
            "application_id": f"app-naive-{len(self.db.new_applications) + 1:04d}",
            "customer_id": self._customer(arguments),
            "product_code": arguments["product_code"],
            "amount": arguments.get("amount", ""),
            "status": "submitted",
        }
        if not dry_run:
            self.db.new_applications.append(application)
        return application

    def _list_credit_applications(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        customer = self._customer(arguments)
        existing = [
            {"application_id": a.application_id, "product_code": a.product_code, "status": a.status.value}
            for a in self.db.world.credit_applications
            if a.customer_id == customer
        ]
        return existing + [a for a in self.db.new_applications if a["customer_id"] == customer] or None

    def _transfer_to_human(self, arguments: dict[str, str], *, dry_run: bool) -> Any:
        def items(key: str) -> list[str]:
            return [part.strip() for part in arguments.get(key, "").split(";") if part.strip()]

        self.db.handoffs.append(
            NaiveHandoff(
                customer_id=self._customer(arguments),
                reason=arguments.get("reason", ""),
                request=arguments.get("request", ""),
                verified_facts=items("verified_facts"),
                actions_taken=items("actions_taken"),
                open_questions=items("open_questions"),
            )
        )
        return {"transferred": True}


def render_result(tool: str, status: str, result: Any) -> str:
    return json.dumps({"tool": tool, "status": status, "result": result}, ensure_ascii=False, default=str)
