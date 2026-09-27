"""Compute the phase 04 evidence from the warehouse: volumes, outcomes, demand patterns, the digital-error
lag, costs, segment baselines, data support, stop conditions, scores, and sensitivity.

The result is a JSON-serializable dictionary; ``render`` turns it into the Markdown reports and ``figures``
into the charts. Every number in the reports comes from here.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from bank_data.analysis import metrics, queries
from bank_data.analysis.config import (
    CRITERIA,
    OTHER,
    SCENARIOS,
    WORKFLOWS,
    CostAssumptions,
    ScoringConfig,
    WorkflowMapping,
)
from bank_data.analysis.labeling import PENDING, LabelSummary
from bank_data.analysis.scoring import (
    Candidate,
    classify_sub_intent,
    harm_inverse,
    order,
    ratio_to_max,
    weight_sensitivity,
    weighted_score,
)
from bank_data.analysis.stats import (
    Interval,
    cramers_v,
    detect_spikes,
    mean_interval,
    proportion_interval,
)

Result = dict[str, Any]
UNMAPPED_LIMIT = 0.05
"""The prompt's stop condition: more than 5% of interaction or complaint volume without a mapping row."""
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
SEGMENT_DIMENSIONS = (("country", "Country"), ("customer_detected_accent", "Detected accent"), ("segment", "Segment"))
LAG_BUCKETS_HOURS = 24
FLAT_PATTERN_RATIO = 1.2
"""A peak-to-trough ratio below this reads as a flat pattern (no peak worth staffing for)."""


@dataclass(frozen=True)
class AnalysisInputs:
    mapping: WorkflowMapping
    scoring: ScoringConfig
    costs: CostAssumptions
    labels: LabelSummary


def _interval(value: Interval) -> Result:
    return {"estimate": value.estimate, "low": value.low, "high": value.high, "n": value.n}


class _Stats:
    """Bootstrap helpers bound to the pre-registered resamples, seed, and confidence."""

    def __init__(self, scoring: ScoringConfig) -> None:
        self.resamples = scoring.statistics.bootstrap_resamples
        self.seed = scoring.statistics.bootstrap_seed
        self.confidence = scoring.statistics.confidence

    def rate(self, values: pd.Series) -> Result:
        known = values.dropna().astype(bool)
        return _interval(
            proportion_interval(
                int(known.sum()), int(known.size), resamples=self.resamples, seed=self.seed, confidence=self.confidence
            )
        )

    def mean(self, values: pd.Series) -> Result:
        array = np.asarray(values.dropna(), dtype=np.float64)
        return _interval(mean_interval(array, resamples=self.resamples, seed=self.seed, confidence=self.confidence))


def _share_table(values: pd.Series) -> list[list[Any]]:
    counts = values.fillna("unknown").astype(str).value_counts()
    total = int(counts.sum())
    return [[str(key), int(count), float(count) / total] for key, count in counts.items()] if total else []


def _column(scenario: str) -> str:
    return f"workflow_{scenario}"


# --------------------------------------------------------------------------------------------- sections


