"""The router benchmark against a hosted language model: orchestration and ``docs/evaluation/router-llm.md``.

``benchmark`` replays the recorded calls (no key needed), builds every system on dev and test, fixes the model
thresholds and the decision on dev (the rule pre-registered in ``docs/plans/router-llm.md``), scores test with the
shared router evaluation and its seed-group bootstrap intervals, and returns one JSON-ready dictionary. ``render``
turns it into Markdown; the hand-written decision between the markers survives a regeneration.
"""

import asyncio
import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from typing import Any, Final

import numpy as np
from numpy.typing import NDArray

from bank_agent.adapters.llm.prices import PriceTable
from bank_agent.adapters.models.keyword_router import THRESHOLD as KEYWORD_THRESHOLD
from bank_agent.adapters.models.keyword_router import KeywordIntentRouter
from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_agent.adapters.models.tfidf_router import TfidfIntentRouter
from bank_agent.bootstrap.settings import DEFAULT_PRICES_FILE
from bank_agent.domain.workflow import Intent
from bank_ml.common.metrics import Interval
from bank_ml.common.paths import EVALUATIONS_DIR
from bank_ml.common.reports import generated_now, git_sha, pct, table
from bank_ml.router.augment import Item
from bank_ml.router.dataset import RouterDataset
from bank_ml.router.evaluate import (
    HIGH_STAKES,
    WORKFLOW_LABELS,
    Scored,
    calibration,
    interval,
    per_intent,
    slices,
    summary,
    workflow_confusion,
)
from bank_ml.router.models import TARGET_RISK, Predictions
from bank_ml.router.report import ci
from bank_ml.router.zero_shot import (
    MAX_OUTPUT_TOKENS,
    PROMPT,
    TEMPERATURE,
    LlmPrediction,
    SystemRun,
    cascade_run,
    choose_llm_threshold,
    classical_run,
    classify_items,
    out_of_scope_confident_misroutes,
    paired_macro_f1_difference,
    timed_route,
    usage,
    write_misroutes,
    zero_shot_run,
)

DEFAULT_MODELS: Final = ("azure/gpt-4.1-mini", "azure/gpt-4o")
SPLITS: Final = ("dev", "test")
TFIDF_REFERENCE: Final = "986872f0284f"
KEYWORD: Final = "keyword@1"
DECISION_BEGIN: Final = "<!-- decision:begin (hand-written; kept when the report is regenerated) -->"
DECISION_END: Final = "<!-- decision:end -->"
PENDING_DECISION: Final = "No decision has been written yet. A person writes it here after reading the dev section."
AUDIT_CONFIDENCE: Final = 0.9
AUDIT_LIMIT: Final = 20
Replay = Callable[[Sequence[str], Sequence[Item], Path], dict[str, list[LlmPrediction]]]


@dataclass(frozen=True)
class DecisionRule:
    """The rule pre-registered in ``docs/plans/router-llm.md`` for recommending a flagged cascade trial."""

    min_gain: float = 0.05
    recall_tolerance: float = 0.02
    extra_write_misroutes: int = 1
    max_model_share: float = 0.60
    max_model_call_p95_ms: float = 2000.0
    max_cost_usd_per_1000: Decimal = Decimal("1.00")


RULE: Final = DecisionRule()


def tfidf_name(reference: str) -> str:
    return f"tfidf@{reference}"


def zero_shot_name(model_id: str) -> str:
    return f"zero-shot {model_id}"


def cascade_name(base: str, model_id: str) -> str:
    return f"{base} then {model_id}"


def _subset(predictions: Predictions, mask: NDArray[np.bool_]) -> Predictions:
    intents = [intent for intent, keep in zip(predictions.intents, mask, strict=True) if keep]
    return Predictions(intents, predictions.confidence[mask], predictions.below_threshold[mask])


def _languages(items: Sequence[Item]) -> list[str]:
    return sorted({item.language for item in items})


@dataclass(frozen=True)
class SplitSystems:
    items: list[Item]
    runs: dict[str, SystemRun]
    scored: dict[str, Scored]


