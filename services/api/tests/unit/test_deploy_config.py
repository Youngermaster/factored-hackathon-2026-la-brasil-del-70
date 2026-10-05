"""The production deployment files keep their hardening: compose, Dockerfiles, Caddy, the env template, the smoke test.

These read the committed files only (no Docker). `docker compose config`, hadolint, and the image builds run in CI and
in `make security`; this suite fails first when an edit drops a control.
"""

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[4]
DEPLOY = ROOT / "deploy"
COMPOSE: dict[str, Any] = yaml.safe_load((DEPLOY / "compose.prod.yml").read_text(encoding="utf-8"))
SERVICES: dict[str, dict[str, Any]] = COMPOSE["services"]
WRITABLE_ROOT = {"ollama"}
"""Services allowed a writable root filesystem, each with the reason in a compose comment."""
OWNER_SERVICES = {"postgres", "migrate", "seed", "purge"}
LOOPBACK_PORTS = {"grafana", "jaeger"}
OWNER_JOB_SECRETS = {"POSTGRES_ADMIN_PASSWORD", "SESSION_SECRET"}
EXPECTED_SECRETS: dict[str, set[str]] = {
    "api": {"POSTGRES_APP_PASSWORD", "SESSION_SECRET", "CSRF_SECRET", "LLM_API_KEY_PRIMARY", "LLM_API_KEY_FALLBACK"},
    "migrate": OWNER_JOB_SECRETS,
    "seed": OWNER_JOB_SECRETS,
    "purge": OWNER_JOB_SECRETS,
    "postgres": {"POSTGRES_SUPERUSER_PASSWORD", "POSTGRES_ADMIN_PASSWORD", "POSTGRES_APP_PASSWORD"},
    "grafana": {"GRAFANA_ADMIN_PASSWORD"},
}
"""The secret files each service mounts (ADR 0037); every other service mounts none."""
SECRET_CONSUMER = {
    "api": "app",
    "migrate": "app",
    "seed": "app",
    "purge": "app",
    "postgres": "postgres",
    "grafana": "grafana",
}
"""The stager directory, and so the container user, whose files each service mounts."""
SECRETS_HOST_DIR = "${SECRETS_HOST_DIR:-/run/bank-agent/secrets}"


