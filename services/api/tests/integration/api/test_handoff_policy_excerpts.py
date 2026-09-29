"""Handoff views carry their policy basis with the clause text from the loaded pack, in the handoff's language."""

from bank_agent.domain.access import AccessContext
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.identifiers import CustomerId, HandoffId
from bank_agent.domain.locale import Country, Language
from bank_agent_api import ApiBackend, ApiClient
from bank_agent_builders import handoff_v1_1
from bank_agent_scenarios import PT

HANDOFF = "ho-api-excerpts-01"
BASIS = ["ESC-ALL-9@1", "ESC-MX-2@1", "ESC-MX-2@7", "ESC-ALL-1@1"]
MX_SLA_PT = (
    "No México, uma pessoa da equipe entrará em contato em até 24 horas. Se a conversa mostrar uma situação de "
    "vulnerabilidade ou urgência, o prazo é de 4 horas."
)


async def test_a_portuguese_handoff_shows_each_resolvable_basis_clause_in_portuguese(api_backend: ApiBackend) -> None:
    harness = api_backend.build()
    document = handoff_v1_1(
        handoff_id=HandoffId(HANDOFF), customer_ref=PT, case_ref=None, actions_taken=[], language=Language.PT,
        jurisdiction=Country.MX, policy_basis=[ClauseRef.parse(ref) for ref in BASIS],
    )  # fmt: skip
    async with harness.container.persistence.uow_factory(AccessContext.for_customer(CustomerId(PT))) as uow:
        await uow.handoffs.add(document)
        await uow.commit()
    async with ApiClient(harness.app) as agent:
        await agent.login("persona-agent")
        listed = await agent.get("/v1/agent/handoffs", params={"language": "pt"})
        detail = await agent.get(f"/v1/agent/handoffs/{HANDOFF}")
        claimed = await agent.post(f"/v1/agent/handoffs/{HANDOFF}/claim")
    (item,) = [view for view in listed.json()["handoffs"] if view["handoff_id"] == HANDOFF]
    view = detail.json()
    assert view["policy_basis"] == BASIS
    excerpts = view["policy_excerpts"]
    assert [citation["clause"] for citation in excerpts] == ["ESC-MX-2@1", "ESC-ALL-1@1"]
    assert excerpts[0]["excerpt"] == MX_SLA_PT
    assert excerpts[1]["excerpt"].startswith("Uma pessoa da equipe assume a conversa quando você pede")
    assert "{" not in excerpts[1]["excerpt"]
    assert item["policy_excerpts"] == excerpts
    assert claimed.json()["policy_excerpts"] == excerpts