def _criteria(
    rule: DecisionRule, cascade: dict[str, Any], base: dict[str, Any], gain: Interval
) -> list[dict[str, Any]]:
    recall, base_recall = cascade["high_stakes_recall_mean"], base["high_stakes_recall_mean"]
    writes, base_writes = cascade["write_misroutes"], base["write_misroutes"]
    share = cascade["usage"]["model_share"]
    p95 = cascade["usage"]["model_call_ms_p95"] or 0.0
    cost = cascade["usage"]["cost_usd_per_1000"]
    return [
        {
            "criterion": f"Macro-F1 gain over TF-IDF above {rule.min_gain:.2f}, paired 95% lower bound above 0",
            "value": f"{gain.estimate:+.3f} [{gain.low:+.3f}, {gain.high:+.3f}]",
            "met": gain.estimate > rule.min_gain and gain.low > 0,
        },
        {
            "criterion": f"High-stakes recall mean at most {rule.recall_tolerance:.2f} below TF-IDF",
            "value": f"{recall:.3f} against {base_recall:.3f}",
            "met": recall >= base_recall - rule.recall_tolerance,
        },
        {
            "criterion": f"Confident write-intent misroutes at most TF-IDF's plus {rule.extra_write_misroutes}",
            "value": f"{writes} against {base_writes}",
            "met": writes <= base_writes + rule.extra_write_misroutes,
        },
        {
            "criterion": f"Model called on at most {pct(rule.max_model_share, 0)} of messages",
            "value": pct(share),
            "met": share <= rule.max_model_share,
        },
        {
            "criterion": f"Model call p95 at most {rule.max_model_call_p95_ms:,.0f} ms",
            "value": f"{p95:,.0f} ms",
            "met": p95 <= rule.max_model_call_p95_ms,
        },
        {
            "criterion": f"Cost at most {rule.max_cost_usd_per_1000} USD per 1,000 messages (list price)",
            "value": f"{cost} USD" if cost is not None else "no price",
            "met": cost is not None and Decimal(cost) <= rule.max_cost_usd_per_1000,
        },
    ]


def decide(
    dev: dict[str, dict[str, Any]],
    scored: dict[str, Scored],
    models: Sequence[str],
    base: str,
    rule: DecisionRule = RULE,
) -> dict[str, Any]:
    """Apply the pre-registered rule on dev to every ``base then model`` cascade and pick at most one model."""
    candidates: dict[str, Any] = {}
    for model_id in models:
        name = cascade_name(base, model_id)
        gain = paired_macro_f1_difference(scored[name], scored[base])
        rows = _criteria(rule, dev[name], dev[base], gain)
        candidates[model_id] = {"system": name, "criteria": rows, "qualifies": all(row["met"] for row in rows)}
    qualifying = [model_id for model_id in models if candidates[model_id]["qualifies"]]
    chosen: str | None = None
    comparison: dict[str, Any] | None = None
    if len(qualifying) == 1:
        chosen = qualifying[0]
    elif len(qualifying) > 1:
        first, second = qualifying[0], qualifying[1]
        difference = paired_macro_f1_difference(scored[cascade_name(base, first)], scored[cascade_name(base, second)])
        comparison = {"first": first, "second": second, "difference": interval(difference)}
        if difference.low <= 0 <= difference.high:
            chosen = min(qualifying, key=lambda m: Decimal(dev[cascade_name(base, m)]["usage"]["cost_usd_per_1000"]))
        else:
            chosen = first if difference.estimate > 0 else second
    return {"candidates": candidates, "qualifying": qualifying, "chosen": chosen, "model_comparison": comparison}


def _system_metrics(items: Sequence[Item], run: SystemRun, prices: PriceTable) -> dict[str, Any]:
    return {
        "usage": usage(run, prices),
        "write_misroutes": write_misroutes(items, run),
        "out_of_scope_confident_misroutes": out_of_scope_confident_misroutes(items, run),
        "out_of_scope_items": sum(item.intent is Intent.UNSUPPORTED for item in items),
    }


def _test_metrics(scored: Scored, *, detailed: bool) -> dict[str, Any]:
    """The summary and the out-of-scope recall for every system; per intent, language, dialect, workflow confusion,
    and reliability only where the report shows them (the keyword cascades are a summary-only reference)."""
    out_of_scope = np.array([item.intent is Intent.UNSUPPORTED for item in scored.items], dtype=bool)
    metrics: dict[str, Any] = {
        **summary(scored),
        "out_of_scope_recall": interval(scored.accuracy(out_of_scope)) if out_of_scope.any() else None,
    }
    if detailed:
        metrics |= {
            "per_intent": per_intent(scored),
            "by_language": slices(scored, lambda item: item.language),
            "by_locale": slices(scored, lambda item: item.locale),
            "workflow_confusion": workflow_confusion(scored),
            "calibration": calibration(scored),
        }
    return metrics


