"""Resolver units: description templates, the tree dump conversion, outcome metrics, silver sheets, windows, CLI."""

import csv
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from bank_agent.application.understanding.descriptor import deterministic_descriptor
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.identifiers import CustomerId, ProductId, TransactionId
from bank_agent.domain.intelligence import RankedCandidate, TransactionDescriptor, TransactionResolution
from bank_agent.domain.locale import Country
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.transaction import (
    FraudContext,
    Transaction,
    TransactionChannel,
    TransactionStatus,
    TransactionType,
)
from bank_ml.cli import app
from bank_ml.common.seeds import rng
from bank_ml.resolver import command
from bank_ml.resolver.dataset import Query, windows
from bank_ml.resolver.describe import amount_phrase, date_phrase, describe, merchant_phrase, misspell
from bank_ml.resolver.evaluate import Outcomes, candidate_bucket, evaluate, failures
from bank_ml.resolver.models import UNFITTED, convert
from bank_ml.resolver.report import _mask
from bank_ml.resolver.silver import export_sheet, sheet_status

NOW = datetime(2026, 3, 10, 18, tzinfo=UTC)


def txn(identifier: str, amount: str = "1250.50", days: int = 2, merchant: str | None = "Super Ahorro") -> Transaction:
    return Transaction(
        transaction_id=TransactionId(identifier), customer_id=CustomerId("CLI-1"), product_id=ProductId("PRD-1"),
        occurred_at=NOW - timedelta(days=days), transaction_type=TransactionType.PURCHASE,
        amount=Money.of(amount, Currency.ARS), channel=TransactionChannel.POS, status=TransactionStatus.APPROVED,
        merchant_name=UntrustedText(merchant) if merchant else None, location_country="AR",
        fraud=FraudContext(label=False),
    )  # fmt: skip


def query(target: str | None, candidates: list[Transaction], customer: str = "CLI-1") -> Query:
    return Query(f"q:{target}", "dispute", "test", "es", Country.AR, customer, NOW, "text",
                 {"amount": "exact", "merchant": "none", "date": "none", "channel": "none"},
                 TransactionDescriptor(amount=Decimal(1)), candidates, target)  # fmt: skip


def test_amount_merchant_and_date_phrases_parse_back() -> None:
    target = txn("T1", "15230.00")
    assert amount_phrase(target, Country.AR, "es", "slang") == "de 15 lucas"
    assert amount_phrase(target, Country.MX, "es", "exact") == "de $15,230"
    assert amount_phrase(target, Country.AR, "es", "rounded") == "de como 15.200 pesos"
    assert amount_phrase(txn("T2", "12.50"), Country.CO, "pt", "rounded") == "de uns 10 pesos"
    assert misspell("Super Ahorro", rng("x")) != "Super Ahorro"
    assert merchant_phrase("Super Ahorro", "pt", "partial", rng("x")) == "na Ahorro"
    today = date(2026, 3, 10)
    assert date_phrase(date(2026, 3, 9), today, "es", "relative") == "ayer"
    assert date_phrase(date(2026, 3, 7), today, "pt", "weekday") == "no sábado"
    assert date_phrase(date(2026, 3, 2), today, "pt", "days_ago") == "há 8 dias"
    assert date_phrase(date(2026, 3, 2), today, "es", "explicit") == "el 2 de marzo"


def test_descriptions_are_deterministic_and_always_give_a_clue() -> None:
    target = txn("T1")
    day = target.occurred_at.date()
    for number in range(40):
        for language in ("es", "pt"):
            kwargs: dict[str, Any] = {"use": "dispute", "country": Country.AR, "language": language}
            first = describe(target, **kwargs, today=NOW.date(), day=day, generator=rng("d", number))
            again = describe(target, **kwargs, today=NOW.date(), day=day, generator=rng("d", number))
            assert first == again
            assert {first.clues["amount"], first.clues["merchant"], first.clues["date"]} != {"none"}
    payment = describe(txn("T9", merchant=None), use="payment_lookup", country=Country.MX, language="es",
                       today=NOW.date(), day=day, generator=rng("p"))  # fmt: skip
    assert payment.clues["merchant"] == "none"
    parsed = deterministic_descriptor("Me cobraron de 15 lucas ayer", NOW.date(), frozenset({Currency.ARS}))
    assert parsed.amount == Decimal(15000)