def _mapping_coverage(interactions: pd.DataFrame, complaints: pd.DataFrame, mapping: WorkflowMapping) -> Result:
    reasons = (
        interactions.groupby(
            [interactions["contact_reason"].fillna("(null)"), interactions["workflow_primary"]], dropna=False
        )
        .size()
        .reset_index(name="interactions")
    )
    reason_rows = []
    for _, row in reasons.iterrows():
        mapped = mapping.lookup("contact_reason", str(row["contact_reason"]))
        reason_rows.append(
            {
                "contact_reason": str(row["contact_reason"]),
                "interactions": int(row["interactions"]),
                "workflow": mapped.workflow_id if mapped else None,
                "strict": mapped.strict_workflow_id if mapped else None,
                "alternative": mapped.alternative_workflow_id if mapped else None,
            }
        )
    categories = (
        complaints.assign(subcategory=complaints["subcategory"].fillna(""))
        .groupby(["category", "subcategory"], dropna=False)
        .size()
        .reset_index(name="complaints")
    )
    category_rows = []
    for _, row in categories.iterrows():
        mapped = mapping.lookup("complaint_category", str(row["category"]), str(row["subcategory"]))
        category_rows.append(
            {
                "category": str(row["category"]),
                "subcategory": str(row["subcategory"]),
                "complaints": int(row["complaints"]),
                "workflow": mapped.workflow_id if mapped else None,
                "sub_intent": mapped.sub_intent if mapped else None,
            }
        )
    unmapped_interactions = int(interactions["workflow_primary"].isna().sum())
    unmapped_complaints = int(complaints["workflow_primary"].isna().sum())
    both = interactions.dropna(subset=["workflow_primary", "reason_category_workflow"])
    conflicts = int((both["workflow_primary"] != both["reason_category_workflow"]).sum())
    return {
        "contact_reasons": sorted(reason_rows, key=lambda item: -item["interactions"]),
        "complaint_categories": sorted(category_rows, key=lambda item: (item["category"], item["subcategory"])),
        "unmapped_interactions": unmapped_interactions,
        "unmapped_interaction_share": unmapped_interactions / len(interactions) if len(interactions) else 0.0,
        "unmapped_complaints": unmapped_complaints,
        "unmapped_complaint_share": unmapped_complaints / len(complaints) if len(complaints) else 0.0,
        "unmapped_values": sorted(
            {str(value) for value in interactions.loc[interactions["workflow_primary"].isna(), "contact_reason"]}
            | {
                f"{category} / {subcategory or '(null)'}"
                for category, subcategory in complaints.loc[
                    complaints["workflow_primary"].isna(), ["category", "subcategory"]
                ].itertuples(index=False)
            }
        ),
        "reason_category_conflicts": conflicts,
    }


def _volume(interactions: pd.DataFrame, complaints: pd.DataFrame, scenario: str) -> Result:
    column = _column(scenario)
    total_interactions, total_complaints = len(interactions), len(complaints)
    total = total_interactions + total_complaints
    rows = {}
    for workflow in (*WORKFLOWS, OTHER):
        n_interactions = int((interactions[column] == workflow).sum())
        n_complaints = int((complaints[column] == workflow).sum())
        rows[workflow] = {
            "interactions": n_interactions,
            "complaints": n_complaints,
            "interaction_share": n_interactions / total_interactions if total_interactions else 0.0,
            "complaint_share": n_complaints / total_complaints if total_complaints else 0.0,
            "contact_share": (n_interactions + n_complaints) / total if total else 0.0,
        }
    return rows


def _months(frame: pd.DataFrame, date_column: str) -> pd.Series:
    return pd.to_datetime(frame[date_column]).dt.to_period("M").astype(str)


def _trend(interactions: pd.DataFrame, complaints: pd.DataFrame) -> Result:
    contacts = pd.concat(
        [
            pd.DataFrame(
                {"month": _months(interactions, "process_date"), "workflow": interactions["workflow_primary"]}
            ),
            pd.DataFrame({"month": _months(complaints, "process_date"), "workflow": complaints["workflow_primary"]}),
        ],
        ignore_index=True,
    )
    contacts["workflow"] = contacts["workflow"].fillna("unmapped")
    table = contacts.groupby(["month", "workflow"]).size().unstack(fill_value=0).sort_index()
    months = [str(month) for month in table.index]
    full = months[1:-1] if len(months) > 2 else months
    first, last = full[:12], full[-12:]
    series: Result = {}
    for workflow in (*WORKFLOWS, OTHER):
        counts = table[workflow] if workflow in table.columns else pd.Series(0, index=table.index)
        first_total = int(counts.loc[first].sum()) if first else 0
        last_total = int(counts.loc[last].sum()) if last else 0
        series[workflow] = {
            "monthly": [int(value) for value in counts.to_list()],
            "first_12_full_months": first_total,
            "last_12_full_months": last_total,
            "change": (last_total - first_total) / first_total if first_total else None,
        }
    return {
        "months": months,
        "full_months": full,
        "first_window": [first[0], first[-1]] if first else None,
        "last_window": [last[0], last[-1]] if last else None,
        "workflows": series,
    }