def _load_stager() -> ModuleType:
    spec = importlib.util.spec_from_file_location("deploy_secrets_stage", DEPLOY / "secrets_stage.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


STAGER = _load_stager()
SECRET_VARIABLES = {secret.variable for secret in STAGER.SECRETS}


def _env(service: str) -> dict[str, Any]:
    environment = SERVICES[service].get("environment", {})
    assert isinstance(environment, dict)
    return environment


def _mounted(service: str) -> dict[str, str]:
    """Secret target name to compose secret name, for one service."""
    return {entry["target"]: entry["source"] for entry in SERVICES[service].get("secrets", [])}


@pytest.mark.parametrize("name", sorted(SERVICES))
def test_every_service_drops_privileges_and_has_limits_and_rotated_logs(name: str) -> None:
    service = SERVICES[name]
    assert "no-new-privileges:true" in service["security_opt"]
    assert service["cap_drop"] == ["ALL"]
    assert "cap_add" not in service
    assert service.get("privileged") is not True
    limits = service["deploy"]["resources"]["limits"]
    assert limits["cpus"]
    assert limits["memory"]
    assert service["logging"]["options"]["max-size"] == "10m"
    if name not in WRITABLE_ROOT:
        assert service["read_only"] is True


@pytest.mark.parametrize("name", sorted(SERVICES))
def test_only_the_web_edge_publishes_public_ports(name: str) -> None:
    ports = [str(port) for port in SERVICES[name].get("ports", [])]
    if name == "web":
        assert ports == ["${HTTP_PORT:-80}:80", "${HTTPS_PORT:-443}:443", "${HTTPS_PORT:-443}:443/udp"]
    elif name in LOOPBACK_PORTS:
        assert ports
        assert all(port.startswith("127.0.0.1:") for port in ports)
    else:
        assert ports == []


def test_postgres_stays_on_the_internal_network_with_the_production_roles() -> None:
    postgres = SERVICES["postgres"]
    assert postgres["networks"] == ["backend"]
    assert COMPOSE["networks"]["backend"]["internal"] is True
    assert postgres["user"] == "70:70"
    assert "./postgres/init-production:/docker-entrypoint-initdb.d:ro" in postgres["volumes"]
    assert _env("postgres")["POSTGRES_USER"] == "postgres"


def test_the_api_trusts_proxy_headers_from_the_web_container_only() -> None:
    web_address = SERVICES["web"]["networks"]["edge"]["ipv4_address"]
    environment = _env("api")
    assert environment["FORWARDED_ALLOW_IPS"] == web_address
    assert environment["RATE_LIMIT_BACKEND"] == "postgres"
    assert environment["APP_ENV"] == "production"
    assert SERVICES["web"]["sysctls"] == {"net.ipv4.ip_unprivileged_port_start": 0}


def test_the_owner_password_reaches_the_owner_jobs_and_postgres_only() -> None:
    holders = {name for name in SERVICES if "POSTGRES_ADMIN_PASSWORD" in _mounted(name)}
    assert holders == OWNER_SERVICES
    assert "POSTGRES_ADMIN_PASSWORD" not in _mounted("api")


@pytest.mark.parametrize("name", sorted(SERVICES))
def test_each_service_mounts_only_the_secrets_it_needs(name: str) -> None:
    assert set(_mounted(name)) == EXPECTED_SECRETS.get(name, set())


@pytest.mark.parametrize("name", sorted(SERVICES))
def test_no_secret_travels_in_an_environment_variable(name: str) -> None:
    environment = _env(name)
    assert not SECRET_VARIABLES & set(environment), name
    for value in environment.values():
        assert not {variable for variable in SECRET_VARIABLES if "${" + variable in str(value)}, (name, value)


def test_every_mounted_secret_is_a_file_the_stager_writes_for_that_container_user() -> None:
    declared = set()
    for name in SERVICES:
        consumer = SECRET_CONSUMER.get(name)
        for target, source in _mounted(name).items():
            assert COMPOSE["secrets"][source]["file"] == f"{SECRETS_HOST_DIR}/{consumer}/{target}", source
            declared.add((consumer, target))
    staged = {(consumer, secret.variable) for secret in STAGER.SECRETS for consumer in secret.consumers}
    assert declared == staged
    assert SERVICES["postgres"]["user"] == "{}:{}".format(*STAGER.CONSUMERS["postgres"])
    dockerfile = (ROOT / "services/api/Dockerfile").read_text(encoding="utf-8")
    assert set(re.findall(r"^USER (\S+)$", dockerfile, flags=re.MULTILINE)) == {
        "{}:{}".format(*STAGER.CONSUMERS["app"])
    }


def test_services_read_their_secrets_from_the_mounted_files() -> None:
    for name in ("api", "migrate", "seed", "purge"):
        assert _env(name)["SECRETS_DIR"] == "/run/secrets"
    assert "POSTGRES_PASSWORD" not in _env("postgres")
    # (service, variable naming a file, the mounted secret it must name)
    file_variables = [
        ("postgres", "POSTGRES_PASSWORD_FILE", "POSTGRES_SUPERUSER_PASSWORD"),
        ("postgres", "POSTGRES_OWNER_PASSWORD_FILE", "POSTGRES_ADMIN_PASSWORD"),
        ("postgres", "POSTGRES_APP_PASSWORD_FILE", "POSTGRES_APP_PASSWORD"),
        ("grafana", "GF_SECURITY_ADMIN_PASSWORD__FILE", "GRAFANA_ADMIN_PASSWORD"),
    ]
    for service, variable, mounted in file_variables:
        assert _env(service)[variable] == f"/run/secrets/{mounted}"
        assert mounted in _mounted(service)
    init = (DEPLOY / "postgres" / "init-production" / "10-roles.sh").read_text(encoding="utf-8")
    assert 'cat "$POSTGRES_OWNER_PASSWORD_FILE"' in init
    assert 'cat "$POSTGRES_APP_PASSWORD_FILE"' in init


def test_the_azure_scripts_use_the_stager_vault_names() -> None:
    provision = (DEPLOY / "azure" / "provision.sh").read_text(encoding="utf-8")
    for secret in STAGER.SECRETS:
        assert secret.vault_name in provision, secret.vault_name
    # keyvault-secrets.sh lists the variables and derives each vault name: lower case, dashes for underscores.
    manager = (DEPLOY / "azure" / "keyvault-secrets.sh").read_text(encoding="utf-8")
    (listed,) = re.findall(r"^VARIABLES=\(([^)]*)\)", manager, flags=re.MULTILINE)
    assert listed.split() == [secret.variable for secret in STAGER.SECRETS]
    assert "tr '[:upper:]' '[:lower:]' | tr '_' '-'" in manager
    for secret in STAGER.SECRETS:
        assert secret.vault_name == secret.variable.lower().replace("_", "-")


BASH_4_ONLY = re.compile(r"declare -A|\bmapfile\b|\breadarray\b|\$\{[A-Za-z_]+(,,|\^\^)\}|&>>")


@pytest.mark.parametrize("script", sorted(path.relative_to(DEPLOY).as_posix() for path in DEPLOY.rglob("*.sh")))
def test_deploy_scripts_run_on_the_macos_default_bash(script: str) -> None:
    """Administrators run these from macOS too, whose /usr/bin/env bash is 3.2: no bash 4 features."""
    text = (DEPLOY / script).read_text(encoding="utf-8")
    assert not BASH_4_ONLY.search(text), script


def test_key_vault_init_never_mistakes_a_failed_lookup_for_a_missing_secret() -> None:
    """A transient error read as "absent" would store a new database password that PostgreSQL does not hold."""
    manager = (DEPLOY / "azure" / "keyvault-secrets.sh").read_text(encoding="utf-8")
    init = manager.split("cmd_init() {", 1)[1].split("\n}", 1)[0]
    assert init.index("load_names") < init.index("exists")
    assert 'az keyvault secret list --vault-name "${VAULT}" --query "[].name" --output tsv)" ||' in manager
    assert "az keyvault secret show" not in manager
    assert "refusing to store an empty value" in manager


def test_the_boot_unit_stages_from_key_vault_with_the_root_owned_copy_before_docker() -> None:
    unit = (DEPLOY / "azure" / "bank-agent-secrets.service").read_text(encoding="utf-8")
    assert "Before=docker.service" in unit
    assert "After=network-online.target" in unit
    (exec_start,) = re.findall(r"^ExecStart=(.+)$", unit, flags=re.MULTILINE)
    assert exec_start.startswith("/usr/bin/python3 /usr/local/lib/bank-agent/secrets_stage.py stage --source keyvault")
    assert exec_start.endswith(f"--dest {STAGER.DEFAULT_DEST}")
    assert "RuntimeDirectory=bank-agent" in unit
    assert "RuntimeDirectoryMode=0711" in unit


def test_prod_sh_stages_the_secrets_before_every_start() -> None:
    script = (DEPLOY / "prod.sh").read_text(encoding="utf-8")
    up = script.split("cmd_up() {", 1)[1].split("\n}", 1)[0]
    assert up.index("cmd_stage_secrets") < up.index("cmd_check") < up.index("compose up")
    assert "with SECRETS_SOURCE=keyvault these belong in Key Vault" in script


@pytest.mark.parametrize("name", sorted(SERVICES))
def test_third_party_images_are_pinned_by_digest(name: str) -> None:
    image = str(SERVICES[name]["image"])
    if image.startswith("bank-agent-"):
        assert image.endswith(":${IMAGE_TAG:-local}")
    else:
        assert re.search(r"@sha256:[0-9a-f]{64}$", image), image


def test_every_compose_variable_is_in_the_env_template_without_a_value() -> None:
    compose_text = (DEPLOY / "compose.prod.yml").read_text(encoding="utf-8")
    used = set(re.findall(r"\$\{([A-Z][A-Z0-9_]*)", compose_text)) - {"IMAGE_TAG"}
    template = (DEPLOY / ".env.production.example").read_text(encoding="utf-8").splitlines()
    assignments = [line for line in template if re.match(r"^[A-Z][A-Z0-9_]*=", line)]
    listed = {line.split("=", 1)[0] for line in assignments}
    assert used <= listed, sorted(used - listed)
    assert all(line.endswith("=") for line in assignments)


@pytest.mark.parametrize("dockerfile", ["services/api/Dockerfile", "apps/web/Dockerfile"])
def test_images_pin_their_bases_run_as_non_root_and_check_health(dockerfile: str) -> None:
    text = (ROOT / dockerfile).read_text(encoding="utf-8")
    bases = re.findall(r"^ARG [A-Z_]+_IMAGE=(\S+)$", text, flags=re.MULTILINE)
    assert bases
    assert all(re.search(r"@sha256:[0-9a-f]{64}$", base) for base in bases)
    users = re.findall(r"^USER (\S+)$", text, flags=re.MULTILINE)
    assert users
    assert all(user.split(":")[0] not in {"0", "root"} for user in users)
    assert "HEALTHCHECK" in text


def test_the_api_image_ships_the_price_table_and_a_stored_index_without_the_ml_extra() -> None:
    text = (ROOT / "services/api/Dockerfile").read_text(encoding="utf-8")
    assert "COPY services/api/config services/api/config" in text
    assert "bank-agent index build" in text
    assert "RETRIEVAL_INDEX_SOURCE=stored" in text
    assert "--extra ml" not in text
    assert "--no-access-log" in text


def test_the_spa_csp_allows_no_inline_script_and_only_nonced_styles() -> None:
    caddyfile = (DEPLOY / "caddy" / "Caddyfile").read_text(encoding="utf-8")
    (policy,) = re.findall(r'Content-Security-Policy "([^"]+)"', caddyfile)
    directives = {part.split()[0]: " ".join(part.split()[1:]) for part in policy.split(";")}
    assert directives["default-src"] == "'none'"
    assert directives["script-src"] == "'self'"
    assert directives["style-src"] == "'self' 'nonce-{http.request.uuid}'"
    assert directives["frame-ancestors"] == "'none'"
    assert "unsafe" not in policy
    assert "data:" not in policy
    assert "admin off" in caddyfile


def test_the_smoke_test_covers_every_workflow_in_both_languages() -> None:
    spec = importlib.util.spec_from_file_location("smoke_test", DEPLOY / "smoke_test.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    workflows = {flow.workflow for flow in module.FLOWS}
    assert workflows == {"account_inquiry", "card_support", "dispute", "credit", None}
    languages = {flow.name.rsplit("(", 1)[1].rstrip(")") for flow in module.FLOWS}
    assert languages == {"es", "pt"}
    assert any(flow.outcomes == frozenset({"abstained"}) for flow in module.FLOWS)


def test_qdrant_is_an_opt_in_internal_service_with_a_read_only_root_and_a_health_check() -> None:
    qdrant = SERVICES["qdrant"]
    assert qdrant["profiles"] == ["rag"]
    assert re.fullmatch(r"qdrant/qdrant:v[0-9.]+-unprivileged@sha256:[0-9a-f]{64}", qdrant["image"])
    assert qdrant["user"] == "1000:1000"
    assert qdrant["read_only"] is True
    assert qdrant["networks"] == ["backend"]
    assert COMPOSE["networks"]["backend"].get("internal") is True
    assert "ports" not in qdrant
    assert "secrets" not in qdrant
    assert qdrant["deploy"]["resources"]["limits"]["memory"] == "512M"
    assert qdrant["environment"]["QDRANT__TELEMETRY_DISABLED"] == "true"
    assert set(qdrant["volumes"]) == {"qdrant-storage:/qdrant/storage", "qdrant-snapshots:/qdrant/snapshots"}
    assert {entry.split(":", 1)[0] for entry in qdrant["tmpfs"]} == {"/tmp", "/qdrant/init"}  # noqa: S108
    assert qdrant["environment"]["QDRANT_INIT_FILE_PATH"].startswith("/qdrant/init/")
    test = " ".join(qdrant["healthcheck"]["test"])
    assert "/dev/tcp/127.0.0.1/6333" in test
    assert "/readyz" in test


def test_the_api_selects_bm25_unless_the_rag_settings_are_given() -> None:
    environment = _env("api")
    assert environment["RETRIEVAL_RETRIEVER"] == "${RETRIEVAL_RETRIEVER:-bm25}"
    assert environment["RETRIEVAL_QDRANT_URL"] == "${RETRIEVAL_QDRANT_URL:-}"
    assert "qdrant" not in SERVICES["api"].get("depends_on", {})


def test_prod_sh_starts_and_stops_the_rag_profile() -> None:
    script = (DEPLOY / "prod.sh").read_text(encoding="utf-8")
    assert '[[ "${RAG:-0}" == "1" ]] && flags+=(--profile rag)' in script
    assert script.count("--profile ollama --profile rag") == 2
