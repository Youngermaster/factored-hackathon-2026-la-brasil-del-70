"""`deploy/prod.sh check` refuses an empty staged key file for a hosted model or an enabled Langfuse export.

The optional key files are staged empty when a secret is not set or the VM may not read it, and an API started with an
enabled hosted model or Langfuse export and an empty key refuses its settings. prod.sh runs for real under bash with
the env-file source, `SECRETS_NO_CHOWN=1` (no root), and a fake `docker` first on PATH, so these tests need no Docker,
network, or Key Vault. They also pin that the refusal names the file and never prints a value.
"""

import os
import secrets
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
PROD_SH = ROOT / "deploy" / "prod.sh"
REQUIRED_SECRETS = ("POSTGRES_SUPERUSER_PASSWORD", "POSTGRES_ADMIN_PASSWORD", "POSTGRES_APP_PASSWORD")
APP_SECRETS = ("SESSION_SECRET", "CSRF_SECRET")
FAKE_DOCKER = "#!/usr/bin/env bash\nexit 0\n"


def _env_file(tmp_path: Path, settings: dict[str, str]) -> tuple[Path, dict[str, str]]:
    """A mode 600 env-file-source server env file with fresh fixture secrets and the given extra settings."""
    values = {name: "fixture-" + secrets.token_hex(24) for name in (*REQUIRED_SECRETS, *APP_SECRETS)}
    lines = {
        "SECRETS_SOURCE": "env-file",
        "SECRETS_HOST_DIR": str(tmp_path / "staged"),
        "SITE_ADDRESS": "demo.example.org",
        "PUBLIC_ORIGIN": "https://demo.example.org",
        "CADDY_TLS": "internal",
        **values,
        **settings,
    }
    path = tmp_path / "server.env"
    path.write_text("".join(f"{name}={value}\n" for name, value in lines.items()), encoding="utf-8")
    path.chmod(0o600)
    return path, values | {name: value for name, value in settings.items() if "KEY" in name}


def _prod(
    tmp_path: Path, env_file: Path, command: str, docker_body: str = FAKE_DOCKER
) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    docker = bin_dir / "docker"
    docker.write_text(docker_body, encoding="utf-8")
    docker.chmod(0o755)
    base = {key: value for key, value in os.environ.items() if not key.startswith(("LLM_", "LANGFUSE_", "SECRETS_"))}
    env = base | {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "ENV_FILE": str(env_file),
        "SECRETS_NO_CHOWN": "1",
    }
    return subprocess.run(
        ["bash", str(PROD_SH), command], capture_output=True, text=True, env=env, check=False, timeout=60
    )


def _stage_then_check(tmp_path: Path, settings: dict[str, str]) -> tuple[subprocess.CompletedProcess[str], set[str]]:
    env_file, values = _env_file(tmp_path, settings)
    staged = _prod(tmp_path, env_file, "stage-secrets")
    assert staged.returncode == 0, staged.stderr
    return _prod(tmp_path, env_file, "check"), {value for value in values.values() if value}


def _key() -> str:
    return "fixture-key-" + secrets.token_hex(24)


@pytest.mark.parametrize(
    ("settings", "named"),
    [
        (
            {"LLM_PROVIDER": "litellm", "LLM_PRIMARY_MODEL": "azure/gpt-4.1-mini"},
            ["app/LLM_API_KEY_PRIMARY (for LLM_PRIMARY_MODEL=azure/gpt-4.1-mini)"],
        ),
        (
            {
                "LLM_PROVIDER": "litellm",
                "LLM_PRIMARY_MODEL": "azure/gpt-4.1-mini",
                "LLM_API_KEY_PRIMARY": _key(),
                "LLM_FALLBACK_MODEL": "azure/gpt-4o",
            },
            ["app/LLM_API_KEY_FALLBACK (for LLM_FALLBACK_MODEL=azure/gpt-4o)"],
        ),
        (
            {"LLM_PROVIDER": "litellm", "LLM_PRIMARY_MODEL": "ollama/qwen2.5:7b-instruct", "LANGFUSE_ENABLED": "True"},
            ["app/LANGFUSE_PUBLIC_KEY (for LANGFUSE_ENABLED)", "app/LANGFUSE_SECRET_KEY (for LANGFUSE_ENABLED)"],
        ),
    ],
)
def test_check_refuses_an_empty_key_file_and_names_it_without_any_value(
    tmp_path: Path, settings: dict[str, str], named: list[str]
) -> None:
    result, values = _stage_then_check(tmp_path, settings)

    assert result.returncode != 0
    assert "empty staged key file" in result.stderr
    for name in named:
        assert f"{tmp_path / 'staged'}/{name}" in result.stderr
    output = result.stdout + result.stderr
    assert not any(value in output for value in values)


