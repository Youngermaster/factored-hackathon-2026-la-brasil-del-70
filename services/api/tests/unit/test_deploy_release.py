"""The pull-by-tag path of continuous deployment (ADR 0038): `deploy/prod.sh pull` and `deploy/prod.sh release`.

prod.sh runs for real under bash against a fake `docker` first on PATH, so these tests make no network call and need no
Docker. They pin what the deploy workflow relies on: images pulled by digest and tagged as `deploy/prod.sh build` would
tag them, and a registry token that only ever travels on stdin, inside a throwaway Docker config.
"""

import os
import secrets
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
DEPLOY = ROOT / "deploy"
TOKEN = "registry-token-" + secrets.token_hex(16)
"""A fresh fake registry token per run; it must never show in an argument list or any output."""
DIGESTS = {name: "sha256:" + digit * 64 for name, digit in (("API", "a"), ("JOB", "b"), ("WEB", "c"))}
FAKE_DOCKER = """#!/usr/bin/env bash
printf '%s|%s\\n' "${DOCKER_CONFIG:-}" "$*" >> "${FAKE_LOG}"
if [[ "$1" == "login" ]]; then cat > "${FAKE_LOG}.stdin"; fi
exit 0
"""


def _commit() -> tuple[str, str]:
    full = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return full.stdout.strip(), full.stdout.strip()[:12]


def _fake(tmp_path: Path, name: str, body: str) -> dict[str, str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(exist_ok=True)
    tool = bin_dir / name
    tool.write_text(body, encoding="utf-8")
    tool.chmod(0o755)
    return {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "FAKE_LOG": str(tmp_path / "log")}


def _run(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    base = {key: value for key, value in os.environ.items() if not key.startswith(("IMAGE_", "REGISTRY_", "AZURE_"))}
    return subprocess.run(["bash", *command], capture_output=True, text=True, env=base | env, check=False, timeout=60)


def _calls(tmp_path: Path) -> list[tuple[str, str]]:
    lines = (tmp_path / "log").read_text(encoding="utf-8").splitlines()
    return [(config, arguments) for config, _, arguments in (line.partition("|") for line in lines)]


def test_pull_takes_each_image_by_digest_and_tags_it_as_build_would(tmp_path: Path) -> None:
    full, short = _commit()
    token_file = tmp_path / "token"
    token_file.write_text(TOKEN, encoding="utf-8")
    env = (
        _fake(tmp_path, "docker", FAKE_DOCKER)
        | {
            "ENV_FILE": str(tmp_path / "absent.env"),
            "IMAGE_REGISTRY": "ghcr.io/owner/repository",
            "REGISTRY_USER": "github-actions[bot]",
            "REGISTRY_TOKEN_FILE": str(token_file),
        }
        | {f"IMAGE_DIGEST_{name}": digest for name, digest in DIGESTS.items()}
    )

    result = _run([str(DEPLOY / "prod.sh"), "pull"], env)

    assert result.returncode == 0, result.stderr
    calls = _calls(tmp_path)
    arguments = [call for _, call in calls]
    assert arguments[0] == "login ghcr.io --username github-actions[bot] --password-stdin"
    assert (tmp_path / "log.stdin").read_text(encoding="utf-8") == TOKEN
    for name, digest in DIGESTS.items():
        image = f"ghcr.io/owner/repository/bank-agent-{name.lower()}"
        assert f"pull --quiet {image}@{digest}" in arguments
        assert f"tag {image}@{digest} bank-agent-{name.lower()}:{short}" in arguments
    assert arguments[-1] == "logout ghcr.io"
    assert full not in " ".join(arguments)
    # Every call used the same throwaway Docker config, and it is gone afterwards.
    configs = {config for config, _ in calls}
    assert len(configs) == 1
    (config,) = configs
    assert config
    assert not Path(config).exists()
    assert TOKEN not in result.stdout + result.stderr + " ".join(arguments)


def test_pull_without_digests_or_token_uses_the_full_commit_tag_and_no_login(tmp_path: Path) -> None:
    full, short = _commit()
    env = _fake(tmp_path, "docker", FAKE_DOCKER) | {
        "ENV_FILE": str(tmp_path / "absent.env"),
        "IMAGE_REGISTRY": "ghcr.io/owner/repository",
    }

    result = _run([str(DEPLOY / "prod.sh"), "pull"], env)

    assert result.returncode == 0, result.stderr
    arguments = [call for _, call in _calls(tmp_path)]
    assert not any(call.startswith(("login", "logout")) for call in arguments)
    assert f"pull --quiet ghcr.io/owner/repository/bank-agent-web:{full}" in arguments
    assert f"tag ghcr.io/owner/repository/bank-agent-web:{full} bank-agent-web:{short}" in arguments


@pytest.mark.parametrize(
    ("variable", "value", "message"),
    [
        ("IMAGE_REGISTRY", "ghcr.io/Owner/Repository", "set IMAGE_REGISTRY to the lower-case image prefix"),
        ("IMAGE_REGISTRY", "ghcr.io/owner/repo;rm -rf /", "set IMAGE_REGISTRY to the lower-case image prefix"),
        ("IMAGE_DIGEST_JOB", "sha256:short", "IMAGE_DIGEST_JOB must look like sha256:<64 hex digits>"),
    ],
)
def test_pull_refuses_a_malformed_registry_or_digest(tmp_path: Path, variable: str, value: str, message: str) -> None:
    env = _fake(tmp_path, "docker", FAKE_DOCKER) | {
        "ENV_FILE": str(tmp_path / "absent.env"),
        "IMAGE_REGISTRY": "ghcr.io/owner/repository",
        variable: value,
    }

    result = _run([str(DEPLOY / "prod.sh"), "pull"], env)

    assert result.returncode == 1
    assert message in result.stderr
    log = tmp_path / "log"
    assert not log.exists() or "bank-agent-job" not in log.read_text(encoding="utf-8")


def test_release_pulls_backs_up_when_the_database_runs_then_starts() -> None:
    script = (DEPLOY / "prod.sh").read_text(encoding="utf-8")
    release = script.split("cmd_release() {", 1)[1].split("\n}", 1)[0]
    assert release.index("cmd_pull") < release.index("cmd_backup") < release.index("cmd_up")
    assert "if database_running; then cmd_backup;" in release
    assert "    release) cmd_release ;;" in script
    assert "    pull) cmd_pull ;;" in script
    # pull replaces build on this path: it never builds, and the build path stays for local and manual use.
    pull = script.split("cmd_pull() (", 1)[1].split("\n)", 1)[0]
    assert "build" not in pull
    assert "--password-stdin" in pull
    assert "    build) cmd_build ;;" in script
