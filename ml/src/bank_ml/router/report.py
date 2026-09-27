"""Renders ``docs/evaluation/router.md`` from the evaluation JSON written by ``bank-ml router evaluate``."""

from typing import Any

from bank_ml.common.reports import pct, table
from bank_ml.router.evaluate import WORKFLOW_LABELS


def ci(value: dict[str, float], digits: int = 3) -> str:
    if value["estimate"] != value["estimate"]:  # NaN: no item in the cell
        return "n/a"
    return f"{value['estimate']:.{digits}f} [{value['low']:.{digits}f}, {value['high']:.{digits}f}]"


def _header(result: dict[str, Any]) -> list[str]:
    dataset = result["dataset"]
    artifacts = ", ".join(f"`{ref}`" for ref in result["artifacts"].values() if ref) or "none"
    lines = [
        "# Router evaluation",
        "",
        f"Generated {result['generated_at']} from commit `{result['git_sha']}` by `bank-ml router evaluate`. "
        "Do not edit by hand; rerun `make train` (or `bank-ml router evaluate`).",
        "",
        f"- Dataset `{dataset['version']}`, content hash `{dataset['hash'][:16]}`: "
        + ", ".join(f"{split} {count}" for split, count in dataset["rows_per_split"].items())
        + " items.",
        f"- Evaluated artifacts ({result['alias']}): {artifacts}.",
        "- All text is synthetic: team-authored seeds in es-MX, es-CO, es-AR, and pt-BR plus deterministic "
        "augmentation (`docs/models/router.md`). Organizer transcripts carry no intent signal (see the last "
        "section). pt-BR seeds await native review, and no language-model paraphrase is included yet.",
        "- Intervals are 95% percentile bootstraps that resample whole seed groups (1,000 resamples); `n` is items "
        "and seed groups. The test split was never used for any choice: C, the temperature, the abstention "
        "threshold, and promotion all use dev.",
    ]
    if result.get("embeddings_skipped"):
        lines.append(f"- `router:embeddings` was not trained: {result['embeddings_skipped']}.")
    return [*lines, ""]


def _headline(result: dict[str, Any], split: str) -> list[str]:
    header = ["Model", "Accuracy", "Macro-F1", "Workflow accuracy", "Coverage", "Risk at threshold", "ECE"]
    header += ["High-stakes recall (mean)", "n (items / seed groups)"]
    rows = []
    for name, model in result["models"].items():
        s = model[split]
        rows.append(
            [
                f"`{name}`",
                ci(s["accuracy"]),
                ci(s["macro_f1"]),
                ci(s["workflow_accuracy"]),
                ci(s["coverage"]),
                ci(s["risk_at_threshold"]),
                f"{s['ece']:.3f}",
                f"{s['high_stakes_recall_mean']:.3f}",
                f"{s['items']} / {s['seed_groups']}",
            ]
        )
    return table(header, rows)


def _thresholds(result: dict[str, Any]) -> list[str]:
    rows = [
        [f"`{name}`", f"{t['threshold']:.4f}", pct(t["coverage"]), pct(t["risk"]), pct(t["target"]), t["met"]]
        for name, t in result["thresholds"].items()
    ]
    rows.append(["`keyword@1`", "0.6000 (fixed in code)", "-", "-", "-", "-"])
    return table(["Model", "Threshold", "Dev coverage", "Dev risk", "Target risk", "Met"], rows)


def _per_intent(result: dict[str, Any]) -> list[str]:
    names = list(result["models"])
    first = result["models"][names[0]]["test"]["per_intent"]
    header = ["Intent", "Workflow", "n (items / groups)", *(f"{name} P / R" for name in names)]
    rows = []
    for position, row in enumerate(first):
        cells = [
            f"{result['models'][name]['test']['per_intent'][position]['precision']:.2f} / "
            f"{result['models'][name]['test']['per_intent'][position]['recall']:.2f}"
            for name in names
        ]
        mark = " (high stakes)" if row["high_stakes"] else ""
        rows.append([f"`{row['intent']}`{mark}", row["workflow"], f"{row['items']} / {row['seed_groups']}", *cells])
    return table(header, rows)


