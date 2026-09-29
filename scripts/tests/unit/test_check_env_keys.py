"""Tests for scripts/checks/check_env_keys.py. They use temporary files only, never the real .env."""

import secrets
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "checks" / "check_env_keys.py"
REPOSITORY_EXAMPLE = Path(__file__).resolve().parents[3] / ".env.example"
REQUIRED = ("POSTGRES_ADMIN_PASSWORD", "POSTGRES_APP_PASSWORD", "SESSION_SECRET", "CSRF_SECRET")
S3 = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_DEFAULT_REGION", "DATA_BUCKET", "DATA_PREFIX")
LLM = ("LLM_PROVIDER", "LLM_PRIMARY_MODEL", "LLM_FALLBACK_MODEL", "LLM_API_KEY_PRIMARY", "LLM_API_KEY_FALLBACK")
EXAMPLE = "\n".join(f"{name}=" for name in (*REQUIRED, *S3, *LLM, "BANK_DATA_SOURCE", "LOG_LEVEL")) + "\n"


def _run(
    tmp_path: Path, env_text: str | None, process_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    example = tmp_path / "example.env"
    example.write_text(EXAMPLE, encoding="utf-8")
    env_file = tmp_path / "local.env"
    if env_text is not None:
        env_file.write_text(env_text, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--env-file", str(env_file), "--example", str(example)],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", **(process_env or {})},
        check=False,
    )


def _sentinels() -> dict[str, str]:
    return {name: f"sentinel-{secrets.token_hex(8)}" for name in REQUIRED}


def test_all_required_names_set_passes_without_printing_values(tmp_path: Path) -> None:
    values = _sentinels()
    lines = []
    for index, (name, value) in enumerate(values.items()):
        if index % 3 == 0:
            lines.append(f'{name}="{value}"')
        elif index % 3 == 1:
            lines.append(f"export {name}={value}")
        else:
            lines.append(f"{name}={value}  # inline comment")

    result = _run(tmp_path, "\n".join(lines) + "\n")

    assert result.returncode == 0
    assert f"all {len(REQUIRED)} required variable(s) set" in result.stdout
    for value in values.values():
        assert value not in result.stdout
        assert value not in result.stderr


def test_empty_quoted_commented_and_missing_values_count_as_unset(tmp_path: Path) -> None:
    values = _sentinels()
    lines = [f"{name}={value}" for name, value in values.items() if name not in {"SESSION_SECRET", "CSRF_SECRET"}]
    lines += ["SESSION_SECRET=   # left empty on purpose", 'CSRF_SECRET=""']

    result = _run(tmp_path, "\n".join(lines) + "\n")

    assert result.returncode == 1
    assert "  SESSION_SECRET: unset" in result.stdout
    assert "  CSRF_SECRET: unset" in result.stdout
    assert "2 of 4 required variable(s) unset" in result.stdout
    for value in values.values():
        assert value not in result.stdout


def test_missing_env_file_falls_back_to_the_process_environment(tmp_path: Path) -> None:
    result = _run(tmp_path, env_text=None)

    assert result.returncode == 1
    assert "not found; checking the process environment only" in result.stdout
    assert f"{len(REQUIRED)} of {len(REQUIRED)} required variable(s) unset" in result.stdout


def test_names_set_in_the_process_environment_count_as_set_and_stay_hidden(tmp_path: Path) -> None:
    values = _sentinels()

    result = _run(tmp_path, env_text=None, process_env=values)

    assert result.returncode == 0
    assert "  SESSION_SECRET: set" in result.stdout
    for value in values.values():
        assert value not in result.stdout


def test_optional_names_are_reported_separately(tmp_path: Path) -> None:
    result = _run(tmp_path, "LLM_API_KEY_PRIMARY=something\n")

    optional = result.stdout.split("Optional:")[1]
    assert "  LLM_API_KEY_PRIMARY: set" in optional
    assert "  LOG_LEVEL: unset" in optional
    assert "something" not in result.stdout


def test_missing_example_file_is_an_input_error(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--example", str(tmp_path / "absent.env")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "example file not found" in result.stderr


def _always() -> list[str]:
    return [f"{name}={value}" for name, value in _sentinels().items()]


def test_the_s3_source_makes_the_bucket_variables_required(tmp_path: Path) -> None:
    from_file = _run(tmp_path, "\n".join([*_always(), "BANK_DATA_SOURCE=s3  # organizer bucket"]) + "\n")
    from_process = _run(tmp_path, "\n".join([*_always(), "BANK_DATA_SOURCE=sample"]) + "\n",
                        process_env={"BANK_DATA_SOURCE": "s3"})  # fmt: skip

    for result in (from_file, from_process):
        assert result.returncode == 1
        assert "Data source: s3; the organizer bucket variables are required" in result.stdout
        assert "5 of 9 required variable(s) unset" in result.stdout


def test_a_hosted_live_model_needs_its_keys_and_a_local_ollama_model_does_not(tmp_path: Path) -> None:
    hosted = _run(tmp_path, "\n".join([*_always(), "LLM_PROVIDER=litellm", "LLM_PRIMARY_MODEL=openai/gpt-5-mini",
                                         "LLM_FALLBACK_MODEL=anthropic/claude-haiku-4-5-20251001"]) + "\n")  # fmt: skip
    local = _run(tmp_path, "\n".join([*_always(), "LLM_PROVIDER=litellm",
                                        "LLM_PRIMARY_MODEL=ollama/qwen2.5:7b-instruct"]) + "\n")  # fmt: skip
    cassette = _run(tmp_path, "\n".join([*_always(), "LLM_PROVIDER=cassette"]) + "\n")

    assert hosted.returncode == 1
    assert "  LLM_API_KEY_PRIMARY: unset" in hosted.stdout.split("Optional:")[0]
    assert "  LLM_API_KEY_FALLBACK: unset" in hosted.stdout.split("Optional:")[0]
    assert local.returncode == 0
    assert "LLM_API_KEY_PRIMARY" in local.stdout.split("Optional:")[1]
    assert cassette.returncode == 1
    assert "  LLM_PRIMARY_MODEL: unset" in cassette.stdout.split("Optional:")[0]


def test_a_fresh_copy_of_the_repository_example_passes(tmp_path: Path) -> None:
    copied = tmp_path / ".env"
    copied.write_text(REPOSITORY_EXAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--env-file", str(copied), "--example", str(REPOSITORY_EXAMPLE)],
        capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"}, check=False,
    )  # fmt: skip

    assert result.returncode == 0, result.stdout
    assert "Data source: sample" in result.stdout
    assert "dev-only" not in result.stdout
