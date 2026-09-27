"""``bank-ml risk promote``: move ``champion`` to a learned candidate only when it beats every reference on the
held-out test split, and record the decision either way.

The rule was fixed in ``docs/plans/phase-10b.md`` before any test number existed (the human asked that the learned
model beat the baselines on test, never used for tuning). Against each reference the candidate needs:

- the paired bootstrap 95% lower bound of the test ROC AUC difference above zero;
- test PR AUC not lower;
- test Brier score not higher by more than ``BRIER_TOLERANCE``;
- test ECE at most ``ECE_CEILING``.

``lgbm`` is compared with both score-band baselines and ``logreg``; ``logreg`` with both score-band baselines. The
evaluation must be of the current candidate (same artifact version); otherwise nothing is promoted.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import JsonValue

from bank_agent.adapters.models.registry import FilesystemModelStore
from bank_ml.common.promotion import Decision
from bank_ml.risk.evaluation import REFERENCES
from bank_ml.risk.training import registry_name

BRIER_TOLERANCE = 0.002
ECE_CEILING = 0.03


def check(evaluation: dict[str, Any], kind: str) -> Decision:
    models, comparisons = evaluation["models"], evaluation["comparisons"][kind]
    candidate = models[kind]["test"]
    ok, reasons, compared = True, [], {}
    for reference in REFERENCES[kind]:
        other = models[reference]["test"]
        auc_low = comparisons[reference]["roc_auc"]["low"]
        pr_gain = candidate["pr_auc"]["estimate"] - other["pr_auc"]["estimate"]
        brier_loss = candidate["brier"]["estimate"] - other["brier"]["estimate"]
        checks = (
            (auc_low > 0, f"vs {reference}: ROC AUC difference lower bound {auc_low:+.4f} (needs > 0)"),
            (pr_gain >= 0, f"vs {reference}: PR AUC {pr_gain:+.4f} (needs >= 0)"),
            (brier_loss <= BRIER_TOLERANCE, f"vs {reference}: Brier {brier_loss:+.4f} (needs <= {BRIER_TOLERANCE})"),
        )
        for passed, reason in checks:
            ok = ok and passed
            reasons.append(f"{reason}: {'pass' if passed else 'fail'}")
        compared[reference] = {
            "roc_auc": other["roc_auc"]["estimate"],
            "pr_auc": other["pr_auc"]["estimate"],
            "brier": other["brier"]["estimate"],
            "roc_auc_diff_low": auc_low,
        }
    ece = candidate["ece"]["estimate"]
    ok = ok and ece <= ECE_CEILING
    reasons.append(f"test ECE {ece:.4f} (needs <= {ECE_CEILING}): {'pass' if ece <= ECE_CEILING else 'fail'}")
    compared["candidate"] = {key: candidate[key]["estimate"] for key in ("roc_auc", "pr_auc", "brier", "ece")}
    return Decision(ok, tuple(reasons), compared)


def promote_all(
    store: FilesystemModelStore, evaluation_file: Path, *, approved_by: str, now: datetime, commit: str
) -> dict[str, Decision]:
    if not evaluation_file.is_file():
        return {kind: Decision(False, ("no evaluation; run bank-ml risk evaluate first",)) for kind in REFERENCES}
    evaluation = json.loads(evaluation_file.read_text(encoding="utf-8"))
    decisions: dict[str, Decision] = {}
    for kind in REFERENCES:
        name = registry_name(kind)
        alias = store.alias(name, "candidate")
        if alias is None:
            decisions[kind] = Decision(False, (f"{name} has no candidate; run train first",))
            continue
        candidate = store.registry.resolve(name, "candidate")
        if evaluation["learned"][kind]["artifact"] != str(candidate.ref):
            decisions[kind] = Decision(False, (f"the evaluation is not of {candidate.ref}; run evaluate first",))
            continue
        champion = store.alias(name, "champion")
        if champion is not None and champion["version"] == candidate.ref.version:
            decisions[kind] = Decision(False, ("the candidate is already the champion",))
            continue
        decision = check(evaluation, kind)
        record: dict[str, JsonValue] = {
            "approved_by": approved_by,
            "decided_at": now.isoformat(),
            "git_sha": commit,
            "candidate": str(candidate.ref),
            "compared_with": list[JsonValue](REFERENCES[kind]),
            "split": "test",
            "evaluation_generated_at": str(evaluation["generated_at"]),
            "decision": "promoted" if decision.promote else "refused",
            "reasons": list[JsonValue](decision.reasons),
            "metrics_compared": {key: dict(values.items()) for key, values in decision.compared.items()},
        }
        if decision.promote:
            store.set_alias(name, "champion", candidate.ref.version, record)
        else:
            store.log_decision(name, {"alias": "champion", "version": candidate.ref.version, **record})
        decisions[kind] = decision
    return decisions
