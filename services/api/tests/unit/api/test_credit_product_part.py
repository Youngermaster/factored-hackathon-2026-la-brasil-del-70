"""``AssistantMessage.of`` names each credit product in the response's language, and ``None`` for an unknown code."""

from bank_agent.api.schemas.conversations import AssistantMessage
from bank_agent.domain.conversation import AssistantResponse
from bank_agent.domain.credit import CreditProductType
from bank_agent.domain.identifiers import CreditProductCode
from bank_agent.domain.locale import Country, Language
from bank_agent.policy.loader.catalog import ProductDisplay
from bank_agent_credit import credit_product

LOAN = credit_product("MX-PL-FIXTURE", CreditProductType.PERSONAL_LOAN, Country.MX, "10000", "350000")
CARD = credit_product("MX-CC-FIXTURE", CreditProductType.CREDIT_CARD, Country.MX, "5000", "100000")


class FixtureNames:
    """Catalog names for the loan only, in every language. Test double."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, Language]] = []

    def display(self, code: CreditProductCode, language: Language) -> ProductDisplay | None:
        self.asked.append((code, language))
        if code != "MX-PL-FIXTURE":
            return None
        return ProductDisplay(name=f"loan name ({language.value})", summary="Fixture summary.")


def test_names_come_from_the_catalog_in_the_message_language() -> None:
    names = FixtureNames()
    response = AssistantResponse(language=Language.PT, text="Fixture.", credit_products=(LOAN, CARD))
    message = AssistantMessage.of(response, names)
    assert [(p.product_code, p.display_name) for p in message.credit_products] == [
        ("MX-PL-FIXTURE", "loan name (pt)"),
        ("MX-CC-FIXTURE", None),
    ]
    assert names.asked == [("MX-PL-FIXTURE", Language.PT), ("MX-CC-FIXTURE", Language.PT)]
    assert message.credit_products[0].max_amount == LOAN.max_amount
    assert message.text == "Fixture."


def test_a_message_without_credit_products_asks_for_no_names() -> None:
    names = FixtureNames()
    message = AssistantMessage.of(AssistantResponse(language=Language.ES, text="Hola."), names)
    assert message.credit_products == ()
    assert names.asked == []