def _confusion_by_language(items: Sequence[Item], run: SystemRun) -> dict[str, list[list[int]]]:
    result = {}
    for language in _languages(items):
        mask = np.array([item.language == language for item in items], dtype=bool)
        chosen = [item for item, keep in zip(items, mask, strict=True) if keep]
        result[language] = workflow_confusion(Scored(f"{run.name}:{language}", chosen, _subset(run.predictions, mask)))
    return result


def _regions(split: SplitSystems, base: str, systems: Sequence[str]) -> dict[str, Any]:
    """Accuracy of each system where ``base`` acts (at or above its threshold) and where it abstains."""
    below = split.runs[base].predictions.below_threshold
    regions: dict[str, Any] = {}
    for label, mask in (("acts", ~below), ("abstains", below)):
        regions[label] = {
            "items": int(mask.sum()),
            "accuracy": {name: interval(split.scored[name].accuracy(mask)) for name in systems if mask.any()},
        }
    return regions


def _audit(items: Sequence[Item], llm: dict[str, list[LlmPrediction]]) -> list[dict[str, Any]]:
    """Canonical test seeds where every model agrees at high confidence and disagrees with the gold label."""
    rows = []
    models = list(llm)
    for position, item in enumerate(items):
        if item.augmentation != "canonical":
            continue
        predictions = [llm[model][position] for model in models]
        labels = {prediction.intent for prediction in predictions}
        if (
            len(labels) == 1
            and not predictions[0].failed
            and predictions[0].intent is not item.intent
            and min(prediction.confidence for prediction in predictions) >= AUDIT_CONFIDENCE
        ):
            rows.append(
                {
                    "item_id": item.item_id,
                    "text": item.text,
                    "locale": item.locale,
                    "gold": item.intent.value,
                    "models": predictions[0].intent.value,
                    "confidence": min(prediction.confidence for prediction in predictions),
                }
            )
    return sorted(rows, key=lambda row: (-float(row["confidence"]), str(row["item_id"])))[:AUDIT_LIMIT]


def _prompt_digest() -> str:
    path = files("bank_agent.prompts") / PROMPT.prompt_id / f"{PROMPT.version}.md"
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def replay_cassettes(
    models: Sequence[str], items: Sequence[Item], cassette_dir: Path
) -> dict[str, list[LlmPrediction]]:
    """Every model's replies to ``items``, replayed from the cassettes (a missing one stops the run)."""
    replayed: dict[str, list[LlmPrediction]] = {}
    for model_id in models:
        run = asyncio.run(classify_items(model_id, items, cassette_dir))
        replayed[model_id] = run.predictions
    return replayed