def _surveys_of(surveys: pd.DataFrame, interaction_ids: pd.Series, survey_type: str) -> pd.Series:
    subset = surveys[(surveys["survey_type"] == survey_type) & surveys["interaction_id"].isin(interaction_ids)]
    return subset["main_score"].astype("float64")


def _outcomes(
    stats: _Stats, interactions: pd.DataFrame, surveys: pd.DataFrame, complaints: pd.DataFrame, workflow: str
) -> Result:
    inter = interactions[interactions["workflow_primary"] == workflow]
    comp = complaints[complaints["workflow_primary"] == workflow]
    csat = _surveys_of(surveys, inter["interaction_id"], "CSAT")
    nps = _surveys_of(surveys, inter["interaction_id"], "NPS")
    ces = _surveys_of(surveys, inter["interaction_id"], "CES")
    nps_value = None
    if len(nps):
        nps_value = 100.0 * (float((nps >= 9).mean()) - float((nps <= 6).mean()))
    result: Result = {
        "interactions": len(inter),
        "first_contact_resolution": stats.rate(inter["was_resolved"]),
        "escalation": stats.rate(inter["was_escalated"]),
        "requires_followup": stats.rate(inter["requires_followup"]),
        "handle_time_seconds": stats.mean(inter["duration_seconds"]),
        "wait_time_seconds": stats.mean(inter["wait_time_seconds"]),
        "csat_mean": stats.mean(csat),
        "csat_low_share": stats.rate(csat <= 2) if len(csat) else _interval(Interval.empty()),
        "nps": {"score": nps_value, "n": len(nps), "promoters": int((nps >= 9).sum())},
        "ces_mean": stats.mean(ces),
        "channel_mix": _share_table(inter["channel"]),
        "country_mix": _share_table(inter["country"]),
        "complaints": len(comp),
    }
    if len(comp):
        result.update(
            {
                "complaint_country_mix": _share_table(comp["country"]),
                "complaint_channel_mix": _share_table(comp["reception_channel"]),
                "case_type_mix": _share_table(comp["case_type"]),
                "status_mix": _share_table(comp["status"]),
                "sla_breach": stats.rate(comp["sla_breached"]),
                "resolution_days": stats.mean(comp["resolution_days"]),
                "repeat_complainer": stats.rate(comp["is_repeat_complainer"]),
                "compensation_granted_share": float(comp["compensation_granted"].notna().mean()),
                "claimed_amount_present_share": float(comp["claimed_amount"].notna().mean()),
            }
        )
    return result


def _local_times(interactions: pd.DataFrame) -> pd.Series:
    offsets = interactions["country"].map(queries.COUNTRY_UTC_OFFSET_HOURS).astype("float64")
    stamps = pd.to_datetime(interactions["interaction_date"])
    return stamps + pd.to_timedelta(offsets.fillna(0.0), unit="h")


