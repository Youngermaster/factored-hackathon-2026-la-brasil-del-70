"""The feature vector of the learned risk estimators (``risk_features@1``), shared by training and serving.

``bank-ml`` builds training rows from gold ``credit_profiles_serving`` through the API's own ``CreditProfile`` mapper
and ``from_profile``; the adapters build serving rows from ``CreditRiskFeatures`` with ``from_features``. Both go
through ``vector``, so the two paths cannot drift apart.

Only four allowlisted fields are model features: the credit score, tenure, the number of open credit products, and
revolving utilization. The allowlist's days past due define the training label, so they are never read here; the
application fields (product, term, amount to income) do not exist in the single customer snapshot the models learn
from; income is not served in USD (no exchange rates). Nothing here names a protected or proxy attribute, and the
leakage scan in ``ml/tests`` checks this module's source.
"""

import math
from collections.abc import Sequence
from decimal import Decimal

from bank_agent.domain.credit import CreditProfile
from bank_agent.domain.eligibility import CreditRiskFeatures

FEATURES_ID = "risk_features@1"
FEATURE_NAMES: tuple[str, ...] = ("credit_score", "tenure_months", "credit_product_count", "utilization")

Number = int | Decimal | float | None


def vector(
    credit_score: Number, tenure_months: Number, credit_product_count: Number, utilization: Number
) -> list[float]:
    """The model row in ``FEATURE_NAMES`` order; a missing value is NaN."""
    values = (credit_score, tenure_months, credit_product_count, utilization)
    return [math.nan if value is None else float(value) for value in values]


def from_features(features: CreditRiskFeatures) -> list[float]:
    return vector(features.credit_score, features.tenure_months, features.credit_product_count, features.utilization)


def from_profile(profile: CreditProfile) -> list[float]:
    return vector(profile.credit_score, profile.tenure_months, profile.credit_product_count, profile.utilization)


def missing(row: Sequence[float]) -> tuple[str, ...]:
    """Names of the features that are NaN in ``row``, in feature order."""
    return tuple(name for name, value in zip(FEATURE_NAMES, row, strict=True) if math.isnan(value))
