from pathlib import Path

import pandas as pd
import pytest

from bank_data.analysis.labeling import (
    PENDING,
    SAMPLE_COLUMNS,
    has_human_labels,
    prelabel,
    prelabel_frame,
    read_labels,
    select_sample,
    write_prelabels,
    write_sample,
)

BALANCE = "Hola, buenos días. Quisiera saber cuál es mi saldo actual en mi cuenta de ahorros."


def _candidates() -> pd.DataFrame:
    rows = []
    for workflow, count in (("account_inquiry", 30), ("dispute", 30), ("other", 10)):
        for index in range(count):
            country = ("MX", "CO", "AR")[index % 3] if workflow != "dispute" or index < 24 else "AR"
            rows.append(
                {
                    "interaction_id": f"INT-{workflow}-{index:03d}",
                    "workflow": workflow,
                    "country": country,
                    "customer_text": f" {BALANCE} ",
                }
            )
    return pd.DataFrame(rows)


def test_sample_is_stratified_by_country_deterministic_and_in_scope_only() -> None:
    first = select_sample(_candidates(), per_workflow=9, seed="s")
    assert first.equals(select_sample(_candidates(), per_workflow=9, seed="s"))
    assert list(first.columns) == list(SAMPLE_COLUMNS)
    assert set(first["workflow_stratum"]) == {"account_inquiry", "dispute"}
    assert first["item_id"].tolist() == [f"LBL-{index:04d}" for index in range(1, 19)]
    ids = first[first["workflow_stratum"] == "account_inquiry"]["interaction_id"]
    countries = _candidates().set_index("interaction_id").loc[ids, "country"]
    assert countries.value_counts().to_dict() == {"MX": 3, "CO": 3, "AR": 3}
    assert first["customer_text"].iloc[0] == BALANCE
    assert (first["adjudicated_resolvable"] == "").all()
    assert not select_sample(_candidates(), per_workflow=9, seed="other")["interaction_id"].equals(
        first["interaction_id"]
    )


def test_a_short_stratum_passes_its_shortfall_to_the_others() -> None:
    frame = _candidates()
    frame = frame[~((frame["workflow"] == "dispute") & (frame["country"] == "MX"))]
    sample = select_sample(frame, per_workflow=12, seed="s")
    dispute = sample[sample["workflow_stratum"] == "dispute"]
    assert len(dispute) == 12
    countries = frame.set_index("interaction_id").loc[dispute["interaction_id"], "country"]
    assert "MX" not in set(countries)


def test_an_empty_candidate_frame_gives_an_empty_sample() -> None:
    empty = select_sample(_candidates().iloc[0:0], per_workflow=5, seed="s")
    assert empty.empty
    assert list(empty.columns) == list(SAMPLE_COLUMNS)


def test_prelabel_marks_balance_questions_resolvable_but_matching_only_account_inquiry() -> None:
    assert prelabel(BALANCE, "account_inquiry").matches_workflow == "yes"
    card = prelabel(BALANCE, "card_support")
    assert (card.topic, card.resolvable, card.matches_workflow, card.rule) == (
        "balance_inquiry",
        "yes",
        "no",
        "balance_keywords",
    )
    dispute = prelabel("No reconozco un cargo de ayer", "dispute")
    assert (dispute.topic, dispute.resolvable, dispute.matches_workflow) == ("dispute_new", "unclear", "yes")
    assert prelabel("Quiero bloquear mi tarjeta", "card_support").topic == "card_block"
    assert prelabel("Quiero un préstamo personal", "credit").topic == "credit_product_info"
    assert prelabel("Buenas tardes", "credit").rule == "no_rule"


def test_prelabels_are_pending_review(tmp_path: Path) -> None:
    sample = select_sample(_candidates(), per_workflow=3, seed="s")
    frame = prelabel_frame(sample)
    assert set(frame["review_status"]) == {"pending"}
    write_prelabels(tmp_path / "pre.csv", frame)
    assert (tmp_path / "pre.csv").read_text(encoding="utf-8").startswith("item_id,")


def test_write_sample_never_overwrites_human_labels(tmp_path: Path) -> None:
    path = tmp_path / "labeling" / "sample.csv"
    sample = select_sample(_candidates(), per_workflow=3, seed="s")
    assert write_sample(path, sample) == "written"
    assert not has_human_labels(path)
    labeled = pd.read_csv(path, dtype=str, keep_default_na=False)
    labeled.loc[0, "labeler_1_resolvable"] = "yes"
    labeled.to_csv(path, index=False)
    assert has_human_labels(path)
    assert write_sample(path, sample) == "kept"
    assert pd.read_csv(path, dtype=str, keep_default_na=False).loc[0, "labeler_1_resolvable"] == "yes"


def test_labels_are_pending_without_a_file_or_without_adjudication(tmp_path: Path) -> None:
    missing = read_labels(tmp_path / "missing.csv", min_matching=2)
    assert not missing.file_present
    assert missing.workflows["credit"].status == PENDING
    assert missing.share_for("credit") is None
    path = tmp_path / "sample.csv"
    write_sample(path, select_sample(_candidates(), per_workflow=3, seed="s"))
    unlabeled = read_labels(path, min_matching=2)
    assert unlabeled.file_present
    assert unlabeled.workflows["account_inquiry"].items == 3
    assert unlabeled.workflows["account_inquiry"].status == PENDING


def _labeled_file(tmp_path: Path) -> Path:
    path = tmp_path / "sample.csv"
    sample = select_sample(_candidates(), per_workflow=4, seed="s")
    values = {
        "account_inquiry": [("yes", "yes"), ("yes", "yes"), ("no", "yes"), ("unclear", "yes")],
        "dispute": [("yes", "no"), ("yes", "no"), ("maybe", "yes"), ("", "")],
    }
    for workflow, labels in values.items():
        indexes = sample.index[sample["workflow_stratum"] == workflow]
        for index, (resolvable, matches) in zip(indexes, labels, strict=True):
            sample.loc[index, "adjudicated_resolvable"] = resolvable
            sample.loc[index, "adjudicated_matches_workflow"] = matches
            sample.loc[index, "labeler_1_resolvable"] = resolvable or "yes"
            sample.loc[index, "labeler_2_resolvable"] = "yes"
    sample.to_csv(path, index=False)
    return path


def test_labeled_share_counts_only_items_matching_the_workflow(tmp_path: Path) -> None:
    summary = read_labels(_labeled_file(tmp_path), min_matching=3)
    account = summary.workflows["account_inquiry"]
    assert (account.adjudicated, account.matching, account.yes, account.no, account.unclear) == (4, 4, 2, 1, 1)
    assert account.status == "labeled"
    assert account.share == pytest.approx(0.5)  # unclear counts as not automatable
    assert account.double_labeled == 4
    dispute = summary.workflows["dispute"]
    assert (dispute.adjudicated, dispute.matching, dispute.invalid) == (2, 0, 1)
    assert dispute.status.startswith("insufficient matching labels")
    assert summary.share_for("dispute") is None


def test_a_labeling_file_without_the_expected_columns_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("item_id\nLBL-0001\n", encoding="utf-8")
    with pytest.raises(ValueError, match="lacks columns"):
        read_labels(path, min_matching=1)