def test_dump_conversion_keeps_numerical_splits_and_refuses_others() -> None:
    split = {
        "split_feature": 2,
        "threshold": 0.5,
        "decision_type": "<=",
        "default_left": False,
        "missing_type": "NaN",
        "left_child": {"leaf_value": 1.0},
        "right_child": {"leaf_value": -1.0},
    }
    dump: dict[str, Any] = {"tree_info": [{"tree_structure": split}, {"tree_structure": {"leaf_value": 0.25}}]}
    trees = convert(dump)
    assert trees[0]["missing"] == "nan"
    assert trees[1] == {"value": 0.25}
    dump["tree_info"][0]["tree_structure"]["decision_type"] = "=="
    with pytest.raises(ValueError, match="only numerical"):
        convert(dump)


class Scripted:
    name = "scripted"

    def __init__(self, winners: dict[str, str]) -> None:
        self._winners = {key: TransactionId(value) for key, value in winners.items()}

    def rank(self, item: Query) -> TransactionResolution:
        ranked = tuple(
            RankedCandidate(transaction_id=t.transaction_id, score=1.0 / (i + 1), rank=i + 1)
            for i, t in enumerate(item.candidates)
        )
        return TransactionResolution(
            ranked=ranked, margin=0.5, clear_winner=self._winners.get(item.query_id), model=UNFITTED
        )


def test_outcomes_count_wrong_auto_selections_clarifications_and_absent_targets() -> None:
    a, b, c = txn("A"), txn("B"), txn("C")
    queries = [query("A", [a, b]), query("B", [a, b], "CLI-2"), query(None, [c], "CLI-3"), query("B", [a, b], "CLI-4")]
    model = Scripted({"q:A": "A", "q:B": "A", "q:None": "C"})
    outcomes = Outcomes("scripted", queries, model)
    summary = outcomes.summary()
    assert summary["top1"]["estimate"] == pytest.approx(1 / 3)
    assert summary["wrong_rate"]["estimate"] == pytest.approx(3 / 4)
    assert summary["absent_false_auto"]["estimate"] == 1.0
    assert summary["clarified"] == 0
    result = evaluate(outcomes)
    assert {row["slice"] for row in result["by_candidates"]} == {"1", "2-3"}
    assert failures(outcomes)[0]["auto_selected_wrong"] is True
    assert candidate_bucket(query("A", [a] * 8)) == "7+"
    assert _mask("de $1.250 el 03/05 | x") == "de $#.### el ##/## / x"


def test_windows_come_from_the_policy_clauses() -> None:
    found = windows()
    assert found["dispute"] == {Country.MX: 90, Country.CO: 60, Country.AR: 30}
    assert set(found["payment_lookup"].values()) == {92}


def test_silver_sheet_status_and_keep(tmp_path: Path) -> None:
    sheet = tmp_path / "silver.csv"
    assert sheet_status(sheet) == {"status": "not exported"}
    assert export_sheet([], sheet) == "written"
    assert sheet_status(sheet) == {"status": "pending", "items": 0}
    with sheet.open("a", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["C1", "Fees", "10", "ARS", "", "T1", "10", "", "", "yes", "reviewer", ""])
        writer.writerow(["C2", "Fees", "10", "ARS", "", "T2", "10", "", "", "no", "reviewer", ""])
    assert sheet_status(sheet)["precision"] == 0.5
    assert export_sheet([], sheet) == "kept"


def test_resolver_cli_reports_and_promotes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    runner = CliRunner()
    dataset = SimpleNamespace(card=SimpleNamespace(content_hash="b" * 64, rows_per_split={"train": 1}))
    monkeypatch.setattr(command, "train", lambda *args, **kwargs: (dataset, "resolver:lgbm@abc"))
    result = runner.invoke(app, ["resolver", "train", "--registry-dir", str(tmp_path), "--tracking-uri", "none"])
    assert "registered resolver:lgbm@abc as candidate" in result.output
    estimate = {"two_or_more_candidates": {"top1": {"estimate": 0.9}}}
    monkeypatch.setattr(command, "evaluate_all", lambda *a, **k: {"models": {"lgbm": {"test": {"dispute": estimate}}}})
    result = runner.invoke(app, ["resolver", "evaluate", "--registry-dir", str(tmp_path), "--no-report"])
    assert "lgbm dispute: top-1 0.900" in result.output
    result = runner.invoke(app, ["resolver", "promote", "--approved-by", "x", "--registry-dir", str(tmp_path)])
    assert "no candidate" in result.output
