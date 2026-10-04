"""Load test for the bank agent API (docs/operations/capacity.md).

Each simulated customer signs in with a demo persona (demo mode shows the one-time code), opens a conversation, and
sends turns from one workflow, chosen with the phase 04 demand shares (account inquiry 31.9, card support 20.0,
dispute 19.1, credit 7.3 percent of contacts, normalized). Two in five conversations are in Portuguese. Every turn is
read only or stops before a write (no card is blocked, no case or intake is recorded), so the run can repeat on the
same database. Turn requests are named ``turn <workflow>`` so Locust reports p50 and p95 per workflow.

Run it against a local API (fake model, raised rate limits), for example:

    uv run --with locust==2.46.6 locust -f scripts/load/locustfile.py --headless \\
        --host http://127.0.0.1:8015 -u 20 -r 5 -t 60s --csv reports/load/local

Against the production stack behind Caddy's local TLS mode, set ``LOAD_CA_BUNDLE`` to Caddy's root certificate and
raise the rate limits in the server env file first (every simulated customer comes from one address).

Synthetic traffic only: the texts are team-written fixtures, and the personas are seeded demo personas that the
committed sample provides (``make seed`` with the default source); ``acc-co-payments`` has no customer in the sample.
"""

import os
import random
import uuid
from typing import Any, Final

from locust import HttpUser, between, task

# (persona, language, messages): each message is one turn in the same conversation.
SCRIPTS: Final[dict[str, list[tuple[str, str, list[str]]]]] = {
    "account_inquiry": [
        ("acc-mx-accounts", "es", ["¿Cuál es mi saldo?", "¿Y el de mi cuenta de ahorro?"]),
        ("acc-mx-accounts", "es", ["¿Cómo va mi último pago?"]),
        ("acc-mx-accounts", "pt", ["Qual é o meu saldo?"]),
        ("acc-mx-accounts", "pt", ["Qual é o status do meu pagamento?"]),
    ],
    "card_support": [
        ("crd-mx-two-cards", "es", ["¿Está bloqueada mi tarjeta?", "la de crédito"]),
        ("crd-co-declined", "es", ["¿Mi tarjeta está activa?"]),
        ("crd-mx-two-cards", "pt", ["Meu cartão está bloqueado?", "o de crédito"]),
    ],
    "dispute": [
        ("dsp-mx-open-case", "es", ["¿Cómo va mi reclamación?"]),
        ("dsp-co-unrecognized", "es", ["No reconozco un cargo en mi tarjeta"]),
        ("dsp-mx-open-case", "pt", ["Como está a minha contestação?"]),
    ],
    "credit": [
        ("cre-mx-complete", "es", ["¿Qué condiciones tiene el préstamo personal?"]),
        ("cre-mx-complete", "es", ["¿Califico para un préstamo personal de 50 mil pesos a 24 meses?"]),
        ("cre-mx-complete", "pt", ["Quais produtos de crédito vocês têm?"]),
    ],
}
PORTUGUESE_SHARE: Final = 0.4
CA_BUNDLE: Final = os.environ.get("LOAD_CA_BUNDLE", "")
"""A CA certificate to trust, for a stack behind Caddy's local TLS mode (the production stack tested locally)."""


class _Customer(HttpUser):
    """One simulated customer: one persona and language for the whole run, conversations from one workflow."""

    abstract = True
    workflow = ""
    wait_time = between(1, 3)

    def on_start(self) -> None:
        if CA_BUNDLE:
            self.client.verify = CA_BUNDLE
        scripts = SCRIPTS[self.workflow]
        wanted = "pt" if random.random() < PORTUGUESE_SHARE else "es"  # noqa: S311  # nosec B311
        self.script = random.choice([s for s in scripts if s[1] == wanted] or scripts)  # noqa: S311  # nosec B311
        self.csrf = self.client.get("/v1/auth/csrf", name="auth csrf").json()["csrf_token"]
        started = self._post("/v1/auth/start", {"kind": "persona", "persona_id": self.script[0]}, "auth start").json()
        verified = self._post(
            "/v1/auth/verify", {"challenge_id": started["challenge_id"], "code": started["demo_code"]}, "auth verify"
        ).json()
        self.csrf = verified["csrf_token"]

    def _post(self, path: str, body: dict[str, Any] | None = None, name: str | None = None) -> Any:
        return self.client.post(path, json=body, headers={"X-CSRF-Token": self.csrf}, name=name or path)

    @task
    def conversation(self) -> None:
        created = self._post("/v1/conversations", name="conversation open")
        conversation = created.json()["conversation_id"]
        for text in self.script[2]:
            body = {"turn_id": str(uuid.uuid4()), "text": text}
            with self.client.post(
                f"/v1/conversations/{conversation}/turns",
                json=body,
                headers={"X-CSRF-Token": self.csrf},
                name=f"turn {self.workflow}",
                catch_response=True,
            ) as response:
                if response.status_code != 200:
                    response.failure(f"status {response.status_code}")


class AccountInquiryCustomer(_Customer):
    workflow = "account_inquiry"
    weight = 41


class CardSupportCustomer(_Customer):
    workflow = "card_support"
    weight = 26


class DisputeCustomer(_Customer):
    workflow = "dispute"
    weight = 24


class CreditCustomer(_Customer):
    workflow = "credit"
    weight = 9