def _patterns(interactions: pd.DataFrame, complaints: pd.DataFrame, scoring: ScoringConfig) -> Result:
    local = _local_times(interactions)
    result: Result = {"workflows": {}}
    config = scoring.demand_patterns
    for workflow in WORKFLOWS:
        mask = interactions["workflow_primary"] == workflow
        stamps = local[mask]
        hours = stamps.dt.hour.value_counts().reindex(range(24), fill_value=0)
        weekdays = stamps.dt.dayofweek.value_counts().reindex(range(7), fill_value=0)
        months = stamps.dt.month.value_counts().reindex(range(1, 13), fill_value=0)
        daily = pd.concat(
            [
                interactions.loc[mask, "process_date"],
                complaints.loc[complaints["workflow_primary"] == workflow, "process_date"],
            ]
        )
        counts = pd.to_datetime(daily).dt.date.value_counts().sort_index()
        spikes = detect_spikes(
            list(counts.index),
            [int(value) for value in counts.to_list()],
            window=config.spike_window_days,
            threshold=config.spike_robust_z,
        )
        result["workflows"][workflow] = {
            "hour_of_day": [int(value) for value in hours.to_list()],
            "hour_peak_to_trough": float(hours.max() / hours.min()) if hours.min() > 0 else None,
            "weekday_peak_to_trough": float(weekdays.max() / weekdays.min()) if weekdays.min() > 0 else None,
            "weekday": [int(value) for value in weekdays.to_list()],
            "month_of_year": [int(value) for value in months.to_list()],
            "country": _share_table(interactions.loc[mask, "country"]),
            "channel": _share_table(interactions.loc[mask, "channel"]),
            "days": len(counts),
            "daily_mean": float(counts.mean()) if len(counts) else None,
            "spikes": len(spikes),
            "top_spikes": [
                {
                    "day": spike.day.isoformat(),
                    "volume": spike.volume,
                    "baseline": spike.baseline,
                    "robust_z": spike.robust_z,
                }
                for spike in sorted(spikes, key=lambda item: -item.robust_z)[:5]
            ],
        }
    return result


def _lag(stats: _Stats, frame: pd.DataFrame, window_hours: int) -> Result:
    result: Result = {"window_hours": window_hours}
    for label, mask in (("error", frame["is_error"]), ("baseline", ~frame["is_error"])):
        subset = frame[mask]
        contacted = subset["hours_to_contact"].notna()
        histogram = (
            np.histogram(subset["hours_to_contact"].dropna(), bins=LAG_BUCKETS_HOURS, range=(0, window_hours))[0]
            if len(subset)
            else np.zeros(LAG_BUCKETS_HOURS, dtype=int)
        )
        result[label] = {
            "events": len(subset),
            "contact_within_window": stats.rate(contacted) if len(subset) else _interval(Interval.empty()),
            "histogram": [int(value) for value in histogram],
            "contact_workflows": _share_table(subset.loc[contacted, "contact_workflow"]),
        }
    error_rate = result["error"]["contact_within_window"]["estimate"]
    baseline_rate = result["baseline"]["contact_within_window"]["estimate"]
    result["rate_ratio"] = error_rate / baseline_rate if error_rate is not None and baseline_rate else None
    errors = frame[frame["is_error"]]
    pages = []
    for page, group in errors.groupby(errors["page_url"].fillna("(none)")):
        pages.append([str(page), len(group), float(group["hours_to_contact"].notna().mean())])
    result["error_pages"] = sorted(pages, key=lambda item: -item[1])
    return result


