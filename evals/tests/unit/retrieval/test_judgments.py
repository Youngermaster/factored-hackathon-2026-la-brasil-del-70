"""The judgment model and loader."""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from bank_evals.retrieval.judgments import Judgment, JudgmentsError, judgments_digest, load_judgments


def row(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "query_id": "dsp-01",
        "workflow": "dispute",
        "query": "¿Cuántos días tengo para aclarar un cargo?",
        "language": "es",
        "locale": "es-MX",
        "jurisdiction": "MX",
        "relevant": [{"clause_id": "DSP-MX-1", "grade": 2}],
        "expected": "answer",
        "split": "dev",
        "provenance": "team_generated",
        "review_status": "pending",
    }
    return {**fields, **overrides}


def test_a_valid_judgment_exposes_its_grades() -> None:
    judgment = Judgment.model_validate(
        row(relevant=[{"clause_id": "DSP-MX-1", "grade": 2}, {"clause_id": "INF-ALL-1", "grade": 1}])
    )
    assert judgment.grades == {"DSP-MX-1": 2, "INF-ALL-1": 1}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"locale": "pt-BR"}, "locale must be in the judgment's language"),
        ({"expected": "abstain"}, "an abstention has no relevant clause"),
        ({"workflow": "out_of_scope"}, "exactly the out-of-scope queries"),
        ({"relevant": [{"clause_id": "DSP-MX-1", "grade": 2}, {"clause_id": "DSP-MX-1", "grade": 1}]}, "listed once"),
        ({"relevant": [{"clause_id": "NOPE-MX-1", "grade": 2}]}, "clause_id"),
        ({"provenance": "model_generated"}, "provenance"),
    ],
)
def test_invalid_judgments_are_refused(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Judgment.model_validate(row(**overrides))


def test_out_of_scope_queries_expect_abstention() -> None:
    judgment = Judgment.model_validate(row(query_id="oos-01", workflow="out_of_scope", relevant=[], expected="abstain"))
    assert judgment.grades == {}


def write(path: Path, *rows: dict[str, Any]) -> Path:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n\n", encoding="utf-8")
    return path


def test_the_loader_reads_lines_and_reports_the_line_of_a_bad_one(tmp_path: Path) -> None:
    good = write(tmp_path / "good.jsonl", row(), row(query_id="dsp-02"))
    assert [j.query_id for j in load_judgments(good)] == ["dsp-01", "dsp-02"]
    assert len(judgments_digest(good)) == 12
    bad = write(tmp_path / "bad.jsonl", row(), row(query_id="dsp-02", split="train"))
    with pytest.raises(JudgmentsError, match=r"line 2 of bad\.jsonl"):
        load_judgments(bad)
    (tmp_path / "broken.jsonl").write_text("{not json\n", encoding="utf-8")
    with pytest.raises(JudgmentsError, match="line 1"):
        load_judgments(tmp_path / "broken.jsonl")
    repeated = write(tmp_path / "repeated.jsonl", row(), row())
    with pytest.raises(JudgmentsError, match="repeats a query id"):
        load_judgments(repeated)
