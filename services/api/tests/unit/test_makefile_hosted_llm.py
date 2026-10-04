"""`make api-hosted-llm`: the API with a hosted model, configured only from the environment, never printing a key.

The recipe is read from the Makefile and its preflight is run as make would run it (variables expanded, `$$` read as
`$`) in a temporary directory, with dummy values in the process environment only, so no `.env` is read.
"""

import re
import shutil
import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
MAKEFILE = (REPOSITORY_ROOT / "Makefile").read_text(encoding="utf-8")
CHECK_SCRIPT = REPOSITORY_ROOT / "scripts" / "checks" / "check_env_keys.py"
DUMMY_KEY = "dummy-value-that-must-never-be-printed-0000"
APP_SECRETS = ("POSTGRES_ADMIN_PASSWORD", "POSTGRES_APP_PASSWORD", "SESSION_SECRET", "CSRF_SECRET")


def _joined(text: str) -> str:
    """Make's line continuation: a backslash, the newline, and the indentation become one space."""
    return re.sub(r"\\\n\s*", " ", text)


def _variable(name: str) -> str:
    match = re.search(rf"^{name} :?= (.*)$", _joined(MAKEFILE), re.MULTILINE)
    assert match is not None, f"{name} is not defined in the Makefile"
    return match.group(1)


def _recipe(target: str) -> list[str]:
    block = MAKEFILE.split(f"\n{target}:", 1)[1].split("\n\n", 1)[0]
    lines = _joined(block).splitlines()[1:]
    return [line.strip() for line in lines if line.startswith("\t")]


def _expanded(command: str) -> str:
    command = command.replace("$(HOSTED_LLM_PREFLIGHT)", _variable("HOSTED_LLM_PREFLIGHT"))
    command = command.replace("$(GUARD_PY)", sys.executable)
    command = command.replace("scripts/checks/check_env_keys.py", str(CHECK_SCRIPT))
    return command.replace("$$", "$")


def _preflight(tmp_path: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
    shutil.copy(REPOSITORY_ROOT / ".env.example", tmp_path / ".env.example")
    bash = shutil.which("bash")
    assert bash is not None
    return subprocess.run(  # nosec B603: a fixed command read from the repository's Makefile
        [bash, "-c", _expanded(_recipe("api-hosted-llm")[0])],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin", **environment},
        check=False,
    )


def test_the_hosted_target_selects_litellm_and_takes_model_and_key_from_the_environment() -> None:
    preflight, api = _recipe("api-hosted-llm")

    assert "check_env_keys.py" in preflight
    assert preflight.endswith('exit "$${PIPESTATUS[0]}"')
    assert api.startswith("LLM_PROVIDER=litellm $(LLM_EXTRA_RUN) uvicorn bank_agent.asgi:create_app --factory")
    assert api.endswith("--host 127.0.0.1 --port 8000")
    assert _variable("LLM_EXTRA_RUN").startswith("uv run --frozen --extra litellm")
    for line in (preflight, api):
        assert not re.search(r"LLM_(API_KEY_\w+|PRIMARY_MODEL|API_BASE)=", line)


def test_the_preflight_stops_and_names_the_missing_key_without_any_value(tmp_path: Path) -> None:
    result = _preflight(tmp_path, {"LLM_PRIMARY_MODEL": "openai/gpt-5-mini", "SESSION_SECRET": DUMMY_KEY})

    assert result.returncode == 1
    assert "  LLM_PRIMARY_MODEL: set" in result.stdout
    assert "  LLM_API_KEY_PRIMARY: unset" in result.stdout
    assert "  SESSION_SECRET: set" in result.stdout
    assert DUMMY_KEY not in result.stdout + result.stderr
    assert "openai/gpt-5-mini" not in result.stdout


def test_the_preflight_passes_with_every_required_variable_and_shows_only_the_relevant_ones(tmp_path: Path) -> None:
    environment = dict.fromkeys(APP_SECRETS, DUMMY_KEY)
    environment |= {"LLM_PRIMARY_MODEL": "openai/gpt-5-mini", "LLM_API_KEY_PRIMARY": DUMMY_KEY}

    result = _preflight(tmp_path, environment)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "  LLM_API_KEY_PRIMARY: set" in result.stdout
    assert "  LLM_API_KEY_FALLBACK: unset" in result.stdout
    assert "check-env-keys: all 6 required variable(s) set" in result.stdout
    assert "LLM_DAILY_BUDGET_USD" not in result.stdout
    assert DUMMY_KEY not in result.stdout + result.stderr