def _costs(
    interactions: pd.DataFrame, costs: CostAssumptions, labels: LabelSummary, proxies: Mapping[str, float | None]
) -> Result:
    dates = pd.to_datetime(interactions["process_date"])
    last_day = dates.max() if len(dates) else None
    recent = dates > (last_day - pd.Timedelta(days=365)) if last_day is not None else dates.notna()
    result: Result = {"currency": costs.currency, "workflows": {}}
    for workflow in WORKFLOWS:
        mask = interactions["workflow_primary"] == workflow
        subset = interactions[mask]
        annual_volume = int((mask & recent).sum())
        resolved = int(subset["was_resolved"].fillna(False).astype(bool).sum())
        known_minutes = subset["duration_seconds"].dropna().astype("float64") / 60.0
        scenarios: Result = {}
        for multiplier in costs.sensitivity_multipliers:
            per_row = metrics.handle_costs(subset, costs, multiplier=multiplier)
            per_contact = metrics.cost_per_contact(per_row)
            total = metrics.estimated_total_cost(per_row, len(subset))
            annual = per_contact * annual_volume if per_contact is not None else None
            proxy = proxies.get(workflow)
            share = labels.share_for(workflow)
            scenarios[f"{multiplier:g}"] = {
                "cost_per_contact": per_contact,
                "total_cost": total,
                "cost_per_resolved_contact": metrics.cost_per_resolved_contact(total, resolved),
                "annual_handle_cost": annual,
                "addressable_label_based": annual * share if annual is not None and share is not None else PENDING,
                "addressable_ceiling": annual,
                "addressable_proxy": annual * proxy if annual is not None and proxy is not None else None,
            }
        result["workflows"][workflow] = {
            "contacts": len(subset),
            "contacts_with_duration": int(known_minutes.size),
            "mean_handle_minutes": float(known_minutes.mean()) if known_minutes.size else None,
            "resolved": resolved,
            "annual_volume": annual_volume,
            "scenarios": scenarios,
        }
    result["annual_window_end"] = last_day.date().isoformat() if last_day is not None else None
    return result


def _segments(interactions: pd.DataFrame, surveys: pd.DataFrame, scoring: ScoringConfig) -> Result:
    csat = surveys[surveys["survey_type"] == "CSAT"][["interaction_id", "main_score"]]
    joined = interactions.merge(csat, on="interaction_id", how="left")
    small_interactions = scoring.statistics.small_cell_interactions
    small_surveys = scoring.statistics.small_cell_surveys
    groups = {"all_in_scope": joined[joined["workflow_primary"].isin(WORKFLOWS)]}
    groups.update({workflow: joined[joined["workflow_primary"] == workflow] for workflow in WORKFLOWS})
    result: Result = {}
    for column, _title in SEGMENT_DIMENSIONS:
        rows = []
        for group, frame in groups.items():
            keys = frame[column].fillna("unknown").astype(str)
            for value, cell in frame.groupby(keys):
                n = len(cell)
                n_csat = int(cell["main_score"].notna().sum())
                rows.append(
                    {
                        "group": group,
                        "value": str(value),
                        "interactions": n,
                        "first_contact_resolution": metrics.first_contact_resolution_rate(cell),
                        "escalation": metrics.escalation_rate(cell),
                        "csat_mean": float(cell["main_score"].mean()) if n_csat else None,
                        "csat_surveys": n_csat,
                        "small_cell": n < small_interactions or n_csat < small_surveys,
                    }
                )
        result[column] = rows
    return result


def _transcripts(connection: duckdb.DuckDBPyConnection) -> Result:
    openings = queries.transcript_openings(connection)
    table = openings.pivot_table(index="contact_reason", columns="opening", values="transcripts", fill_value=0)
    return {
        "facts": queries.transcript_facts(connection),
        "detected_intents": queries.detected_intent_values(connection),
        "openings": [
            [str(reason), str(opening), int(count)]
            for reason, opening, count in openings[["contact_reason", "opening", "transcripts"]].itertuples(index=False)
        ],
        "cramers_v_reason_by_opening": cramers_v(table.to_numpy().astype(int).tolist()) if table.size else None,
    }