def benchmark(
    dataset: RouterDataset,
    models: Sequence[str],
    store: FilesystemModelStore,
    tfidf_reference: str,
    cassette_dir: Path,
    *,
    prices: PriceTable | None = None,
    replay: Replay = replay_cassettes,
) -> dict[str, Any]:
    prices = prices or PriceTable.from_yaml(DEFAULT_PRICES_FILE)
    resolved = store.registry.resolve("router:tfidf", tfidf_reference)
    if resolved.metadata.get("dataset_hash") != dataset.content_hash:
        raise ValueError(f"{resolved.ref} was trained on another corpus; run bank-ml router train again")
    tfidf_router = TfidfIntentRouter.load(resolved)
    tfidf = tfidf_name(resolved.ref.version)
    items_by_split = {name: dataset.split(name) for name in SPLITS}
    every = [item for name in SPLITS for item in items_by_split[name]]
    replayed = replay(models, every, cassette_dir)
    llm: dict[str, dict[str, list[LlmPrediction]]] = {}
    offset = 0
    for name in SPLITS:
        size = len(items_by_split[name])
        llm[name] = {model_id: replayed[model_id][offset : offset + size] for model_id in models}
        offset += size
    classical: dict[str, dict[str, SystemRun]] = {}
    for name in SPLITS:
        items = items_by_split[name]
        keyword_predictions, keyword_latency = timed_route(KeywordIntentRouter(), items)
        tfidf_predictions, tfidf_latency = timed_route(tfidf_router, items)
        classical[name] = {
            KEYWORD: classical_run(KEYWORD, keyword_predictions, keyword_latency),
            tfidf: classical_run(tfidf, tfidf_predictions, tfidf_latency),
        }
    dev_items = items_by_split["dev"]
    thresholds: dict[str, Any] = {}
    for model_id in models:
        dev_llm = llm["dev"][model_id]
        thresholds[zero_shot_name(model_id)] = choose_llm_threshold(dev_items, dev_llm).__dict__
        for base in (tfidf, KEYWORD):
            handed = classical["dev"][base].predictions.below_threshold
            thresholds[cascade_name(base, model_id)] = choose_llm_threshold(dev_items, dev_llm, handed).__dict__
    splits: dict[str, SplitSystems] = {}
    for name in SPLITS:
        runs = dict(classical[name])
        for model_id in models:
            predictions = llm[name][model_id]
            zs = zero_shot_name(model_id)
            runs[zs] = zero_shot_run(zs, model_id, predictions, thresholds[zs]["threshold"])
            for base in (tfidf, KEYWORD):
                cascade = cascade_name(base, model_id)
                runs[cascade] = cascade_run(
                    cascade, classical[name][base], model_id, predictions, thresholds[cascade]["threshold"]
                )
        items = items_by_split[name]
        scored = {system: Scored(f"{name}:{system}", items, run.predictions) for system, run in runs.items()}
        splits[name] = SplitSystems(items, runs, scored)
    dev: dict[str, dict[str, Any]] = {}
    systems: dict[str, Any] = {}
    for system, run in splits["dev"].runs.items():
        scored_dev = splits["dev"].scored[system]
        dev[system] = {**summary(scored_dev), **_system_metrics(dev_items, run, prices)}
    test_items = items_by_split["test"]
    for system, run in splits["test"].runs.items():
        scored_test = splits["test"].scored[system]
        test = {
            **_test_metrics(scored_test, detailed=not system.startswith(f"{KEYWORD} then ")),
            **_system_metrics(test_items, run, prices),
            "workflow_confusion_by_language": _confusion_by_language(test_items, run),
        }
        systems[system] = {"dev": dev[system], "test": test, "model_id": run.model_id}
    decision = decide(dev, splits["dev"].scored, models, tfidf)
    test_gains = {
        system: interval(paired_macro_f1_difference(splits["test"].scored[system], splits["test"].scored[tfidf]))
        for system in splits["test"].runs
        if system != tfidf
    }
    model_systems = [zero_shot_name(model_id) for model_id in models]
    return {
        "generated_at": generated_now().isoformat(),
        "git_sha": git_sha(),
        "dataset": {
            "version": dataset.card.version,
            "hash": dataset.content_hash,
            "rows_per_split": dict(dataset.card.rows_per_split),
            "seed_groups": {name: len({item.group_id for item in items_by_split[name]}) for name in SPLITS},
        },
        "prompt": {
            "ref": str(PROMPT),
            "sha256_12": _prompt_digest(),
            "temperature": TEMPERATURE,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        },
        "models": list(models),
        "tfidf": {"ref": str(resolved.ref), "threshold": tfidf_router.threshold},
        "keyword": {"ref": f"router:{KEYWORD}", "threshold": KEYWORD_THRESHOLD},
        "cassette_dir": cassette_dir.name,
        "target_risk": TARGET_RISK,
        "thresholds": thresholds,
        "rule": {key: str(value) for key, value in RULE.__dict__.items()},
        "decision": decision,
        "systems": systems,
        "test_gain_over_tfidf": test_gains,
        "regions": {
            "tfidf": _regions(splits["test"], tfidf, [tfidf, *model_systems]),
            "keyword": _regions(splits["test"], KEYWORD, [KEYWORD, *model_systems]),
        },
        "audit": _audit(test_items, llm["test"]),
        "order": {"tfidf": tfidf, "keyword": KEYWORD, "zero_shot": model_systems},
    }


# --- rendering -------------------------------------------------------------------------------------------------


def _cost(value: str | None) -> str:
    return "no price" if value is None else f"{Decimal(value):.4f}"


def _ms(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:,.0f}" if value >= 10 else f"{value:.2f}"


