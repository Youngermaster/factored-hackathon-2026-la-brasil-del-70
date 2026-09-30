# syntax=docker/dockerfile:1.7
# Production images for the API and the owner jobs, built from the repository root:
#   docker build -f services/api/Dockerfile --target api -t bank-agent-api .
#   docker build -f services/api/Dockerfile --target job -t bank-agent-job .
#
# Both keep the repository layout under /app (the settings resolve policies/, services/api/config/, and data/ from
# it), run as a non-root user, need no writable root filesystem (bytecode is compiled at build time), and carry no
# build tools: uv lives only in the build stages. The api image holds the bank-agent package with the litellm extra
# (never the ml extra), the synthetic policy pack, the price table, the published evaluation summaries, and a
# retrieval index built from the shipped pack (RETRIEVAL_INDEX_SOURCE=stored). The job image adds bank-data and the
# gold tables built from the committed sample, for migrations, the seed, and the retention purge.

ARG PYTHON_IMAGE=python:3.12.14-slim-trixie@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.11.17@sha256:03bdc89bb9798628846e60c3a9ad19006c8c3c724ccd2985a33145c039a0577b

FROM ${UV_IMAGE} AS uv

# ---------------------------------------------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS api-build
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
# The workspace metadata first, so dependency layers are cached until uv.lock changes.
COPY pyproject.toml uv.lock ./
COPY services/api/pyproject.toml services/api/README.md services/api/
COPY data_platform/pyproject.toml data_platform/README.md data_platform/
COPY ml/pyproject.toml ml/README.md ml/
COPY evals/pyproject.toml evals/README.md evals/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package bank-agent --extra litellm --no-install-workspace
COPY services/api/src services/api/src
COPY services/api/config services/api/config
COPY policies policies
COPY evals/reports/summaries evals/reports/summaries
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package bank-agent --extra litellm \
    && /app/.venv/bin/bank-agent index build

# ---------------------------------------------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS runtime-base
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --home-dir /nonexistent --no-create-home --shell /usr/sbin/nologin app
ENV PATH=/app/.venv/bin:${PATH} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp \
    LITELLM_LOCAL_MODEL_COST_MAP=True \
    APP_ENV=production \
    RETRIEVAL_INDEX_SOURCE=stored
WORKDIR /app

# ---------------------------------------------------------------------------------------------------------------
FROM runtime-base AS api
COPY --from=api-build --chown=root:root /app /app
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=5 \
    CMD ["python", "-c", "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2).status == 200 else 1)"]
# Workers come from WEB_CONCURRENCY and the trusted proxy from FORWARDED_ALLOW_IPS (uvicorn reads both).
CMD ["uvicorn", "bank_agent.asgi:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--no-server-header", "--no-access-log", "--timeout-graceful-shutdown", "20"]

# ---------------------------------------------------------------------------------------------------------------
FROM api-build AS job-build
ENV BANK_DATA_SOURCE=sample \
    BANK_DATA_DUCKDB_MEMORY_LIMIT=2GB \
    BANK_DATA_DUCKDB_THREADS=2
COPY data_platform data_platform
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package bank-data \
    && /app/.venv/bin/bank-data ingest --source sample \
    && /app/.venv/bin/bank-data build --source sample \
    && rm -rf data/warehouse-sample/dbt data_platform/dbt/target data_platform/dbt/logs

# ---------------------------------------------------------------------------------------------------------------
FROM runtime-base AS job
COPY --from=job-build --chown=root:root /app /app
USER 10001:10001
ENV BANK_DATA_SOURCE=sample
CMD ["bank-agent", "db", "upgrade"]
