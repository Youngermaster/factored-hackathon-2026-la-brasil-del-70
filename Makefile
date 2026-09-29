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
# Data source for the pipeline: sample (committed, offline) or s3 (organizer bucket). Empty means the
# BANK_DATA_SOURCE setting, which defaults to sample. See data_platform/README.md.
DATA_SOURCE ?=
SOURCE_FLAG := $(if $(DATA_SOURCE),--source $(DATA_SOURCE),)
SAMPLE_CUSTOMERS ?= 2000
SEED_CUSTOMERS ?= 200
BANK_DATA := $(UV_RUN) bank-data

.PHONY: help setup up down check lint format typecheck test-unit test-integration test-web env-check docs-check contracts \
	data-download pipeline pipeline-sample data-sample data-report lineage data-codegen analysis db-upgrade seed \
	policy-lock policy-catalog index eval-retrieval train promote openapi llm-smoke api-local-llm env

help: ## List the available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: ## Install Python and web dependencies and the git hooks
	uv sync --all-packages --extra eda-ui --frozen
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

env: ## Create .env from .env.example (only when absent) with freshly generated development secrets
	$(GUARD_PY) scripts/make_env.py

env-check: ## Report which variables the current configuration needs and whether each is set, never a value
	$(GUARD_PY) scripts/checks/check_env_keys.py

contracts: ## Regenerate the JSON Schemas in contracts/schemas from the Pydantic models
	$(UV_RUN) python scripts/generate_contracts.py

# Opt-in local language model (never used by check or CI). The litellm extra is installed on demand for these runs.
LLM_EXTRA_RUN := uv run --frozen --extra litellm --package bank-agent
LOCAL_LLM_MODEL ?= ollama/qwen2.5:7b-instruct
LOCAL_LLM_BASE ?= http://localhost:11434

llm-smoke: ## Opt-in: run the fixture prompts (es, pt, four workflows) against the configured live provider; never in check or CI
	$(LLM_EXTRA_RUN) python scripts/llm_smoke.py

api-local-llm: ## Opt-in: run the API on :8000 with the local Ollama model through LiteLLM (LOCAL_LLM_MODEL, LOCAL_LLM_BASE)
	LLM_PROVIDER=litellm LLM_PRIMARY_MODEL=$(LOCAL_LLM_MODEL) LLM_API_BASE=$(LOCAL_LLM_BASE) \
		$(LLM_EXTRA_RUN) uvicorn bank_agent.asgi:create_app --factory --host 127.0.0.1 --port 8000

openapi: ## Export contracts/openapi.json and regenerate the web API types (apps/web/src/shared/api/generated)
	$(UV_RUN) python scripts/export_openapi.py
	$(WEB) exec node tooling/generate-api-types.ts

policy-lock: ## Rewrite policies/versions.lock.yaml after a clause change (refuses a change without a version bump)
	$(UV_RUN) bank-agent policy lock

policy-catalog: ## Regenerate docs/policy/catalog.md from the policy pack and the credit catalog
	$(UV_RUN) bank-agent policy catalog

index: ## Build the retrieval index for the current pack under data/artifacts (DENSE=1 embeds too; needs the ml extra)
	$(UV_RUN) bank-agent index build $(if $(DENSE),--dense,)

eval-retrieval: ## Compare BM25, dense, and hybrid on the relevance judgments; writes docs/evaluation/retrieval.md
	MLFLOW_TRACKING_URI=$${MLFLOW_TRACKING_URI:-file:./mlruns} $(UV_RUN) bank-eval retrieval

train: ## Train, register as candidates, and evaluate the router, resolver, and risk estimator; writes docs/evaluation (resolver and risk need the s3 gold)
	$(UV_RUN) bank-ml router train
	$(UV_RUN) bank-ml router evaluate
	$(UV_RUN) bank-ml resolver train
	$(UV_RUN) bank-ml resolver evaluate
	$(UV_RUN) bank-ml risk train
	$(UV_RUN) bank-ml risk evaluate