def _header(result: dict[str, Any]) -> list[str]:
    dataset = result["dataset"]
    prompt = result["prompt"]
    groups = dataset["seed_groups"]
    rows = dataset["rows_per_split"]
    return [
        "# Router: classical routers against a hosted language model",
        "",
        f"Generated {result['generated_at']} from commit `{result['git_sha']}` by `bank-ml router zero-shot`. "
        "Every section except the decision is generated; do not edit it by hand. Rerun "
        "`uv run --frozen bank-ml router zero-shot`: it replays the committed cassettes, so no key is needed.",
        "",
        "Inputs:",
        "",
        f"- Dataset `{dataset['version']}`, content hash `{dataset['hash'][:16]}`: dev {rows['dev']} items "
        f"({groups['dev']} seed groups), test {rows['test']} items ({groups['test']} seed groups). All text is "
        "synthetic (team-authored seeds in es-MX, es-CO, es-AR, and pt-BR, with deterministic augmentation).",
        f"- Classical routers: `{result['keyword']['ref']}` (threshold {result['keyword']['threshold']}, fixed in "
        f"code; served in production) and `{result['tfidf']['ref']}` (threshold "
        f"{result['tfidf']['threshold']:.4f}, chosen on dev at training).",
        f"- Prompt `{prompt['ref']}` (file sha256 `{prompt['sha256_12']}`), no router candidates (zero-shot), "
        f"temperature {prompt['temperature']}, at most {prompt['max_output_tokens']} output tokens, called "
        "through the full gateway, so each message is redacted exactly as in production.",
        "- Models: " + ", ".join(f"`{model}`" for model in result["models"]) + " (Azure OpenAI). Recorded calls: "
        f"`ml/cassettes/{result['cassette_dir']}/` (redacted, one JSON file per call).",
        "- Prices: `services/api/config/llm_prices.yaml`, read from the Azure Retail Prices API on 2026-10-05 "
        "(region swedencentral). The table marks them unverified until a person confirms them; that only adds the "
        "gateway's conservative multiplier and does not change this report. Cost per 1,000 messages is the measured "
        "tokens of this workload times the list price: an **offline measurement**, not production spend.",
        "- Intervals are 95% percentile bootstraps over whole seed groups (1,000 resamples). Dev fixed every "
        f"choice: the model thresholds (error among covered at most {pct(result['target_risk'], 0)}), the cascade "
        "thresholds, and the decision. Test only reports.",
        "",
    ]


def _rule_text(result: dict[str, Any]) -> list[str]:
    rule = result["rule"]
    return [
        "## Pre-registered decision rule",
        "",
        "Committed in [`docs/plans/router-llm.md`](../plans/router-llm.md) before any model call and before any "
        "test number existed. The zero-shot model is a reference, never a serving candidate. A cascade (TF-IDF "
        "first, the model only below TF-IDF's threshold) is recommended for a default-off end-to-end dev trial "
        "only if every criterion holds on dev:",
        "",
        f"1. Macro-F1 gain over TF-IDF alone above {Decimal(rule['min_gain']):.2f}, with the paired seed-group "
        "bootstrap 95% lower bound above 0.",
        f"2. High-stakes recall mean at most {Decimal(rule['recall_tolerance']):.2f} below TF-IDF alone.",
        "3. Confident misroutes into the write intents (`dispute_new`, `card_block`, `credit_application`) at "
        f"most TF-IDF's count plus {rule['extra_write_misroutes']}.",
        f"4. The model is called on at most {pct(float(rule['max_model_share']), 0)} of messages.",
        f"5. Model call p95 latency at most {float(rule['max_model_call_p95_ms']):,.0f} ms.",
        f"6. Cost at most {rule['max_cost_usd_per_1000']} USD per 1,000 messages at list price.",
        "",
        "When both models qualify, the higher dev macro-F1 wins unless the paired difference's interval contains "
        "0, in which case the cheaper model wins. Test never changes the decision. No production default changes "
        "in this work: the team's rule needs an end-to-end dev gain first, so `keyword@1` keeps serving.",
        "",
    ]


def _decision(result: dict[str, Any]) -> list[str]:
    decision = result["decision"]
    models = result["models"]
    lines = ["## Dev: the rule applied", ""]
    first = decision["candidates"][models[0]]["criteria"]
    header = ["Criterion", *(f"`{decision['candidates'][model]['system']}`" for model in models)]
    rows = []
    for position, row in enumerate(first):
        cells = [
            f"{decision['candidates'][model]['criteria'][position]['value']} "
            f"({'met' if decision['candidates'][model]['criteria'][position]['met'] else 'not met'})"
            for model in models
        ]
        rows.append([row["criterion"], *cells])
    rows.append(["Qualifies", *("yes" if decision["candidates"][model]["qualifies"] else "no" for model in models)])
    lines += table(header, rows)
    lines.append("")
    if decision["model_comparison"] is not None:
        comparison = decision["model_comparison"]
        lines += [
            f"Paired dev macro-F1 difference `{comparison['first']}` minus `{comparison['second']}`: "
            f"{ci(comparison['difference'])}.",
            "",
        ]
    if decision["chosen"] is None:
        outcome = "no cascade meets every criterion, so no end-to-end cascade trial is recommended."
    else:
        outcome = (
            f"the cascade with `{decision['chosen']}` meets every criterion, so a default-off end-to-end dev trial "
            "is recommended. This is not a default change."
        )
    lines += [f"**Mechanical outcome on dev:** {outcome}", ""]
    return lines


