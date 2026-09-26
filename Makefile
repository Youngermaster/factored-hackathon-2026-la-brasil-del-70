# Repository commands. `make help` lists what exists; phases add targets as they implement them.
# Prerequisites: uv, Node 24.15 or later with pnpm, Docker with Compose, pre-commit, and gitleaks.

SHELL := bash
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := help
MAKEFLAGS += --no-print-directory

UV_RUN := uv run --frozen
# The guard scripts are stdlib-only; this pins them to Python 3.12 without syncing the project environment.
GUARD_PY := uv run --no-project --python 3.12 python
WEB := pnpm --dir apps/web
PYTHON_SOURCES := services/api/src data_platform/src ml/src evals/src scripts
PROFILES ?=
PROFILE_FLAGS := $(foreach profile,$(PROFILES),--profile $(profile))

.PHONY: help setup up down check lint format typecheck test-unit test-integration test-web env-check docs-check contracts

help: ## List the available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install Python and web dependencies and the git hooks
	uv sync --all-packages --frozen
	$(WEB) install --frozen-lockfile
	pre-commit install --install-hooks

up: ## Start the dev stack; PROFILES="api web obs ml" adds profiles (reads .env)
	docker compose $(PROFILE_FLAGS) up -d --wait

down: ## Stop the dev stack, every profile
	docker compose --profile '*' down

lint: ## Ruff, ruff format check, import-linter, bandit, ESLint, Prettier check
	$(UV_RUN) ruff check .
	$(UV_RUN) ruff format --check .
	$(UV_RUN) lint-imports
	$(UV_RUN) bandit -q -c pyproject.toml -r $(PYTHON_SOURCES)
	$(WEB) run lint
	$(WEB) run format:check

format: ## Apply ruff fixes and formatting, ESLint fixes, and Prettier
	$(UV_RUN) ruff check --fix .
	$(UV_RUN) ruff format .
	$(WEB) exec eslint . --fix
	$(WEB) run format

typecheck: ## mypy (strict) and the TypeScript compiler
	$(UV_RUN) mypy
	$(UV_RUN) mypy conftest.py
	$(WEB) run typecheck

test-unit: ## Python unit tests (network disabled), coverage into .coverage.unit
	COVERAGE_FILE=.coverage.unit $(UV_RUN) pytest -m unit --cov --cov-report=

test-integration: ## Python integration tests against PostgreSQL (needs Docker), coverage into .coverage.integration
	COVERAGE_FILE=.coverage.integration $(UV_RUN) pytest -m integration --cov --cov-report=

test-web: ## Web tests with coverage
	$(WEB) run test:coverage

env-check: ## Report set or unset for every documented environment variable, never a value
	$(GUARD_PY) scripts/checks/check_env_keys.py

contracts: ## Regenerate the JSON Schemas in contracts/schemas from the Pydantic models
	$(UV_RUN) python scripts/generate_contracts.py

docs-check: ## Markdown lint and Mermaid validation
	apps/web/node_modules/.bin/markdownlint-cli2
	node scripts/checks/check_mermaid.mjs
	node --test 'scripts/checks/tests/*.test.mjs'

check: ## Everything: lint, types, boundaries, tests with coverage gates, docs, emoji, attribution, gitleaks
	@$(MAKE) lint
	@$(MAKE) typecheck
	rm -f .coverage .coverage.unit .coverage.integration coverage.json
	@$(MAKE) test-unit
	@$(MAKE) test-integration
	$(UV_RUN) coverage combine --keep -q .coverage.unit .coverage.integration
	$(UV_RUN) coverage json -q -o coverage.json
	$(GUARD_PY) scripts/checks/check_coverage_gates.py
	@$(MAKE) test-web
	@$(MAKE) docs-check
	$(GUARD_PY) scripts/checks/check_no_emoji.py
	scripts/checks/check_no_ai_attribution.sh
	gitleaks git --redact --no-banner .