promote: ## Move 'champion' to the candidates that win (router and resolver on dev, risk on test), recording APPROVED_BY (required)
	@test -n "$(APPROVED_BY)" || { echo "APPROVED_BY=<name> is required: promotion records who approved it"; exit 1; }
	$(UV_RUN) bank-ml router promote --approved-by "$(APPROVED_BY)"
	$(UV_RUN) bank-ml resolver promote --approved-by "$(APPROVED_BY)"
	$(UV_RUN) bank-ml risk promote --approved-by "$(APPROVED_BY)"

data-download: ## Incremental, manifest-driven download of the organizer bucket into data/warehouse (needs S3 credentials)
	$(BANK_DATA) ingest --source s3 --download-only

pipeline: ## Ingest, build, and test bronze, silver, gold (DATA_SOURCE=sample|s3; default BANK_DATA_SOURCE or sample)
	$(BANK_DATA) ingest $(SOURCE_FLAG)
	$(BANK_DATA) build $(SOURCE_FLAG)
	$(BANK_DATA) test $(SOURCE_FLAG)

pipeline-sample: ## Ingest, then build silver and gold for SAMPLE_CUSTOMERS customers chosen by a seeded hash
	$(BANK_DATA) ingest $(SOURCE_FLAG)
	$(BANK_DATA) build $(SOURCE_FLAG) --sample-customers $(SAMPLE_CUSTOMERS)
	$(BANK_DATA) test $(SOURCE_FLAG) --sample-customers $(SAMPLE_CUSTOMERS)

data-sample: ## Regenerate the committed, bounded, pseudonymized sample in data_platform/sample (reads the s3 warehouse)
	$(BANK_DATA) sample
	$(GUARD_PY) scripts/checks/check_data_sample.py

data-report: ## Write the data-quality report (docs/data/quality-report.md for the s3 source)
	$(BANK_DATA) report $(SOURCE_FLAG)

analysis: ## Demand evidence, pre-registered scores, figures, and labeling files (docs/analysis for the s3 source)
	$(BANK_DATA) analysis $(SOURCE_FLAG)

lineage: ## Run dbt docs generate and write the Mermaid lineage (docs/data/lineage.md for the s3 source)
	$(BANK_DATA) lineage $(SOURCE_FLAG)

data-codegen: ## Regenerate the dbt sources, silver contracts, and canonical seed from the table specs
	$(BANK_DATA) codegen

db-upgrade: ## Apply the PostgreSQL migrations as the owner role (reads .env through the service settings)
	$(UV_RUN) bank-agent db upgrade

seed: ## Migrate, then load the demo personas and SEED_CUSTOMERS customers from gold into the compose PostgreSQL
	$(BANK_DATA) seed $(SOURCE_FLAG) --customers $(SEED_CUSTOMERS)

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
	$(GUARD_PY) scripts/checks/check_data_sample.py
	$(UV_RUN) bank-data codegen --check
	$(GUARD_PY) scripts/checks/check_no_emoji.py
	scripts/checks/check_no_ai_attribution.sh
	gitleaks git --redact --no-banner .

.PHONY: eda eda-ui eda-setup
eda-setup: ## Install the local EDA engine and Streamlit viewer
	uv sync --all-packages --extra eda-ui --frozen

eda: ## Run or resume all EDA phases against local CSVs
	uv run --frozen --extra eda bank-data eda run

eda-ui: ## Open the local EDA viewer and sanitized laboratory
	uv run --frozen --extra eda-ui streamlit run data_platform/src/bank_data/eda/ui.py --server.address 127.0.0.1 --server.headless true --browser.gatherUsageStats false --theme.base light --theme.primaryColor '#346538' --theme.backgroundColor '#F7F6F3' --theme.secondaryBackgroundColor '#FFFFFF' --theme.textColor '#2F3437' --theme.font 'Helvetica Neue, sans-serif'
