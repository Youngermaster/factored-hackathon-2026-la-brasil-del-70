"""deploy/azure/setup-github-oidc.sh: the one-time Azure identity for the deploy workflow (ADR 0038).

The dry run executes for real under bash with a fake `az` that is not signed in, so it touches no Azure tenant and no
network: it must print every change it would make, change nothing, and print the GitHub settings. The rest checks the
script's text for the least-privilege choices.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "deploy" / "azure" / "setup-github-oidc.sh"
REPOSITORY = "Example-Owner/example-repository"
FAKE_AZ = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> "${FAKE_LOG}"
exit 1
"""


FAKE_GH_FAILING = """#!/usr/bin/env bash
# Like gh when the call fails: the error body on stdout and a non-zero exit.
printf '{"message":"Not Found","status":"404"}'
exit 1
"""


def _fake_gh_answering(prefix: str) -> str:
    return f"""#!/usr/bin/env bash
printf '%s' '{prefix}'
"""


def _dry_run(tmp_path: Path, gh_script: str = FAKE_GH_FAILING, **settings: str) -> subprocess.CompletedProcess[str]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "az").write_text(FAKE_AZ, encoding="utf-8")
    (bin_dir / "az").chmod(0o755)
    (bin_dir / "gh").write_text(gh_script, encoding="utf-8")
    (bin_dir / "gh").chmod(0o755)
    env = {key: value for key, value in os.environ.items() if key not in {"GITHUB_REPOSITORY", "ROLE_MODE"}}
    env |= {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "FAKE_LOG": str(tmp_path / "az.log")}
    env |= {"GITHUB_REPOSITORY": REPOSITORY} | settings
    return subprocess.run(
        ["bash", str(SCRIPT), "--dry-run"], capture_output=True, text=True, env=env, check=False, timeout=60
    )


def test_the_dry_run_prints_every_change_and_makes_none(tmp_path: Path) -> None:
    result = _dry_run(tmp_path)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "az.log").read_text(encoding="utf-8").splitlines() == ["account show --output none"]
    planned = [line for line in result.stderr.splitlines() if line.startswith("dry-run: ")]
    assert [line.split()[1:4] for line in planned] == [
        ["az", "ad", "app"],
        ["az", "ad", "sp"],
        ["az", "ad", "app"],
        ["az", "ad", "app"],
        ["az", "role", "definition"],
        ["az", "role", "assignment"],
    ]
    assert f"repo:{REPOSITORY}:environment:production" in result.stderr
    assert f"repo:{REPOSITORY}:ref:refs/heads/main" in result.stderr
    assert "/providers/Microsoft.Compute/virtualMachines/vm-bank-agent" in planned[-1]
    for name in ("AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_SUBSCRIPTION_ID", "AZURE_RESOURCE_GROUP", "PUBLIC_URL"):
        assert name in result.stdout
    assert "dry run: nothing was created or changed" in result.stderr


def test_the_branch_credential_can_be_left_out_and_the_builtin_role_scopes_the_group(tmp_path: Path) -> None:
    result = _dry_run(tmp_path, BRANCH_CREDENTIAL="0", ROLE_MODE="builtin")

    assert result.returncode == 0, result.stderr
    assert "refs/heads/main" not in result.stderr.replace("github-main-branch: skipped", "")
    (assignment,) = [line for line in result.stderr.splitlines() if "role assignment create" in line]
    assert "Virtual\\ Machine\\ Contributor" in assignment
    scope = r"--scope /subscriptions/\<subscription-id\>/resourceGroups/rg-bank-agent --output none"
    assert assignment.rstrip().endswith(scope)


@pytest.mark.parametrize("repository", ["not-a-repository", "owner/name; rm -rf /", "owner/name/extra"])
def test_a_malformed_repository_is_refused(tmp_path: Path, repository: str) -> None:
    result = _dry_run(tmp_path, GITHUB_REPOSITORY=repository)

    assert result.returncode == 1
    assert "set GITHUB_REPOSITORY=owner/name" in result.stderr


def test_the_custom_role_allows_run_command_and_reading_the_vm_only() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    actions = re.findall(r'"(Microsoft\.[A-Za-z./]+)"', text)
    assert actions == ["Microsoft.Compute/virtualMachines/read", "Microsoft.Compute/virtualMachines/runCommand/action"]
    assert "*" not in "".join(actions)
    assert "Key Vault" not in re.sub(r"^#.*$", "", text, flags=re.MULTILINE)
    assert "client secret" not in re.sub(r"^#.*$", "", text, flags=re.MULTILINE).lower()
    assert "credential reset" not in text


def test_the_subject_uses_the_prefix_github_reports_when_it_has_immutable_ids(tmp_path: Path) -> None:
    prefix = "repo:Example-Owner@123/example-repository@456"
    result = _dry_run(tmp_path, gh_script=_fake_gh_answering(prefix), BRANCH_CREDENTIAL="0")

    assert result.returncode == 0, result.stderr
    assert f"{prefix}:environment:production" in result.stderr + result.stdout
    assert "repo:Example-Owner/example-repository:environment" not in result.stderr + result.stdout


def test_a_failed_github_call_falls_back_to_the_name_based_subject(tmp_path: Path) -> None:
    result = _dry_run(tmp_path, BRANCH_CREDENTIAL="0")

    assert result.returncode == 0, result.stderr
    assert "repo:Example-Owner/example-repository:environment:production" in result.stderr + result.stdout
    assert "Not Found" not in result.stderr + result.stdout
