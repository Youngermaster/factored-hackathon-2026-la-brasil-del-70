"""Run dbt in a subprocess with an explicit, credential-free environment.

The child process receives only what it needs: ``PATH``, locale and temporary-directory variables, and the
``BANK_DATA_*`` paths. AWS variables are never forwarded, anonymous usage statistics and version checks are
off, and each warehouse gets its own dbt target and log directories so full, sample, and test builds never
share state.
"""

import json
import logging
import os
import subprocess  # nosec B404 (runs the dbt executable of this virtual environment with a fixed argument list)
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bank_data.errors import DbtError

LOGGER = logging.getLogger("bank_data.dbt")
_PASSED_THROUGH = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT")


@dataclass(frozen=True)
class DbtTarget:
    warehouse_db: Path
    bronze_dir: Path
    gold_dir: Path
    work_dir: Path
    """dbt ``target`` and ``logs`` live here, next to the warehouse database."""


@dataclass(frozen=True)
class DbtResources:
    dbt_threads: int = 4
    duckdb_threads: int = 4
    memory_limit: str = "4GB"


def dbt_executable() -> Path:
    return Path(sys.executable).parent / "dbt"


class DbtRunner:
    def __init__(self, project_dir: Path, target: DbtTarget, resources: DbtResources | None = None) -> None:
        self._project = project_dir
        self._target = target
        self._resources = resources or DbtResources()

    @property
    def target_path(self) -> Path:
        return self._target.work_dir / "dbt_target"

    def environment(self) -> dict[str, str]:
        environment = {name: os.environ[name] for name in _PASSED_THROUGH if name in os.environ}
        environment.update(
            {
                "BANK_DATA_WAREHOUSE_DB": self._target.warehouse_db.as_posix(),
                "BANK_DATA_BRONZE_DIR": self._target.bronze_dir.as_posix(),
                "BANK_DATA_DBT_THREADS": str(self._resources.dbt_threads),
                "BANK_DATA_DUCKDB_THREADS": str(self._resources.duckdb_threads),
                "BANK_DATA_DUCKDB_MEMORY_LIMIT": self._resources.memory_limit,
                "DBT_PROFILES_DIR": self._project.as_posix(),
                "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
                "DO_NOT_TRACK": "1",
                "PYTHONWARNINGS": "ignore",
            }
        )
        return environment

    def command(self, arguments: Sequence[str], variables: Mapping[str, Any] | None = None) -> list[str]:
        command = [
            dbt_executable().as_posix(),
            "--no-version-check",
            "--no-use-colors",
            *arguments,
            "--project-dir",
            self._project.as_posix(),
            "--target-path",
            self.target_path.as_posix(),
            "--log-path",
            (self._target.work_dir / "dbt_logs").as_posix(),
        ]
        merged = {"gold_dir": self._target.gold_dir.as_posix(), **(variables or {})}
        command += ["--vars", json.dumps(merged, sort_keys=True)]
        return command

    def run(self, arguments: Sequence[str], variables: Mapping[str, Any] | None = None) -> str:
        """Run one dbt command; return its output, or raise ``DbtError`` with the tail of the output."""
        self._target.work_dir.mkdir(parents=True, exist_ok=True)
        self._target.gold_dir.mkdir(parents=True, exist_ok=True)
        command = self.command(arguments, variables)
        LOGGER.info("running dbt", extra={"dbt_command": arguments[0]})
        completed = subprocess.run(  # noqa: S603  # nosec B603 (fixed executable and arguments, no shell)
            command,
            cwd=self._project,
            env=self.environment(),
            capture_output=True,
            text=True,
            check=False,
        )
        output = completed.stdout + completed.stderr
        if completed.returncode != 0:
            tail = "\n".join(output.strip().splitlines()[-40:])
            raise DbtError(f"dbt {arguments[0]} exited with {completed.returncode}\n{tail}")
        return output

    def build(self, variables: Mapping[str, Any], *, full_refresh: bool = False) -> str:
        arguments = ["build"]
        if full_refresh:
            arguments.append("--full-refresh")
        return self.run(arguments, variables)

    def test(self, variables: Mapping[str, Any]) -> str:
        return self.run(["test"], variables)

    def freshness(self, variables: Mapping[str, Any]) -> str:
        return self.run(["source", "freshness"], variables)

    def docs_generate(self, variables: Mapping[str, Any]) -> str:
        return self.run(["docs", "generate"], variables)

    def manifest_path(self) -> Path:
        return self.target_path / "manifest.json"

    def run_results_path(self) -> Path:
        return self.target_path / "run_results.json"

    def sources_path(self) -> Path:
        return self.target_path / "sources.json"