def _slices(result: dict[str, Any], key: str, title: str) -> list[str]:
    names = list(result["models"])
    first = result["models"][names[0]]["test"][key]
    header = [title, "n (items / groups)", *(f"{name} accuracy" for name in names)]
    rows = []
    for position, row in enumerate(first):
        cells = [ci(result["models"][name]["test"][key][position]["accuracy"], 2) for name in names]
        rows.append([row["slice"], f"{row['items']} / {row['seed_groups']}", *cells])
    return table(header, rows)


def _confusion(matrix: list[list[int]]) -> list[str]:
    rows = [[f"**{label}**", *row] for label, row in zip(WORKFLOW_LABELS, matrix, strict=True)]
    return table(["True \\ predicted", *WORKFLOW_LABELS], rows)


def _calibration(name: str, model: dict[str, Any]) -> list[str]:
    bins = [b for b in model["test"]["calibration"]["reliability"] if b["count"]]
    labels = ", ".join(f'"{b["lower"]:.1f}"' for b in bins)
    accuracy = ", ".join(f"{b['accuracy']:.3f}" for b in bins)
    confidence = ", ".join(f"{b['mean_confidence']:.3f}" for b in bins)
    lines = [
        f"### `{name}`",
        "",
        "```mermaid",
        "xychart-beta",
        f'    title "Reliability, {name} (bars: accuracy; line: mean confidence)"',
        f"    x-axis [{labels}]",
        '    y-axis "Share" 0 --> 1',
        f"    bar [{accuracy}]",
        f"    line [{confidence}]",
        "```",
        "",
    ]
    lines += table(
        ["Bin", "Items", "Mean confidence", "Accuracy"],
        [
            [f"{b['lower']:.1f} to {b['upper']:.1f}", b["count"], f"{b['mean_confidence']:.3f}", f"{b['accuracy']:.3f}"]
            for b in bins
        ],
    )
    curve = model["test"]["calibration"]["coverage_risk"]
    lines += ["", "Coverage against risk (test):", ""]
    lines += table(
        ["Threshold", "Coverage", "Risk"],
        [[f"{p['threshold']:.3f}", pct(p["coverage"]), pct(p["risk"])] for p in curve],
    )
    return [*lines, ""]


def _robustness(result: dict[str, Any]) -> list[str]:
    data = result["robustness"]
    kinds = ["clean", "accents", "homophones", "fillers", "truncation", "combined"]
    rows = [
        [f"`{name}`", *(ci(values[kind], 2) for kind in kinds)]
        for name, values in data.items()
        if name != "items_per_set"
    ]
    lines = [f"Each set is the {data['items_per_set']} canonical test seeds, perturbed deterministically.", ""]
    return lines + table(["Model", *kinds], rows)


def _transfer(result: dict[str, Any]) -> list[str]:
    data = result["transfer"]
    es_pt = data["es_to_pt"]
    lines = [
        f"TF-IDF retrained with the same C without the held-out part; reference: `{data['reference']}`.",
        "",
    ]
    rows = [
        [
            "pt-BR test (Spanish-to-Portuguese transfer)",
            es_pt["items"],
            ci(es_pt["in_language"], 2),
            ci(es_pt["spanish_only"], 2),
        ]
    ]
    rows += [
        [
            f"{locale} test (held-out dialect)",
            values["items"],
            ci(values["in_distribution"], 2),
            ci(values["held_out"], 2),
        ]
        for locale, values in data["held_out_dialect"].items()
    ]
    return lines + table(["Slice", "Items", "Trained with it (in distribution)", "Trained without it"], rows)


def _language(result: dict[str, Any]) -> list[str]:
    data = result["language_detection"]
    rows = [
        [
            language,
            data[language]["items"],
            pct(data[language]["correct"]),
            pct(data[language]["uncertain"]),
            pct(data[language]["wrong"]),
        ]
        for language in ("es", "pt")
    ]
    return [
        f"Detector `{data['detector']}` on every corpus item (all splits).",
        "",
        *table(["Language", "Items", "Correct", "Uncertain (asks)", "Wrong"], rows),
    ]


