"""deploy/secrets_stage.py stages Key Vault or env-file secrets as owner-only files, and never shows a value (ADR 0037).

The Key Vault source runs against a scripted HTTP function, so these tests make no network call.
"""

import importlib.util
import json
import secrets
import stat
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType

import pytest

DEPLOY = Path(__file__).resolve().parents[4] / "deploy"


def _load() -> ModuleType:
    """Import the script by path; dataclasses resolve their annotations through ``sys.modules``."""
    spec = importlib.util.spec_from_file_location("deploy_secrets_stage", DEPLOY / "secrets_stage.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


stager = _load()
REQUIRED = [secret for secret in stager.SECRETS if secret.required]
OPTIONAL = [secret for secret in stager.SECRETS if not secret.required]


def _values() -> dict[str, str]:
    return {secret.variable: secrets.token_urlsafe(32) for secret in REQUIRED}


def _env_file(path: Path, values: Mapping[str, str]) -> Path:
    lines = [
        "# server env file",
        "SITE_ADDRESS=demo.example.org",
        *(f"{name}={value}" for name, value in values.items()),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class FakeAzure:
    """The metadata service and one vault, as HTTP answers; it records every request."""

    def __init__(
        self,
        vault_values: Mapping[str, str],
        *,
        token_failures: int = 0,
        status: int = 200,
        missing_status: int = 404,
    ) -> None:
        self.vault_values = dict(vault_values)
        self.token_failures = token_failures
        self.status = status
        self.missing_status = missing_status
        """403 models per-secret grants: a secret that does not exist has no grant, so the identity is refused."""
        self.requests: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, headers: Mapping[str, str]) -> tuple[int, bytes]:
        self.requests.append((url, dict(headers)))
        if url == stager.MANAGED_IDENTITY_URL:
            if self.token_failures:
                self.token_failures -= 1
                raise OSError("metadata service not ready")
            return 200, json.dumps({"access_token": "token-for-test"}).encode()
        if self.status != 200:
            return self.status, b""
        name = url.split("/secrets/", 1)[1].split("?", 1)[0]
        if name not in self.vault_values:
            return self.missing_status, b""
        return 200, json.dumps({"value": self.vault_values[name]}).encode()


def _vault_values(values: Mapping[str, str]) -> dict[str, str]:
    by_variable = {secret.variable: secret.vault_name for secret in stager.SECRETS}
    return {by_variable[name]: value for name, value in values.items()}


def test_the_env_file_source_stages_each_secret_for_each_consumer_only(tmp_path: Path) -> None:
    values = _values()
    dest = tmp_path / "secrets"

    exit_code = stager.main(
        [
            "stage",
            "--source",
            "env-file",
            "--env-file",
            str(_env_file(tmp_path / "env", values)),
            "--dest",
            str(dest),
            "--no-chown",
        ]
    )

    assert exit_code == 0
    assert sorted(path.name for path in (dest / "postgres").iterdir()) == [
        "POSTGRES_ADMIN_PASSWORD",
        "POSTGRES_APP_PASSWORD",
        "POSTGRES_SUPERUSER_PASSWORD",
    ]
    assert "POSTGRES_SUPERUSER_PASSWORD" not in {path.name for path in (dest / "app").iterdir()}
    assert (dest / "app" / "SESSION_SECRET").read_text(encoding="utf-8") == values["SESSION_SECRET"]
    assert (dest / "postgres" / "POSTGRES_APP_PASSWORD").read_text(encoding="utf-8") == values["POSTGRES_APP_PASSWORD"]
    assert (dest / "app" / "LLM_API_KEY_PRIMARY").read_text(encoding="utf-8") == ""
    assert (dest / "grafana" / "GRAFANA_ADMIN_PASSWORD").read_text(encoding="utf-8") == ""


def test_files_are_owner_read_only_and_directories_unlistable(tmp_path: Path) -> None:
    dest = tmp_path / "secrets"
    stager.stage({secret.variable: "x" * 40 for secret in stager.SECRETS}, dest, chown=False)

    for path in dest.rglob("*"):
        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == (0o711 if path.is_dir() else 0o400), path
    assert not list(dest.rglob(".*.tmp"))


def test_a_missing_required_secret_stops_before_any_file_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    values = _values()
    del values["CSRF_SECRET"]
    dest = tmp_path / "secrets"

    exit_code = stager.main(
        [
            "stage",
            "--source",
            "env-file",
            "--env-file",
            str(_env_file(tmp_path / "env", values)),
            "--dest",
            str(dest),
            "--no-chown",
        ]
    )

    assert exit_code == 1
    assert not dest.exists()
    assert "required secrets missing from env-file: CSRF_SECRET" in capsys.readouterr().err


def test_the_key_vault_source_uses_the_managed_identity_token(tmp_path: Path) -> None:
    values = _values()
    azure = FakeAzure(_vault_values(values) | {"llm-api-key-primary": "provider-key-for-test-" + "k" * 20})
    source = stager.KeyVaultSource("kv-bank-agent", get=azure, sleep=lambda _: None)

    collected = stager.collect(source)
    stager.stage(collected, tmp_path, chown=False)

    token_requests = [headers for url, headers in azure.requests if url == stager.MANAGED_IDENTITY_URL]
    vault_requests = [(url, headers) for url, headers in azure.requests if url != stager.MANAGED_IDENTITY_URL]
    assert token_requests == [{"Metadata": "true"}]
    assert all(url.startswith("https://kv-bank-agent.vault.azure.net/secrets/") for url, _ in vault_requests)
    assert all(headers == {"Authorization": "Bearer token-for-test"} for _, headers in vault_requests)
    assert (tmp_path / "app" / "SESSION_SECRET").read_text(encoding="utf-8") == values["SESSION_SECRET"]
    assert (tmp_path / "app" / "LLM_API_KEY_PRIMARY").read_text(encoding="utf-8").startswith("provider-key-for-test-")
    assert (tmp_path / "app" / "LLM_API_KEY_FALLBACK").read_text(encoding="utf-8") == ""


def test_the_metadata_service_is_retried_while_it_starts(tmp_path: Path) -> None:
    azure = FakeAzure(_vault_values(_values()), token_failures=3)
    waits: list[float] = []

    stager.collect(stager.KeyVaultSource("kv-bank-agent", get=azure, sleep=waits.append))

    assert len(waits) == 3


def test_a_forbidden_secret_is_reported_by_name_and_status_only(capsys: pytest.CaptureFixture[str]) -> None:
    azure = FakeAzure({}, status=403)

    with pytest.raises(stager.StageError) as raised:
        stager.collect(stager.KeyVaultSource("kv-bank-agent", get=azure, sleep=lambda _: None))

    assert str(raised.value) == (
        "Key Vault answered HTTP 403 for secret postgres-superuser-password "
        "(grant the VM identity Key Vault Secrets User on it)"
    )
    assert "token-for-test" not in str(raised.value)


def test_optional_secrets_without_a_per_secret_grant_are_staged_empty(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    values = _values()
    azure = FakeAzure(_vault_values(values), missing_status=403)

    stager.stage(
        stager.collect(stager.KeyVaultSource("kv-bank-agent", get=azure, sleep=lambda _: None)), tmp_path, chown=False
    )

    assert (tmp_path / "app" / "LLM_API_KEY_PRIMARY").read_text(encoding="utf-8") == ""
    assert (tmp_path / "grafana" / "GRAFANA_ADMIN_PASSWORD").read_text(encoding="utf-8") == ""
    assert (tmp_path / "app" / "SESSION_SECRET").read_text(encoding="utf-8") == values["SESSION_SECRET"]
    assert "llm-api-key-primary: not readable by this identity (HTTP 403); optional, staged empty" in (
        capsys.readouterr().err
    )


def test_a_required_secret_without_a_grant_still_stops_the_run() -> None:
    values = _values()
    del values["CSRF_SECRET"]
    azure = FakeAzure(_vault_values(values), missing_status=403)

    with pytest.raises(stager.StageError) as raised:
        stager.collect(stager.KeyVaultSource("kv-bank-agent", get=azure, sleep=lambda _: None))

    assert str(raised.value) == (
        "Key Vault answered HTTP 403 for secret csrf-secret (grant the VM identity Key Vault Secrets User on it)"
    )


def test_required_secrets_missing_from_the_vault_are_named_by_their_vault_names() -> None:
    values = _values()
    del values["SESSION_SECRET"]

    with pytest.raises(stager.StageError) as raised:
        stager.collect(
            stager.KeyVaultSource("kv-bank-agent", get=FakeAzure(_vault_values(values)), sleep=lambda _: None)
        )

    assert str(raised.value) == "required secrets missing from keyvault: session-secret"


@pytest.mark.parametrize("vault", ["", "kv", "1vault", "kv_bank", "kv-bank-agent-name-is-too-long", "kv.evil.example"])
def test_invalid_vault_names_are_refused(vault: str) -> None:
    with pytest.raises(stager.StageError):
        stager.KeyVaultSource(vault, get=FakeAzure({}), sleep=lambda _: None)


def test_staging_again_replaces_each_file_with_the_new_version(tmp_path: Path) -> None:
    first, second = _values(), _values()
    stager.stage(first | {secret.variable: "" for secret in OPTIONAL}, tmp_path, chown=False)

    stager.stage(second | {secret.variable: "" for secret in OPTIONAL}, tmp_path, chown=False)

    assert (tmp_path / "app" / "CSRF_SECRET").read_text(encoding="utf-8") == second["CSRF_SECRET"]


def test_check_reads_metadata_only_and_names_each_problem(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    values = _values() | {secret.variable: "" for secret in OPTIONAL}
    stager.stage(values, tmp_path, chown=False)
    assert stager.main(["check", "--dest", str(tmp_path), "--no-chown"]) == 0
    (tmp_path / "app" / "SESSION_SECRET").unlink()
    (tmp_path / "postgres" / "POSTGRES_APP_PASSWORD").chmod(0o644)
    csrf = tmp_path / "app" / "CSRF_SECRET"
    csrf.chmod(0o600)
    csrf.write_text("", encoding="utf-8")
    csrf.chmod(0o400)

    exit_code = stager.main(["check", "--dest", str(tmp_path), "--no-chown"])

    assert exit_code == 1
    assert capsys.readouterr().err.splitlines()[-3:] == [
        "secrets-stage: postgres/POSTGRES_APP_PASSWORD must be mode 0400",
        "secrets-stage: app/SESSION_SECRET is missing",
        "secrets-stage: app/CSRF_SECRET is empty",
    ]


def test_staging_for_containers_needs_root(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = stager.main(
        [
            "stage",
            "--source",
            "env-file",
            "--env-file",
            str(_env_file(tmp_path / "env", _values())),
            "--dest",
            str(tmp_path / "secrets"),
        ],
        geteuid=lambda: 1000,
    )

    assert exit_code == 1
    assert "run as root (sudo)" in capsys.readouterr().err
    assert not (tmp_path / "secrets").exists()


def test_no_value_ever_reaches_the_output(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    values = _values()

    stager.main(
        [
            "stage",
            "--source",
            "env-file",
            "--env-file",
            str(_env_file(tmp_path / "env", values)),
            "--dest",
            str(tmp_path / "secrets"),
            "--no-chown",
        ]
    )
    stager.main(["check", "--dest", str(tmp_path / "secrets"), "--no-chown"])

    output = capsys.readouterr()
    expected_files = sum(len(secret.consumers) for secret in stager.SECRETS)
    assert f"staged {expected_files} files from env-file" in output.err
    for value in values.values():
        assert value not in output.out + output.err


def test_requests_never_follow_a_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    """urllib replays the Authorization header on a redirect, so the bearer token could reach another host."""
    handlers: list[object] = []

    class Opener:
        def open(self, request: object, timeout: float) -> object:
            raise stager.urllib.error.HTTPError("https://kv.example", 302, "Found", {}, None)

    def build_opener(*given: object) -> Opener:
        handlers.extend(given)
        return Opener()

    monkeypatch.setattr(stager.urllib.request, "build_opener", build_opener)

    status, body = stager.http_get("https://kv-bank-agent.vault.azure.net/secrets/csrf-secret", {})

    assert (status, body) == (302, b"")
    refusing = [handler for handler in handlers if isinstance(handler, stager._NoRedirect)]
    assert len(refusing) == 1
    assert refusing[0].redirect_request() is None


def test_a_redirect_from_the_vault_stops_the_run_by_status() -> None:
    azure = FakeAzure({}, status=302)

    with pytest.raises(stager.StageError) as raised:
        stager.collect(stager.KeyVaultSource("kv-bank-agent", get=azure, sleep=lambda _: None))

    assert str(raised.value) == "Key Vault answered HTTP 302 for secret postgres-superuser-password"


def test_a_network_error_reaching_the_vault_is_named_without_a_traceback() -> None:
    def get(url: str, headers: Mapping[str, str]) -> tuple[int, bytes]:
        if url == stager.MANAGED_IDENTITY_URL:
            return 200, json.dumps({"access_token": "token-for-test"}).encode()
        raise TimeoutError("timed out")

    with pytest.raises(stager.StageError) as raised:
        stager.collect(stager.KeyVaultSource("kv-bank-agent", get=get, sleep=lambda _: None))

    assert str(raised.value) == ("Key Vault could not be reached for secret postgres-superuser-password (TimeoutError)")


def test_a_symbolic_link_destination_is_refused(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(mode=0o755)
    link = tmp_path / "secrets"
    link.symlink_to(elsewhere, target_is_directory=True)

    with pytest.raises(stager.StageError, match="symbolic link"):
        stager.stage(_values(), link, chown=False)

    assert stat.S_IMODE(elsewhere.stat().st_mode) == 0o755
    assert not list(elsewhere.iterdir())


def test_a_symbolic_link_consumer_directory_is_refused(tmp_path: Path) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir(mode=0o755)
    dest = tmp_path / "secrets"
    dest.mkdir()
    (dest / "postgres").symlink_to(elsewhere, target_is_directory=True)
    values = _values() | {secret.variable: "" for secret in OPTIONAL}

    with pytest.raises(stager.StageError, match="symbolic link"):
        stager.stage(values, dest, chown=False)

    assert not list(elsewhere.iterdir())
    assert stat.S_IMODE(elsewhere.stat().st_mode) == 0o755


def test_a_relative_destination_is_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = stager.main(
        [
            "stage",
            "--source",
            "env-file",
            "--env-file",
            str(_env_file(tmp_path / "env", _values())),
            "--dest",
            "relative/secrets",
            "--no-chown",
        ]
    )

    assert exit_code == 1
    assert "the destination must be an absolute path" in capsys.readouterr().err