@pytest.mark.parametrize(
    "settings",
    [
        {},
        {"LLM_PROVIDER": "fake", "LLM_PRIMARY_MODEL": "azure/gpt-4.1-mini", "LANGFUSE_ENABLED": "false"},
        {"LLM_PROVIDER": "litellm", "LLM_PRIMARY_MODEL": "ollama/qwen2.5:7b-instruct"},
        {"LLM_PROVIDER": "litellm", "LLM_PRIMARY_MODEL": "ollama_chat/qwen2.5:7b-instruct"},
        {
            "LLM_PROVIDER": "litellm",
            "LLM_PRIMARY_MODEL": "azure/gpt-4.1-mini",
            "LLM_API_KEY_PRIMARY": _key(),
            "LLM_FALLBACK_MODEL": "azure/gpt-4o",
            "LLM_API_KEY_FALLBACK": _key(),
            "LANGFUSE_ENABLED": "true",
            "LANGFUSE_PUBLIC_KEY": "pk-lf-fixture",
            "LANGFUSE_SECRET_KEY": _key(),
        },
    ],
    ids=["no-model", "fake-provider", "ollama", "ollama-chat", "hosted-with-keys-and-langfuse"],
)
def test_check_passes_when_every_enabled_key_file_has_content(tmp_path: Path, settings: dict[str, str]) -> None:
    result, values = _stage_then_check(tmp_path, settings)

    assert result.returncode == 0, result.stderr
    assert "env file, staged secrets, and compose file are valid" in result.stderr
    output = result.stdout + result.stderr
    assert not any(value in output for value in values)


def test_up_refuses_before_starting_anything_when_a_hosted_key_is_empty(tmp_path: Path) -> None:
    env_file, _ = _env_file(tmp_path, {"LLM_PROVIDER": "litellm", "LLM_PRIMARY_MODEL": "azure/gpt-4.1-mini"})
    log = tmp_path / "docker.log"
    logging_docker = f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "{log}"\nexit 0\n'

    result = _prod(tmp_path, env_file, "up", logging_docker)

    assert result.returncode != 0
    assert "app/LLM_API_KEY_PRIMARY" in result.stderr
    calls = log.read_text(encoding="utf-8") if log.exists() else ""
    assert " up " not in f" {calls} "


def _logging_docker(log: Path) -> str:
    return f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "{log}"\nexit 0\n'


def test_llm_probe_stages_checks_and_runs_one_throwaway_api_container(tmp_path: Path) -> None:
    settings = {"LLM_PROVIDER": "litellm", "LLM_PRIMARY_MODEL": "azure/gpt-4.1-mini", "LLM_API_KEY_PRIMARY": _key()}
    env_file, values = _env_file(tmp_path, settings)
    log = tmp_path / "docker.log"

    result = _prod(tmp_path, env_file, "llm-probe", _logging_docker(log))

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "staged" / "app" / "LLM_API_KEY_PRIMARY").stat().st_size > 0
    calls = log.read_text(encoding="utf-8").splitlines()
    assert calls[-1].endswith("run --rm --no-deps -T api bank-agent llm-probe")
    assert not any(" up " in f" {call} " for call in calls)
    output = result.stdout + result.stderr
    assert not any(value in output for value in values.values() if value)


def test_llm_probe_refuses_before_any_container_when_the_key_file_is_empty(tmp_path: Path) -> None:
    env_file, _ = _env_file(tmp_path, {"LLM_PROVIDER": "litellm", "LLM_PRIMARY_MODEL": "azure/gpt-4.1-mini"})
    log = tmp_path / "docker.log"

    result = _prod(tmp_path, env_file, "llm-probe", _logging_docker(log))

    assert result.returncode != 0
    assert "app/LLM_API_KEY_PRIMARY" in result.stderr
    calls = log.read_text(encoding="utf-8") if log.exists() else ""
    assert "llm-probe" not in calls


def test_help_lists_every_command_including_the_last_header_line(tmp_path: Path) -> None:
    env_file, _ = _env_file(tmp_path, {})

    result = _prod(tmp_path, env_file, "help")

    assert result.returncode == 0
    assert "deploy/prod.sh llm-probe" in result.stdout
    assert result.stdout.rstrip().endswith("secret value.")
    assert "set -euo pipefail" not in result.stdout
