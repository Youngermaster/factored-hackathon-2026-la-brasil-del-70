"""The synthetic credit catalog under ``policies/credit/``: one file per product per jurisdiction.

Each file is a ``CreditProduct`` plus ``display`` text in es, pt, and en. The catalog must be internally
consistent (one version, unique codes, file name equal to the code) and agree with the policy pack: every
eligibility clause exists, and a self-service product lists exactly the ELG clauses the synthetic eligibility
service will use for its jurisdiction and type.
"""

import re
from collections.abc import Mapping
from typing import Annotated

from pydantic import StringConstraints, ValidationError

from bank_agent.domain.base import DomainModel
from bank_agent.domain.credit import CreditProduct
from bank_agent.domain.errors import PolicyPackInvalidError
from bank_agent.domain.locale import Language
from bank_agent.policy.lexicon import approval_terms
from bank_agent.policy.loader.documents import PackProblems, load_yaml
from bank_agent.policy.pack import PolicyPack
from bank_agent.policy.selection import eligibility_clauses

CATALOG_PATH = re.compile(r"^credit/(?P<code>[A-Z][A-Z0-9_-]{2,31})\.yaml$")
HUMAN_ASSESSMENT_CLAUSE = "ELG-ALL-3"


class ProductDisplay(DomainModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=120)]
    summary: Annotated[str, StringConstraints(min_length=1, max_length=400)]


class CatalogEntry(DomainModel):
    product: CreditProduct
    display: dict[Language, ProductDisplay]


def parse_catalog(files: Mapping[str, str]) -> tuple[CatalogEntry, ...]:
    """Parse and check every catalog file; raises ``PolicyPackInvalidError`` listing every problem."""
    problems = PackProblems()
    entries: list[CatalogEntry] = []
    for path in sorted(files):
        match = CATALOG_PATH.fullmatch(path)
        if not path.startswith("credit/"):
            continue
        if match is None:
            problems.add(path, "a catalog file is credit/<PRODUCT-CODE>.yaml")
            continue
        data = load_yaml(path, files[path], problems)
        if not isinstance(data, dict) or "display" not in data:
            problems.add(path, "a catalog file is a product with a display section")
            continue
        display = data.pop("display")
        try:
            entry = CatalogEntry(product=CreditProduct.model_validate(data), display=display)
        except ValidationError as error:
            fields = sorted({".".join(str(part) for part in item["loc"]) for item in error.errors()})
            problems.add(path, f"invalid ({', '.join(fields)})")
            continue
        if entry.product.product_code != match["code"]:
            problems.add(path, "the file name must be the product code")
        if set(entry.display) != set(Language):
            problems.add(path, "display text is needed in es, pt, and en")
        if any(approval_terms(f"{text.name} {text.summary}") for text in entry.display.values()):
            problems.add(path, "display text contains approval wording")
        entries.append(entry)
    versions = {entry.product.catalog_version for entry in entries}
    if len(versions) > 1:
        problems.add("credit/", "every product carries the same catalog version")
    codes = [entry.product.product_code for entry in entries]
    if len(set(codes)) != len(codes):
        problems.add("credit/", "product codes must be unique")
    if not entries:
        problems.add("credit/", "the catalog is empty")
    if problems:
        raise PolicyPackInvalidError("invalid credit catalog: " + "; ".join(problems.items))
    return tuple(entries)


def check_catalog_against_pack(entries: tuple[CatalogEntry, ...], pack: PolicyPack) -> None:
    """Raise ``PolicyPackInvalidError`` when a product's eligibility clauses disagree with the pack."""
    problems = PackProblems()
    known = set(pack.clause_ids())
    for entry in entries:
        product = entry.product
        listed = set(product.eligibility_clause_ids)
        for clause_id in sorted(listed - known):
            problems.add(product.product_code, f"names unknown clause {clause_id}")
        if product.self_service_eligibility:
            current = pack.list_clauses(language=Language.ES, jurisdiction=product.jurisdiction)
            used = eligibility_clauses(current, product.jurisdiction, product.product_type.value)
            if listed != {clause.metadata.clause_id for clause in used}:
                problems.add(product.product_code, "must list exactly the ELG clauses used for its type")
        elif HUMAN_ASSESSMENT_CLAUSE not in listed:
            problems.add(product.product_code, f"a human-assessed product lists {HUMAN_ASSESSMENT_CLAUSE}")
    if problems:
        raise PolicyPackInvalidError("credit catalog disagrees with the policy pack: " + "; ".join(problems.items))
