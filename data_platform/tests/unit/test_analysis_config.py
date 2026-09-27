from pathlib import Path

import pytest
import yaml

from bank_data.analysis.config import (
    CRITERIA,
    DEFAULT_COST_FILE,
    DEFAULT_SCORING_FILE,
    WORKFLOWS,
    load_costs,
    load_mapping,
    load_scoring,
)
from bank_data.analysis.queries import DATA_SUPPORT_ITEMS
from bank_data.errors import ConfigurationError

HEADER = "source,value,subcategory,workflow_id,sub_intent,strict_workflow_id,alternative_workflow_id,rationale\n"
RATIONALE = "a rationale long enough"


def _mapping(tmp_path: Path, *rows: str, header: str = HEADER) -> Path:
    path = tmp_path / "mapping.csv"
    path.write_text(header + "".join(f"{row}\n" for row in rows), encoding="utf-8")
    return path


def test_the_preregistered_scoring_file_uses_the_prompt_default_weights() -> None:
    scoring = load_scoring()
    assert scoring.weights == {
        "demand": 20,
        "pain": 25,
        "automatable_share": 20,
        "harm_inverse": 10,
        "data_support": 15,
        "demo_depth": 10,
    }
    assert set(scoring.weights) == set(CRITERIA)
    assert scoring.sensitivity.delta_points == 5
    assert set(scoring.harm) == set(WORKFLOWS)


def test_every_data_support_item_in_use_has_a_measurement() -> None:
    known = {item.name for item in DATA_SUPPORT_ITEMS}
    assert load_scoring().items_in_use() <= known


def test_every_cost_value_is_labeled_as_an_unverified_assumption() -> None:
    costs = load_costs()
    assert costs.currency == "USD"
    assert set(costs.countries) == {"MX", "CO", "AR"}
    for country in costs.countries.values():
        assert country.assumption is True
        assert country.verified is False
    assert costs.after_call_work_factor.assumption is True
    assert costs.cost_per_minute("MX") == pytest.approx(0.18 * 1.15)
    assert costs.cost_per_minute("BR") is None
    assert costs.cost_per_minute(None) is None


def test_cost_values_not_marked_as_assumptions_are_refused(tmp_path: Path) -> None:
    document = yaml.safe_load(DEFAULT_COST_FILE.read_text(encoding="utf-8"))
    document["countries"]["MX"]["assumption"] = False
    path = tmp_path / "costs.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="assumption"):
        load_costs(path)


def test_scoring_with_a_missing_weight_is_refused(tmp_path: Path) -> None:
    document = yaml.safe_load(DEFAULT_SCORING_FILE.read_text(encoding="utf-8"))
    del document["weights"]["pain"]
    path = tmp_path / "scoring.yaml"
    path.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="weights"):
        load_scoring(path)


def test_unreadable_configuration_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="cannot read"):
        load_scoring(tmp_path / "missing.yaml")
    with pytest.raises(ConfigurationError, match="cannot read"):
        load_mapping(tmp_path / "missing.csv")


def test_mapping_lookup_and_scenarios(tmp_path: Path) -> None:
    mapping = load_mapping(
        _mapping(
            tmp_path,
            f"contact_reason,Producto,,card_support,,other,credit,{RATIONALE}",
            f"complaint_category,Fees,Cobro indebido,dispute,dispute_new,dispute,dispute,{RATIONALE}",
        )
    )
    row = mapping.lookup("contact_reason", " Producto ")
    assert row is not None
    assert (row.workflow_for("primary"), row.workflow_for("strict"), row.workflow_for("alternative")) == (
        "card_support",
        "other",
        "credit",
    )
    assert mapping.lookup("complaint_category", "Fees", "Cobro indebido") is not None
    assert mapping.lookup("complaint_category", "Fees", None) is None
    assert len(mapping.for_source("contact_reason")) == 1


@pytest.mark.parametrize(
    ("row", "message"),
    [
        (f"contact_reason,X,,loans,,other,other,{RATIONALE}", "unknown workflow"),
        (f"contact_reason,X,,other,balance_inquiry,other,other,{RATIONALE}", "names a sub-intent"),
        (f"contact_reason,X,sub,other,,other,other,{RATIONALE}", "subcategory"),
        (f"channel,X,,other,,other,other,{RATIONALE}", "unknown mapping source"),
        ("contact_reason,X,,other,,other,other,short", "rationale"),
    ],
)
def test_invalid_mapping_rows_are_refused(tmp_path: Path, row: str, message: str) -> None:
    with pytest.raises(ConfigurationError, match=message):
        load_mapping(_mapping(tmp_path, row))


def test_duplicate_mapping_rows_and_wrong_columns_are_refused(tmp_path: Path) -> None:
    row = f"contact_reason,X,,other,,other,other,{RATIONALE}"
    with pytest.raises(ConfigurationError, match="duplicate"):
        load_mapping(_mapping(tmp_path, row, row))
    with pytest.raises(ConfigurationError, match="columns"):
        load_mapping(_mapping(tmp_path, "X,other", header="value,workflow_id\n"))