def _stop_conditions(counts: Mapping[str, int], coverage: Result) -> Result:
    checks = []

    def check(name: str, passed: bool, detail: str, workflows: str) -> None:
        checks.append({"check": name, "passed": passed, "detail": detail, "workflows": workflows})

    check(
        "account_inquiry read path",
        counts["payment_or_transfer_transactions"] > 0,
        f"{counts['payment_or_transfer_transactions']:,} payment or transfer transactions",
        "account_inquiry",
    )
    check(
        "card_support read path",
        counts["card_products"] > 0,
        f"{counts['card_products']:,} card products",
        "card_support",
    )
    check(
        "dispute read path",
        counts["purchase_transactions"] > 0,
        f"{counts['purchase_transactions']:,} purchases",
        "dispute",
    )
    check(
        "credit read path",
        counts["credit_products_with_limit_or_rate"] > 0,
        f"{counts['credit_products_with_limit_or_rate']:,} credit products with a limit or an interest rate",
        "credit",
    )
    interaction_share = float(coverage["unmapped_interaction_share"])
    complaint_share = float(coverage["unmapped_complaint_share"])
    check(
        "mapped volume",
        interaction_share <= UNMAPPED_LIMIT and complaint_share <= UNMAPPED_LIMIT,
        f"unmapped: {interaction_share:.2%} of interactions, {complaint_share:.2%} of complaints (limit 5%)",
        "all",
    )
    customers = counts["customers"] or 1
    credit_products = counts["credit_products"] or 1
    score_share = counts["customers_with_credit_score"] / customers
    income_share = counts["customers_with_income"] / customers
    dpd_share = counts["credit_products_with_days_past_due"] / credit_products
    check(
        "credit profile columns",
        score_share >= 0.5 and income_share >= 0.5 and dpd_share >= 0.5,
        f"credit_score {score_share:.1%} and income {income_share:.1%} of customers; "
        f"days_past_due {dpd_share:.1%} of credit products",
        "credit",
    )
    return {
        "counts": dict(counts),
        "checks": checks,
        "blocked": [item["check"] for item in checks if not item["passed"]],
    }


# --------------------------------------------------------------------------------------------- scoring


def _criteria(
    interactions: pd.DataFrame,
    surveys: pd.DataFrame,
    complaints: pd.DataFrame,
    scenario: str,
    inputs: AnalysisInputs,
    data_support: Mapping[str, float],
) -> Result:
    column = _column(scenario)
    total = len(interactions) + len(complaints)
    csat = surveys[surveys["survey_type"] == "CSAT"]
    raw: Result = {}
    handle = {}
    for workflow in WORKFLOWS:
        inter = interactions[interactions[column] == workflow]
        handle[workflow] = float(inter["duration_seconds"].mean()) if inter["duration_seconds"].notna().any() else 0.0
    top_handle = max(handle.values(), default=0.0)
    for workflow in WORKFLOWS:
        inter = interactions[interactions[column] == workflow]
        comp = complaints[complaints[column] == workflow]
        csat_scores = csat[csat["interaction_id"].isin(inter["interaction_id"])]["main_score"]
        fcr = metrics.first_contact_resolution_rate(inter)
        escalation = metrics.escalation_rate(inter)
        sla = metrics.sla_breach_rate(comp) if len(comp) else None
        components = {
            "unresolved_first_contact": 1.0 - fcr if fcr is not None else 0.0,
            "escalated": escalation if escalation is not None else 0.0,
            "low_csat": float((csat_scores <= 2).mean()) if len(csat_scores) else 0.0,
            "relative_handle_time": handle[workflow] / top_handle if top_handle > 0 else 0.0,
            "complaint_sla_breach": sla if sla is not None else 0.0,
        }
        proxy = metrics.simple_contact_rate(inter)
        label_share = inputs.labels.share_for(workflow)
        raw[workflow] = {
            "interactions": len(inter),
            "complaints": len(comp),
            "demand_raw": (len(inter) + len(comp)) / total if total else 0.0,
            "pain_components": components,
            "pain_raw": sum(components.values()) / len(components),
            "automatable_source": "human labels" if label_share is not None else "proxy",
            "automatable_proxy": proxy,
            "automatable_share": label_share if label_share is not None else (proxy if proxy is not None else 0.0),
        }
    demand = ratio_to_max({workflow: raw[workflow]["demand_raw"] for workflow in WORKFLOWS})
    pain = ratio_to_max({workflow: raw[workflow]["pain_raw"] for workflow in WORKFLOWS})
    scoring = inputs.scoring
    criteria: Result = {}
    for workflow in WORKFLOWS:
        points = sum(1 for flag in scoring.demo_depth[workflow].values() if flag)
        criteria[workflow] = {
            "demand": demand[workflow],
            "pain": pain[workflow],
            "automatable_share": float(raw[workflow]["automatable_share"]),
            "harm_inverse": harm_inverse(scoring.harm[workflow].score),
            "data_support": float(data_support[workflow]),
            "demo_depth": points / len(scoring.demo_depth[workflow]),
        }
    scores = {workflow: weighted_score(criteria[workflow], scoring.weights) for workflow in WORKFLOWS}
    ranking = order(
        [Candidate(w, scores[w], criteria[w]["data_support"], scoring.harm[w].score) for w in WORKFLOWS],
        tie_margin=scoring.prioritization.tie_margin_points,
    )
    return {"raw": raw, "criteria": criteria, "scores": scores, "ranking": ranking}


