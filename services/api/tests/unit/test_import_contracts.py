"""Negative control for the import-linter contracts in the root pyproject.toml.

A misconfigured contract (a typo in a module name, a wrong contract type) could pass silently on the real
code base. This test copies the real contracts, applies them to a throwaway ``bank_agent`` package that
breaks each one, and asserts that import-linter reports every contract as broken.
"""

import os
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
LAYERS = ("domain", "ports", "policy", "application", "adapters", "api", "bootstrap", "testing")

VIOLATIONS = {
    # Layers: the domain must not import the API.
    "domain/imports_api.py": "from bank_agent.api import routes\n",
    "api/routes.py": "",
    # Pure core: the policy kernel must not import a web framework.
    "policy/imports_fastapi.py": "import fastapi\n",
    # Entry points: a layer must not import the ASGI entry point.
    "adapters/imports_entry_point.py": "import bank_agent.asgi\n",
    # Test doubles: production code must not import them.
    "application/imports_testing.py": "import bank_agent.testing\n",
    # Test doubles: they must not depend on adapters.
    "testing/imports_adapters.py": "import bank_agent.adapters\n",
    # The application must not import the evaluation harness.
    "ports/imports_evals.py": "import bank_evals\n",
}
EVALS_VIOLATIONS = {
    "__init__.py": "",
    "systems/__init__.py": "",
    "systems/engine_system.py": "",
    "systems/failures.py": "",
    # Baseline B1 must not reach the policy kernel.
    "systems/naive_agent/__init__.py": "import bank_agent.policy\n",
}


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"unsupported TOML value: {value!r}")


def _write_config(path: Path, settings: dict[str, Any]) -> None:
    lines = ["[tool.importlinter]"]
    lines += [f"{key} = {_toml_value(value)}" for key, value in settings.items() if key != "contracts"]
    for contract in settings["contracts"]:
        lines.append("[[tool.importlinter.contracts]]")
        lines += [f"{key} = {_toml_value(value)}" for key, value in contract.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_violating_package(source_root: Path) -> None:
    package = source_root / "bank_agent"
    for layer in LAYERS:
        (package / layer).mkdir(parents=True)
        (package / layer / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "asgi.py").write_text("", encoding="utf-8")
    (package / "cli.py").write_text("", encoding="utf-8")
    for relative_path, content in VIOLATIONS.items():
        (package / relative_path).write_text(content, encoding="utf-8")
    evals = source_root / "bank_evals"
    (evals / "systems" / "naive_agent").mkdir(parents=True)
    for relative_path, content in EVALS_VIOLATIONS.items():
        (evals / relative_path).write_text(content, encoding="utf-8")


def test_every_contract_detects_its_violation(tmp_path: Path) -> None:
    settings = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["importlinter"]
    config = tmp_path / "importlinter.toml"
    _write_config(config, settings)
    _build_violating_package(tmp_path / "src")
    lint_imports = Path(sys.executable).with_name("lint-imports")

    result = subprocess.run(
        [str(lint_imports), "--config", str(config), "--no-cache"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(tmp_path / "src")},
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert f"Contracts: 0 kept, {len(settings['contracts'])} broken." in result.stdout
    for contract in settings["contracts"]:
        assert f"{contract['name']} BROKEN" in result.stdout
