"""deploy/azure/run-on-vm.sh and deploy/azure/vm-deploy.sh: the run-command half of continuous deployment (ADR 0038).

run-on-vm.sh runs for real under bash against a fake `az` first on PATH (no network, no Azure). It must send every
setting inside a private script, never as an argument, and fail unless the VM reports success for the action.
vm-deploy.sh needs root and an Ubuntu VM, so its rules are checked on the text.
"""

import os
import re
import secrets
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[4]
DEPLOY = ROOT / "deploy"
TOKEN = "registry-token-" + secrets.token_hex(16)
"""A fresh fake registry token per run; it must never show in an argument list or any output."""
DIGESTS = {name: "sha256:" + digit * 64 for name, digit in (("API", "a"), ("JOB", "b"), ("WEB", "c"))}
FAKE_AZ = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "${FAKE_LOG}"
for argument in "$@"; do
  if [[ "${argument}" == @* ]]; then
    cp "${argument#@}" "${FAKE_LOG}.script"
    stat -c '%a' "${argument#@}" > "${FAKE_LOG}.mode" 2> /dev/null || stat -f '%Lp' "${argument#@}" > "${FAKE_LOG}.mode"
    printf '%s\\n' "${argument#@}" > "${FAKE_LOG}.path"
  fi
done
printf 'Enable succeeded: \\n[stdout]\\n%s\\n\\n[stderr]\\n' "${FAKE_LAST_LINE}"
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


def _vm_env(tmp_path: Path, last_line: str) -> dict[str, str]:
    return (
        _fake(tmp_path, "az", FAKE_AZ)
        | {
            "FAKE_LAST_LINE": last_line,
            "AZURE_RESOURCE_GROUP": "rg-bank-agent",
            "AZURE_VM_NAME": "vm-bank-agent",
            "DEPLOY_SHA": _commit()[0],
            "IMAGE_REGISTRY": "ghcr.io/owner/repository",
            "REGISTRY_USER": "github-actions[bot]",
            "REGISTRY_TOKEN": TOKEN,
        }
        | {f"IMAGE_DIGEST_{name}": digest for name, digest in DIGESTS.items()}
    )


def test_run_on_vm_sends_the_settings_inside_a_private_script_never_as_arguments(tmp_path: Path) -> None:
    result = _run([str(DEPLOY / "azure" / "run-on-vm.sh"), "deploy"], _vm_env(tmp_path, "vm-deploy: result=deploy-ok"))

    assert result.returncode == 0, result.stderr
    arguments = (tmp_path / "log").read_text(encoding="utf-8")
    assert arguments.startswith("vm run-command invoke --resource-group rg-bank-agent --name vm-bank-agent")
    assert "--command-id RunShellScript --scripts @" in arguments
    assert TOKEN not in arguments
    assert (tmp_path / "log.mode").read_text(encoding="utf-8").strip() == "600"
    assert not Path((tmp_path / "log.path").read_text(encoding="utf-8").strip()).exists()
    script = (tmp_path / "log.script").read_text(encoding="utf-8")
    assert f"export REGISTRY_TOKEN={TOKEN}\n" in script
    assert "export DEPLOY_ACTION=deploy\n" in script
    assert f"export IMAGE_DIGEST_WEB={DIGESTS['WEB']}\n" in script
    assert script.endswith((DEPLOY / "azure" / "vm-deploy.sh").read_text(encoding="utf-8").split("\n", 1)[1])
    assert TOKEN not in result.stdout + result.stderr


@pytest.mark.parametrize("last_line", ["vm-deploy: result=deploy-failed", "vm-deploy: result=rollback-ok", ""])
def test_run_on_vm_fails_unless_the_vm_reports_success_for_the_action(tmp_path: Path, last_line: str) -> None:
    result = _run([str(DEPLOY / "azure" / "run-on-vm.sh"), "deploy"], _vm_env(tmp_path, last_line))

    assert result.returncode == 1
    assert "vm-deploy.sh did not report success" in result.stderr


@pytest.mark.parametrize(
    ("variable", "value"),
    [("DEPLOY_SHA", "main"), ("AZURE_VM_NAME", "vm;reboot"), ("IMAGE_DIGEST_API", "sha256:0"), ("VM_CHECKOUT", "rel")],
)
def test_run_on_vm_refuses_malformed_settings_before_calling_azure(tmp_path: Path, variable: str, value: str) -> None:
    result = _run(
        [str(DEPLOY / "azure" / "run-on-vm.sh"), "deploy"],
        _vm_env(tmp_path, "vm-deploy: result=deploy-ok") | {variable: value},
    )

    assert result.returncode == 1
    assert f"{variable} is missing or malformed" in result.stderr
    assert value not in result.stderr
    assert not (tmp_path / "log").exists()


def test_vm_deploy_runs_git_and_prod_sh_as_the_operator_and_reports_a_result_line() -> None:
    script = (DEPLOY / "azure" / "vm-deploy.sh").read_text(encoding="utf-8")
    assert 'runuser -u "${OWNER}" --' in script
    # No git or prod.sh command runs as root: each line that starts one goes through as_owner.
    bare = [line for line in script.splitlines() if re.match(r"^\s+(git|\"\$\{CHECKOUT\}/deploy/prod\.sh\")\s", line)]
    assert bare == []
    assert 'say "result=${ACTION}-ok"' in script
    assert "set -x" not in script
    assert 'printf \'%s\' "${REGISTRY_TOKEN}" > "${TOKEN_FILE}"' in script
    assert stat.S_IMODE((DEPLOY / "azure" / "vm-deploy.sh").stat().st_mode) & 0o111
