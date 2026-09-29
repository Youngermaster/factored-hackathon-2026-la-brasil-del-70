"""Credit product parts name each product from the catalog in the message's language, in turns and in history."""

from bank_agent_api import ApiBackend, ApiClient


async def test_credit_products_carry_the_catalog_name_in_the_message_language(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    async with ApiClient(harness.app) as spanish, ApiClient(harness.app) as portuguese:
        await spanish.login("persona-co")
        es_conversation = await spanish.open_conversation()
        es_turn = await spanish.say(es_conversation, "¿Qué condiciones tiene el préstamo personal?")
        history = await spanish.get(f"/v1/conversations/{es_conversation}")
        await portuguese.login("persona-pt", language="pt")
        pt_conversation = await portuguese.open_conversation()
        pt_turn = await portuguese.say(pt_conversation, "Quais produtos de crédito vocês têm?")
    es_message = es_turn.json()["message"]
    assert es_message["language"] == "es"
    assert [(p["product_code"], p["display_name"]) for p in es_message["credit_products"]] == [
        ("CO-PL-STANDARD", "Préstamo personal Estándar")
    ]
    (turn,) = history.json()["turns"]
    assert turn["message"]["credit_products"][0]["display_name"] == "Préstamo personal Estándar"
    pt_message = pt_turn.json()["message"]
    assert pt_message["language"] == "pt"
    names = {p["product_code"]: p["display_name"] for p in pt_message["credit_products"]}
    assert names == {
        "MX-CC-CLASSIC": "Cartão de crédito Clássico",
        "MX-MG-FIXED": "Financiamento imobiliário a taxa fixa",
        "MX-PL-STANDARD": "Empréstimo pessoal Padrão",
    }
