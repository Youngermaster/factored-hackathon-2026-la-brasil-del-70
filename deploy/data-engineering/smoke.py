"""Exercise the production API against the VM database, with no HTTP port exposed."""

import asyncio
import json
import sys
import uuid
from pathlib import Path

import httpx

from bank_agent.asgi import create_app

FLOWS = (
    ("account_inquiry", "es", "acc-mx-accounts", "¿Cuál es el saldo de mis cuentas?"),
    ("account_inquiry", "pt", "acc-mx-accounts", "Qual é o saldo das minhas contas?"),
    ("card_support", "es", "crd-co-declined", "¿Cuál es el estado de mi tarjeta?"),
    ("card_support", "pt", "crd-co-declined", "Qual é o status do meu cartão?"),
    ("dispute", "es", "dsp-co-unrecognized", "No reconozco un cargo en mi tarjeta de crédito"),
    ("dispute", "pt", "dsp-co-unrecognized", "Não reconheço uma cobrança no meu cartão de crédito"),
    ("credit", "es", "cre-mx-complete", "Quiero conocer los productos de crédito que ofrecen."),
    ("credit", "pt", "cre-mx-complete", "Quero conhecer os produtos de crédito que vocês oferecem."),
)


def require(condition: bool, stage: str) -> None:
    if not condition:
        raise RuntimeError(f"Application verification failed at {stage}; customer output withheld")


async def run(output: Path) -> None:
    app = create_app()
    evidence: list[dict[str, str | int]] = []
    first_conversation = ""
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://la70.internal") as client,
    ):
        for path in ("/health/live", "/health/ready"):
            response = await client.get(path)
            require(response.status_code == 200, path)
        for index, (workflow, language, persona, message) in enumerate(FLOWS):
            # Each scenario represents an independent client; preserve production auth limits.
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app, client=(f"192.0.2.{index + 1}", 443)),
                base_url="https://la70.internal",
            ) as scenario:
                csrf = (await scenario.get("/v1/auth/csrf")).json()["csrf_token"]
                scenario.headers["X-CSRF-Token"] = csrf
                started = await scenario.post("/v1/auth/start", json={"kind": "persona", "persona_id": persona})
                require(started.status_code == 200, "identity-start")
                challenge = started.json()
                verified = await scenario.post(
                    "/v1/auth/verify", json={"challenge_id": challenge["challenge_id"], "code": challenge["demo_code"]}
                )
                require(verified.status_code == 200, "identity-verify")
                scenario.headers["X-CSRF-Token"] = verified.json()["csrf_token"]
                created = await scenario.post("/v1/conversations")
                require(created.status_code == 201, "conversation-create")
                conversation = created.json()["conversation_id"]
                first_conversation = first_conversation or conversation
                reply = await scenario.post(
                    f"/v1/conversations/{conversation}/turns", json={"turn_id": str(uuid.uuid4()), "text": message}
                )
                require(reply.status_code == 200, "conversation-turn")
                body = reply.json()
                actual_workflow = (body.get("workflow") or {}).get("id")
                require(
                    actual_workflow == workflow,
                    f"{workflow}/{language} workflow={actual_workflow} "
                    f"state={body.get('state')} outcome={body.get('outcome')}",
                )
                require(body["message"].get("language") == language, "reply-language")
                require(body["outcome"] in {"resolved", "clarified", "in_progress"}, workflow)
                require(bool(body["message"].get("text")), "reply")
                evidence.append({"workflow": workflow, "language": language, "outcome": body["outcome"]})
                if index == len(FLOWS) - 1:
                    probe = await scenario.get(f"/v1/conversations/{first_conversation}")
                    require(probe.status_code == 404, "customer-isolation")
    await asyncio.to_thread(
        output.write_text, json.dumps({"flows": evidence, "cross_customer_status": 404}, indent=2) + "\n"
    )


if __name__ == "__main__":
    asyncio.run(run(Path(sys.argv[1])))