def _sub_intents(primary: Result, item_values: Mapping[str, float], inputs: AnalysisInputs) -> Result:
    scoring = inputs.scoring
    rows: Result = {}
    for name, spec in scoring.sub_intents.items():
        workflow_criteria = primary["criteria"][spec.workflow]
        support = sum(item_values[item] for item in spec.data_support) / len(spec.data_support)
        criteria = {
            "demand": workflow_criteria["demand"],
            "pain": workflow_criteria["pain"],
            "automatable_share": workflow_criteria["automatable_share"] * spec.capability,
            "harm_inverse": harm_inverse(spec.harm),
            "data_support": support,
            "demo_depth": workflow_criteria["demo_depth"],
        }
        rows[name] = {
            "workflow": spec.workflow,
            "capability": spec.capability,
            "harm": spec.harm,
            "data_support_items": list(spec.data_support),
            "criteria": criteria,
            "score": weighted_score(criteria, scoring.weights),
            "class": classify_sub_intent(
                spec.capability, support, threshold=scoring.prioritization.subintent_data_support_threshold
            ),
        }
    for workflow in WORKFLOWS:
        members = [name for name, row in rows.items() if row["workflow"] == workflow and row["class"] == "automate"]
        for position, name in enumerate(sorted(members, key=lambda item: (-rows[item]["score"], item)), start=1):
            rows[name]["automation_order"] = position
    return rows


def _weight_sensitivity(primary: Result, inputs: AnalysisInputs) -> Result:
    scoring = inputs.scoring
    variants = weight_sensitivity(
        primary["criteria"],
        scoring.weights,
        delta=scoring.sensitivity.delta_points,
        harm={workflow: scoring.harm[workflow].score for workflow in WORKFLOWS},
        tie_margin=scoring.prioritization.tie_margin_points,
    )
    base = primary["ranking"]
    ranges = {}
    for workflow in WORKFLOWS:
        scores = [variant.scores[workflow] for variant in variants]
        ranks = [variant.ranking.index(workflow) + 1 for variant in variants]
        ranges[workflow] = {
            "score_min": min(scores),
            "score_max": max(scores),
            "rank_min": min(ranks),
            "rank_max": max(ranks),
        }
    return {
        "variants": [
            {
                "label": variant.label,
                "scores": variant.scores,
                "ranking": variant.ranking,
                "changed": variant.ranking != base,
            }
            for variant in variants
        ],
        "changed_variants": sum(1 for variant in variants if variant.ranking != base),
        "ranges": ranges,
    }


def _labels(labels: LabelSummary) -> Result:
    return {
        "file_present": labels.file_present,
        "workflows": {
            workflow: {
                "items": item.items,
                "adjudicated": item.adjudicated,
                "matching": item.matching,
                "yes": item.yes,
                "no": item.no,
                "unclear": item.unclear,
                "invalid": item.invalid,
                "double_labeled": item.double_labeled,
                "kappa_resolvable": item.kappa_resolvable,
                "status": item.status,
                "share": item.share,
            }
            for workflow, item in labels.workflows.items()
        },
    }