def _thresholds(result: dict[str, Any]) -> list[str]:
    rows = [
        [f"`{name}`", f"{t['threshold']:.3f}", pct(t["coverage"]), pct(t["risk"]), "yes" if t["met"] else "no"]
        for name, t in result["thresholds"].items()
    ]
    note = (
        "For a cascade, the threshold applies to the model's stated confidence on the dev messages that reach "
        "the model; coverage and risk are over those messages."
    )
    return [
        "## Model thresholds (chosen on dev)",
        "",
        *table(["System", "Threshold", "Dev coverage", "Dev error among covered", "Target met"], rows),
        "",
        note,
        "",
    ]


def _headline(result: dict[str, Any], split: str) -> list[str]:
    header = [
        "System",
        "Accuracy",
        "Macro-F1",
        "Workflow accuracy",
        "Coverage",
        "Error when acting",
        "High-stakes recall (mean)",
        "Confident write-intent misroutes",
        "Model share",
        "p50 / p95 ms per message",
        "Cost per 1,000 messages (USD)",
    ]
    rows = []
    for name, system in result["systems"].items():
        s = system[split]
        u = s["usage"]
        rows.append(
            [
                f"`{name}`",
                ci(s["accuracy"]),
                ci(s["macro_f1"]),
                ci(s["workflow_accuracy"]),
                ci(s["coverage"]),
                ci(s["risk_at_threshold"]),
                f"{s['high_stakes_recall_mean']:.3f}",
                f"{s['write_misroutes']} of {s['items']}",
                pct(u["model_share"]),
                f"{_ms(u['latency_ms_p50'])} / {_ms(u['latency_ms_p95'])}",
                _cost(u["cost_usd_per_1000"]),
            ]
        )
    return table(header, rows)


def _gains(result: dict[str, Any]) -> list[str]:
    tfidf = result["order"]["tfidf"]
    rows = [[f"`{name}`", ci(value)] for name, value in result["test_gain_over_tfidf"].items()]
    return [
        f"Paired test macro-F1 difference against `{tfidf}` (same items, seed groups resampled jointly):",
        "",
        *table(["System", "Macro-F1 minus TF-IDF"], rows),
        "",
    ]


