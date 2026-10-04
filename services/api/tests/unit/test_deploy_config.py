"""The production deployment files keep their hardening: compose, Dockerfiles, Caddy, the env template, the smoke test.

These read the committed files only (no Docker). `docker compose config`, hadolint, and the image builds run in CI and
in `make security`; this suite fails first when an edit drops a control.
"""

import importlib.util
import re
from pathlib import Path
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


def _env(service: str) -> dict[str, Any]:
    environment = SERVICES[service].get("environment", {})
    assert isinstance(environment, dict)
    return environment


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
    holders = {
        name for name in SERVICES if any("POSTGRES_ADMIN_PASSWORD" in str(value) for value in _env(name).values())
    }
    assert holders == OWNER_SERVICES
    assert "POSTGRES_ADMIN_PASSWORD" not in _env("api")


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
