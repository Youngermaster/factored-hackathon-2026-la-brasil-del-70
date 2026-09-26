# bank_agent.domain

## Responsibility

The domain layer holds the business vocabulary of the dispute workflow: entities, value objects, enums, and typed domain errors. It is pure. It performs no I/O, reads no configuration, and imports no framework, database, HTTP, or model library.

Examples of what belongs here (added from phase 02): a `Money` value object with a `Decimal` amount and an explicit currency (never floats), case and dispute entities, identifiers as value objects, and errors such as a dispute filed after its window closed.

## Who may import it

Every other layer. It imports nothing from `bank_agent` except other `domain` modules.

import-linter enforces this with two contracts: the layers contract (nothing below `domain`) and the pure-core contract (no `fastapi`, `sqlalchemy`, `httpx`, `boto3`, or `litellm`).

## How to extend

- Add an entity or value object as a Pydantic model or a frozen dataclass, with invariants validated at construction.
- Add a typed error as a subclass of the domain base error. Register it in `bank_agent/api/problems.py` so it maps to a problem type in one place.
- Keep time and identifiers out: they come from the `Clock` and `IdGenerator` ports, passed in by the application layer.

## How to test

Unit tests under `services/api/tests/unit/domain/`, with Hypothesis property tests for invariants such as money arithmetic. Coverage gate: 90% line coverage.
