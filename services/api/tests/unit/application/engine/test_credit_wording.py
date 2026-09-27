"""Credit wording guards: no template in any language contains approval wording, even negated, and no credit
template claims an eligibility outcome of its own (outcomes come only from the rendered eligibility view)."""

import pytest

from bank_agent.application.engine.templates import TEMPLATES
from bank_agent.application.grounding.lexicon import claimed_outcomes
from bank_agent.application.grounding.numbers import fold_same_length
from bank_agent.application.workflows.baseline import templates as baseline_templates
from bank_agent.domain.locale import Language
from bank_agent.policy.lexicon import approval_terms

del baseline_templates


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_no_template_contains_approval_wording(template: str) -> None:
    for language in (Language.ES, Language.PT, Language.EN):
        assert approval_terms(TEMPLATES[template][language]) == (), (template, language)


@pytest.mark.parametrize("template", sorted(name for name in TEMPLATES if name.startswith("credit.")))
def test_no_credit_template_claims_an_eligibility_outcome(template: str) -> None:
    for language in (Language.ES, Language.PT, Language.EN):
        assert claimed_outcomes(fold_same_length(TEMPLATES[template][language])) == [], (template, language)