def compute(connection: duckdb.DuckDBPyConnection, inputs: AnalysisInputs) -> Result:
    """Every section of the evidence, in one dictionary."""
    queries.register_mapping(connection, inputs.mapping)
    stats = _Stats(inputs.scoring)
    interactions = queries.interactions(connection)
    surveys = queries.surveys(connection)
    complaints = queries.complaints(connection)
    item_values_raw = queries.data_support_values(connection, inputs.scoring.items_in_use())
    item_values = {name: (value if value is not None else 0.0) for name, value in item_values_raw.items()}
    workflow_support = {
        workflow: sum(item_values[item] for item in items) / len(items)
        for workflow, items in inputs.scoring.data_support.items()
    }
    coverage = _mapping_coverage(interactions, complaints, inputs.mapping)
    scenarios = {
        scenario: _criteria(interactions, surveys, complaints, scenario, inputs, workflow_support)
        for scenario in SCENARIOS
    }
    primary = scenarios["primary"]
    proxies = {workflow: primary["raw"][workflow]["automatable_proxy"] for workflow in WORKFLOWS}
    patterns_config = inputs.scoring.demand_patterns
    lag_frame = queries.error_contact_lag(
        connection,
        window_hours=patterns_config.error_contact_window_hours,
        baseline_share=patterns_config.baseline_sample_share,
        baseline_seed=patterns_config.baseline_seed,
    )
    dates = pd.to_datetime(interactions["process_date"])
    return {
        "dataset": {
            "interactions": len(interactions),
            "complaints": len(complaints),
            "surveys": len(surveys),
            "first_day": dates.min().date().isoformat() if len(dates) else None,
            "last_day": dates.max().date().isoformat() if len(dates) else None,
        },
        "mapping": coverage,
        "volume": {scenario: _volume(interactions, complaints, scenario) for scenario in SCENARIOS},
        "trend": _trend(interactions, complaints),
        "outcomes": {workflow: _outcomes(stats, interactions, surveys, complaints, workflow) for workflow in WORKFLOWS},
        "automatable": {
            workflow: {
                "proxy": stats.rate(_simple_flags(interactions[interactions["workflow_primary"] == workflow])),
                "label_status": inputs.labels.workflows[workflow].status,
                "label_share": inputs.labels.share_for(workflow),
            }
            for workflow in WORKFLOWS
        },
        "labels": _labels(inputs.labels),
        "patterns": _patterns(interactions, complaints, inputs.scoring),
        "lag": _lag(stats, lag_frame, patterns_config.error_contact_window_hours),
        "costs": _costs(interactions, inputs.costs, inputs.labels, proxies),
        "segments": _segments(interactions, surveys, inputs.scoring),
        "data_support": {
            "items": {
                item.name: {"description": item.description, "value": item_values_raw.get(item.name)}
                for item in queries.DATA_SUPPORT_ITEMS
                if item.name in item_values_raw
            },
            "workflows": workflow_support,
        },
        "transcripts": _transcripts(connection),
        "stop_conditions": _stop_conditions(queries.stop_condition_counts(connection), coverage),
        "scores": {
            "weights": dict(inputs.scoring.weights),
            "criteria_order": list(CRITERIA),
            "scenarios": scenarios,
            "sensitivity": _weight_sensitivity(primary, inputs),
            "sub_intents": _sub_intents(primary, item_values, inputs),
        },
    }


def _simple_flags(interactions: pd.DataFrame) -> pd.Series:
    usable = interactions.dropna(subset=["was_resolved", "was_escalated", "requires_followup"])
    return (
        usable["was_resolved"].astype(bool)
        & ~usable["was_escalated"].astype(bool)
        & ~usable["requires_followup"].astype(bool)
    )