def _transcripts(result: dict[str, Any]) -> list[str]:
    data = result.get("transcripts")
    if not data:
        return ["Not computed: no local warehouse (`make pipeline DATA_SOURCE=s3`)."]
    rows = [[workflow, count] for workflow, count in data["by_mapped_workflow"].items()]
    lines = [
        f"{data['texts']:,} interactions carry customer text, but only **{data['distinct_texts']} distinct texts** "
        f"exist (balance-question templates). `detected_intents`: "
        + ", ".join(f"`{k}` {v:,}" for k, v in data["detected_intents"].items())
        + f". Agreement between the mapped contact reason and `detected_intents`: {pct(data['agreement'])} "
        "(no detected intent maps to a workflow). The mapped contact reason therefore cannot label router intents, "
        "and the router uses team-authored seeds instead (`docs/analysis/labeling-protocol.md`).",
        "",
    ]
    return lines + table(["Workflow of the mapped contact reason", "Texts"], rows)


def _validation(result: dict[str, Any]) -> list[str]:
    data = result["validation"]
    if data.get("status") != "labeled":
        return [
            f"Status: **{data.get('status')}** ({data.get('items', 0)} items in "
            "`ml/corpus/router/validation/router_validation_v1.csv`; protocol in "
            "`docs/evaluation/router-labeling.md`). Agreement and label accuracy are reported once labeled."
        ]
    lines = [f"Double-labeled: {data['double_labeled']} of {data['items']}."]
    if "kappa" in data:
        lines.append(f"Cohen's kappa: {data['kappa']:.3f}.")
    if "label_accuracy" in data:
        lines.append(
            f"Label accuracy against the assigned intents: {pct(data['label_accuracy'])} "
            f"({data['adjudicated']} adjudicated)."
        )
    return [" ".join(lines)]


def _errors(result: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for name, rows in result["errors"].items():
        lines += [f"### `{name}`", ""]
        lines += table(
            ["Text (synthetic)", "Locale", "True", "Predicted", "Confidence"],
            [
                [
                    row["text"].replace("|", "/"),
                    row["locale"],
                    row["truth"],
                    row["predicted"],
                    f"{row['confidence']:.2f}",
                ]
                for row in rows
            ],
        )
        lines.append("")
    return lines


def render(result: dict[str, Any]) -> str:
    sections: list[str] = _header(result)
    sections += ["## Test split (held out)", "", *_headline(result, "test"), ""]
    sections += ["## Dev split (used for C, temperature, threshold, and promotion)", "", *_headline(result, "dev"), ""]
    sections += ["## Abstention thresholds (chosen on dev)", "", *_thresholds(result), ""]
    sections += ["## Per intent (test)", "", *_per_intent(result), ""]
    sections += ["## By workflow (test)", "", *_slices(result, "by_workflow", "Workflow"), ""]
    sections += ["## By language and locale (test)", "", *_slices(result, "by_language", "Language"), ""]
    sections += [*_slices(result, "by_locale", "Locale"), ""]
    sections += ["## By augmentation kind (test)", "", *_slices(result, "by_augmentation", "Augmentation"), ""]
    sections += ["## Workflow confusion (test)", ""]
    for name, model in result["models"].items():
        if name in result["artifacts"] or name == "keyword@1":
            sections += [f"### `{name}`", "", *_confusion(model["test"]["workflow_confusion"]), ""]
    sections += ["## Calibration and coverage (test)", ""]
    for name, model in result["models"].items():
        if name in result["artifacts"]:
            sections += _calibration(name, model)
    sections += ["## Robustness: speech-to-text noise (test)", "", *_robustness(result), ""]
    sections += ["Paraphrase robustness set: " + result["paraphrase_eval"], ""]
    sections += ["## Transfer and out of distribution", "", *_transfer(result), ""]
    sections += ["## Language detector", "", *_language(result), ""]
    sections += ["## Human validation", "", *_validation(result), ""]
    sections += ["## Failure examples (canonical test seeds, most confident first)", "", *_errors(result)]
    sections += ["## Why not transcripts", "", *_transcripts(result), ""]
    return "\n".join(sections).rstrip() + "\n"