def _regions_section(result: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for key, title in (("tfidf", result["order"]["tfidf"]), ("keyword", result["order"]["keyword"])):
        regions = result["regions"][key]
        names = list(next(iter(region["accuracy"] for region in regions.values() if region["accuracy"]), {}))
        rows = []
        for label, region in regions.items():
            cells = [ci(region["accuracy"][name]) if name in region["accuracy"] else "n/a" for name in names]
            rows.append([f"`{title}` {label}", region["items"], *cells])
        lines += table(["Region (test)", "Items", *(f"`{name}` accuracy" for name in names)], rows)
        lines.append("")
    return lines


def _slices(result: dict[str, Any], key: str, metric: str) -> list[str]:
    names = [name for name, system in result["systems"].items() if key in system["test"]]
    values = [row["slice"] for row in result["systems"][names[0]]["test"][key]]
    rows = []
    for name in names:
        by_slice = {row["slice"]: row for row in result["systems"][name]["test"][key]}
        rows.append([f"`{name}`", *(ci(by_slice[value][metric]) for value in values)])
    counts = {row["slice"]: row for row in result["systems"][names[0]]["test"][key]}
    header = ["System", *(f"{value} (n {counts[value]['items']} / {counts[value]['seed_groups']})" for value in values)]
    return table(header, rows)


def _per_intent(result: dict[str, Any], names: Sequence[str]) -> list[str]:
    first = result["systems"][names[0]]["test"]["per_intent"]
    rows = []
    for position, row in enumerate(first):
        cells = [f"{result['systems'][name]['test']['per_intent'][position]['f1']:.2f}" for name in names]
        marker = " (high stakes)" if row["high_stakes"] else ""
        rows.append([f"`{row['intent']}`{marker}", row["workflow"], row["items"], *cells])
    return table(["Intent", "Workflow", "n", *(f"`{name}` F1" for name in names)], rows)


def _high_stakes(result: dict[str, Any], names: Sequence[str]) -> list[str]:
    rows = []
    for intent in HIGH_STAKES:
        rows.append(
            [
                f"`{intent.value}`",
                *(ci(result["systems"][n]["test"]["high_stakes_recall"][intent.value]) for n in names),
            ]
        )
    return table(["Intent", *(f"`{name}` recall" for name in names)], rows)


def _out_of_scope(result: dict[str, Any]) -> list[str]:
    rows = []
    for name, system in result["systems"].items():
        test = system["test"]
        recall = test["out_of_scope_recall"]
        rows.append(
            [
                f"`{name}`",
                ci(recall) if recall else "n/a",
                f"{test['out_of_scope_confident_misroutes']} of {test['out_of_scope_items']}",
            ]
        )
    return table(["System", "Out-of-scope recall", "Confidently routed into a workflow"], rows)


def _confusions(result: dict[str, Any], names: Sequence[str]) -> list[str]:
    lines: list[str] = []
    for name in names:
        for language, matrix in result["systems"][name]["test"]["workflow_confusion_by_language"].items():
            rows = [[f"**{label}**", *row] for label, row in zip(WORKFLOW_LABELS, matrix, strict=True)]
            lines += [f"### `{name}`, {language}", "", *table(["True \\ predicted", *WORKFLOW_LABELS], rows), ""]
    return lines


def _calibration(result: dict[str, Any], names: Sequence[str]) -> list[str]:
    lines = [
        "The stated confidence is the model's own number for its top label. ECE uses 10 equal-width bins; empty "
        "bins are omitted.",
        "",
    ]
    rows = [[f"`{name}`", f"{result['systems'][name]['test']['ece']:.3f}"] for name in result["systems"]]
    lines += [*table(["System", "ECE (test)"], rows), ""]
    for name in names:
        bins = [b for b in result["systems"][name]["test"]["calibration"]["reliability"] if b["count"]]
        cells = [
            [f"{b['lower']:.1f} to {b['upper']:.1f}", b["count"], f"{b['mean_confidence']:.3f}", f"{b['accuracy']:.3f}"]
            for b in bins
        ]
        lines += [f"### `{name}`", "", *table(["Confidence bin", "Items", "Mean confidence", "Accuracy"], cells), ""]
    return lines


LATENCY_NOTE: Final = " ".join(
    (
        "Latency of a model call is the provider round trip recorded in the cassette, measured from the",
        "development machine under the recording concurrency, so it includes provider queueing. The committed",
        "cassettes were recorded on 2026-10-05: `azure/gpt-4.1-mini` on the evaluation account (East US, 8 calls",
        "in flight, capped at 130 per minute) and `azure/gpt-4o` on the production account (Sweden Central,",
        "2 calls in flight, capped at 35 per minute). Production calls `azure/gpt-4.1-mini` in Sweden Central",
        "from the Azure VM, so its latency differs. The classical routers were timed in process on the machine",
        "that generated this report. None of these numbers includes the rest of a turn.",
    )
)


def _operations(result: dict[str, Any]) -> list[str]:
    rows = []
    for name, system in result["systems"].items():
        u = system["test"]["usage"]
        if not u["model_calls"]:
            continue
        basis = u["price_basis"]
        price = (
            f"{basis['input_usd_per_million']} / {basis['output_usd_per_million']} "
            f"({'verified' if basis['verified'] else 'unverified'}, {basis['effective_date']})"
            if basis
            else "no price"
        )
        rows.append(
            [
                f"`{name}`",
                f"{u['model_calls']} ({pct(u['model_share'])})",
                f"{u['input_tokens_per_call']:.0f} / {u['output_tokens_per_call']:.0f}",
                f"{_ms(u['model_call_ms_p50'])} / {_ms(u['model_call_ms_p95'])}",
                u["failures"],
                u["repaired"],
                _cost(u["cost_usd_per_1000"]),
                price,
            ]
        )
    header = [
        "System",
        "Model calls (share)",
        "Input / output tokens per call",
        "Model call p50 / p95 ms",
        "Failures",
        "Repaired outputs",
        "Cost per 1,000 messages (USD)",
        "List price in / out per million (USD)",
    ]
    return [
        *table(header, rows),
        "",
        LATENCY_NOTE,
        "",
    ]


def _audit_section(result: dict[str, Any]) -> list[str]:
    rows = [
        [
            row["locale"],
            row["text"].replace("|", "/"),
            f"`{row['gold']}`",
            f"`{row['models']}`",
            f"{row['confidence']:.2f}",
        ]
        for row in result["audit"]
    ]
    intro = (
        "Canonical test seeds where every model agrees at stated confidence of at least "
        f"{AUDIT_CONFIDENCE} and disagrees with the team's label. They are candidates for the human validation "
        "sheet (`ml/corpus/router/validation/`), never relabeled automatically: the disagreement may be a model "
        "error, an ambiguous message, or a labeling convention the prompt does not state."
    )
    if not rows:
        return [intro, "", "None.", ""]
    return [intro, "", *table(["Locale", "Text", "Team label", "Models", "Confidence"], rows), ""]


LIMITATIONS: Final = (
    "- All text is synthetic and team-authored, and the same people wrote the seeds and the keyword patterns. "
    "The pt-BR seeds await native review, and the 200-item human validation sheet has no labels yet.",
    "- The prompt gives label names without definitions, so the model cannot know team conventions such as "
    "`informational` against `credit_product_info`. Part of its error measures label ambiguity, not "
    "understanding. A prompt with definitions or examples would be a new version, chosen on dev.",
    "- The stated confidence is coarse (few distinct values), so the model thresholds are coarse.",
    "- Dev has 68 seed groups, so the dev intervals that drive the decision are wide.",
    "- The latency is from one machine, one day, and one region, under the recording concurrency. It is not a "
    "production service level.",
    "- Cost covers the routing call only, at list price. It excludes the other model calls of a turn and any "
    "discount or reservation.",
    "- This is a component evaluation. Whether better routing changes safe automated resolution end to end "
    "needs a `bank-eval` dev run, which the team's rule requires before any default changes.",
)


def existing_decision(path: Path) -> str:
    """The hand-written decision between the markers of an existing report, or the pending sentence."""
    if not path.is_file():
        return PENDING_DECISION
    text = path.read_text(encoding="utf-8")
    start, end = text.find(DECISION_BEGIN), text.find(DECISION_END)
    if start < 0 or end < start:
        return PENDING_DECISION
    return text[start + len(DECISION_BEGIN) : end].strip() or PENDING_DECISION


def render(result: dict[str, Any], decision: str = PENDING_DECISION) -> str:
    order = result["order"]
    models = result["models"]
    main = [order["keyword"], order["tfidf"], *order["zero_shot"]]
    cascades = [f"{order['tfidf']} then {model}" for model in models]
    sections = [*_header(result), *_rule_text(result), *_decision(result), *_thresholds(result)]
    sections += ["## Dev split (every choice was made here)", "", *_headline(result, "dev"), ""]
    sections += ["## Test split (held out; report only)", "", *_headline(result, "test"), "", *_gains(result)]
    sections += [
        "## Where the model helps",
        "",
        "Test accuracy split by whether the classical router acts (at or above its threshold) or abstains. In the "
        "cascade, the model only sees the abstaining region.",
        "",
        *_regions_section(result),
    ]
    sections += ["## Per intent (test, F1)", "", *_per_intent(result, main), ""]
    sections += ["## High-stakes recall (test)", "", *_high_stakes(result, [*main, *cascades]), ""]
    sections += ["## Out-of-scope slice (test)", "", *_out_of_scope(result), ""]
    sections += ["## By language (test, accuracy)", "", *_slices(result, "by_language", "accuracy"), ""]
    sections += ["## By language (test, macro-F1)", "", *_slices(result, "by_language", "macro_f1"), ""]
    sections += ["## By dialect (test, accuracy)", "", *_slices(result, "by_locale", "accuracy"), ""]
    sections += ["## Workflow confusion by language (test)", "", *_confusions(result, [*order["zero_shot"], *cascades])]
    sections += ["## Calibration of the stated confidence (test)", "", *_calibration(result, order["zero_shot"])]
    sections += ["## Tokens, latency, and cost (test)", "", *_operations(result)]
    sections += ["## Label audit candidates (test)", "", *_audit_section(result)]
    sections += ["## Limitations", "", *LIMITATIONS, ""]
    sections += ["## Decision", "", DECISION_BEGIN, "", decision, "", DECISION_END, ""]
    return "\n".join(sections)


def write_benchmark(
    dataset: RouterDataset,
    models: Sequence[str],
    store: FilesystemModelStore,
    tfidf_reference: str,
    cassette_dir: Path,
    output: Path,
    evaluations_dir: Path = EVALUATIONS_DIR,
    replay: Replay = replay_cassettes,
) -> dict[str, Any]:
    """Run the benchmark from the cassettes, write the evaluation JSON, and rewrite the report at ``output``."""
    result = benchmark(dataset, models, store, tfidf_reference, cassette_dir, replay=replay)
    evaluations_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False, default=str)
    (evaluations_dir / "router_llm.json").write_text(payload, encoding="utf-8")
    output.write_text(render(result, existing_decision(output)), encoding="utf-8")
    return result
