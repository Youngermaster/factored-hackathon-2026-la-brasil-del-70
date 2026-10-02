#!/usr/bin/env python3
"""Stage the production stack's secrets as files that Compose mounts into each service (ADR 0036).

Standard library only, so it runs with the VM's own python3 before any image exists.

Sources:
    keyvault  Azure Key Vault, through the VM's managed identity: a token from the instance metadata service, then the
              Key Vault REST API. No credential is stored anywhere; the identity can only read (Key Vault Secrets User).
    env-file  The server env file (deploy/.env.production), for hosts without a managed secret store and local tests.

Layout under DEST (default /run/bank-agent/secrets: /run is a tmpfs, so nothing reaches the disk, the checkout, an
image, or a volume, and a reboot clears it until the systemd unit stages it again):
    app/<NAME>       owned by uid 10001, the user of the api and job images
    postgres/<NAME>  owned by uid 70, the user of the postgres image
    grafana/<NAME>   owned by uid 472, the user of the grafana image
Files are mode 0400 and directories 0711: dockerd (root) bind-mounts known paths, and no other host user can list or
read them. A secret that a source does not have is written empty when it is optional (a model key, the Grafana
password) and stops the run when it is required. Values never appear in output, logs, or command-line arguments.

    sudo python3 deploy/secrets_stage.py stage --source keyvault --vault <vault name>
    sudo python3 deploy/secrets_stage.py stage --source env-file --env-file deploy/.env.production
    python3 deploy/secrets_stage.py check          # names and states only; it reads no secret
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

DEFAULT_DEST = Path("/run/bank-agent/secrets")
MANAGED_IDENTITY_URL = (
    "http://169.254.169.254/metadata/identity/oauth2/token"
    "?api-version=2018-02-01&resource=https%3A%2F%2Fvault.azure.net"
)
KEY_VAULT_API_VERSION = "7.4"
VAULT_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9-]{1,22}[A-Za-z0-9]$")
FILE_MODE = 0o400
DIRECTORY_MODE = 0o711
TOKEN_ATTEMPTS = 12
"""The metadata service can answer late right after boot; about a minute of retries covers it."""


@dataclass(frozen=True)
class Secret:
    variable: str
    """The variable and file name, as the settings read it (``SESSION_SECRET``)."""
    vault_name: str
    """The Key Vault secret name (Key Vault allows letters, digits, and dashes only)."""
    consumers: tuple[str, ...]
    required: bool


SECRETS: tuple[Secret, ...] = (
    Secret("POSTGRES_SUPERUSER_PASSWORD", "postgres-superuser-password", ("postgres",), required=True),
    Secret("POSTGRES_ADMIN_PASSWORD", "postgres-admin-password", ("postgres", "app"), required=True),
    Secret("POSTGRES_APP_PASSWORD", "postgres-app-password", ("postgres", "app"), required=True),
    Secret("SESSION_SECRET", "session-secret", ("app",), required=True),
    Secret("CSRF_SECRET", "csrf-secret", ("app",), required=True),
    Secret("LLM_API_KEY_PRIMARY", "llm-api-key-primary", ("app",), required=False),
    Secret("LLM_API_KEY_FALLBACK", "llm-api-key-fallback", ("app",), required=False),
    Secret("GRAFANA_ADMIN_PASSWORD", "grafana-admin-password", ("grafana",), required=False),
)
CONSUMERS: dict[str, tuple[int, int]] = {"app": (10001, 10001), "postgres": (70, 70), "grafana": (472, 0)}
"""Owner uid and gid of each consumer directory: the non-root user its container runs as."""

HttpGet = Callable[[str, Mapping[str, str]], tuple[int, bytes]]


class StageError(Exception):
    """A failure that names secrets and statuses, never a value."""


def say(message: str) -> None:
    print(f"secrets-stage: {message}", file=sys.stderr)


def http_get(url: str, headers: Mapping[str, str]) -> tuple[int, bytes]:
    """GET with a 10-second timeout; the metadata service is reached without any proxy, as Azure requires."""
    handlers: list[urllib.request.BaseHandler] = []
    if url.startswith("http://169.254.169.254/"):
        handlers.append(urllib.request.ProxyHandler({}))
    opener = urllib.request.build_opener(*handlers)
    # The URLs are the fixed metadata endpoint and https://<validated vault name>.vault.azure.net only.
    request = urllib.request.Request(url, headers=dict(headers), method="GET")  # noqa: S310
    try:
        with opener.open(request, timeout=10) as response:
            return int(response.status), response.read()
    except urllib.error.HTTPError as error:
        return int(error.code), b""


class EnvFileSource:
    """Secrets from the server env file: ``NAME=value`` lines, the last assignment wins (as in deploy/prod.sh)."""

    label = "env-file"

    def __init__(self, path: Path) -> None:
        if not path.is_file():
            raise StageError(f"no env file at {path}")
        self._values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            name, separator, value = line.partition("=")
            if separator and re.fullmatch(r"[A-Z][A-Z0-9_]*", name):
                self._values[name] = value.strip()

    def get(self, secret: Secret) -> str | None:
        return self._values.get(secret.variable) or None


class KeyVaultSource:
    """Secrets from Azure Key Vault, read with the managed identity's token."""

    label = "keyvault"

    def __init__(self, vault: str, get: HttpGet = http_get, sleep: Callable[[float], None] = time.sleep) -> None:
        if not VAULT_NAME.fullmatch(vault):
            raise StageError("the vault name must be 3 to 24 letters, digits, or dashes, starting with a letter")
        self._vault = vault
        self._get = get
        self._sleep = sleep
        self._token: str | None = None

    def _bearer(self) -> str:
        if self._token is None:
            for attempt in range(TOKEN_ATTEMPTS):
                try:
                    status, body = self._get(MANAGED_IDENTITY_URL, {"Metadata": "true"})
                except OSError:
                    status, body = 0, b""
                if status == 200:
                    token = json.loads(body).get("access_token", "")
                    if token:
                        self._token = str(token)
                        break
                if status in {400, 403}:
                    raise StageError(
                        f"the metadata service refused a token (HTTP {status}); "
                        "is a system-assigned managed identity enabled on this VM?"
                    )
                self._sleep(min(2.0 * (attempt + 1), 10.0))
            else:
                raise StageError("no managed identity token from the instance metadata service; is this an Azure VM?")
        return f"Bearer {self._token}"

    def get(self, secret: Secret) -> str | None:
        url = (
            f"https://{self._vault}.vault.azure.net/secrets/{quote(secret.vault_name)}"
            f"?api-version={KEY_VAULT_API_VERSION}"
        )
        status, body = self._get(url, {"Authorization": self._bearer()})
        if status == 404:
            return None
        if status == 403 and not secret.required:
            # Access is granted per secret, so an optional secret that was never created (no grant can exist for it
            # yet) answers 403, not 404: the identity may not even learn whether it exists. It is simply not in use.
            say(f"{secret.vault_name}: not readable by this identity (HTTP 403); optional, staged empty")
            return None
        if status != 200:
            hint = " (grant the VM identity Key Vault Secrets User on it)" if status == 403 else ""
            raise StageError(f"Key Vault answered HTTP {status} for secret {secret.vault_name}{hint}")
        value = json.loads(body).get("value")
        return str(value) if value else None


Source = EnvFileSource | KeyVaultSource


def collect(source: Source) -> dict[str, str]:
    """Read every secret first, so a missing required one stops the run before any file changes."""
    values: dict[str, str] = {}
    missing: list[str] = []
    for secret in SECRETS:
        value = source.get(secret)
        if value is None and secret.required:
            missing.append(secret.vault_name if source.label == "keyvault" else secret.variable)
        values[secret.variable] = value or ""
    if missing:
        raise StageError(f"required secrets missing from {source.label}: {', '.join(missing)}")
    return values


def _write(path: Path, value: str, owner: tuple[int, int] | None) -> None:
    """Write next to the target, set owner and mode, then rename, so a reader never sees a partial file."""
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.unlink(missing_ok=True)
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(value)
    if owner is not None:
        os.chown(temporary, *owner)
    temporary.chmod(FILE_MODE)
    temporary.replace(path)


def stage(values: Mapping[str, str], dest: Path, *, chown: bool) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    dest.chmod(DIRECTORY_MODE)
    written: list[Path] = []
    for secret in SECRETS:
        for consumer in secret.consumers:
            directory = dest / consumer
            directory.mkdir(exist_ok=True)
            directory.chmod(DIRECTORY_MODE)
            target = directory / secret.variable
            _write(target, values[secret.variable], CONSUMERS[consumer] if chown else None)
            written.append(target)
    return written


def check(dest: Path, *, chown: bool) -> list[str]:
    """Problems with the staged files, from their metadata only: present, mode 0400, owner, non-empty if required."""
    problems: list[str] = []
    for secret in SECRETS:
        for consumer in secret.consumers:
            path = dest / consumer / secret.variable
            try:
                info = path.stat()
            except FileNotFoundError:
                problems.append(f"{consumer}/{secret.variable} is missing")
                continue
            if not stat.S_ISREG(info.st_mode):
                problems.append(f"{consumer}/{secret.variable} is not a regular file")
            elif stat.S_IMODE(info.st_mode) != FILE_MODE:
                problems.append(f"{consumer}/{secret.variable} must be mode 0400")
            elif chown and (info.st_uid, info.st_gid) != CONSUMERS[consumer]:
                problems.append(f"{consumer}/{secret.variable} must be owned by uid {CONSUMERS[consumer][0]}")
            elif secret.required and info.st_size == 0:
                problems.append(f"{consumer}/{secret.variable} is empty")
    return problems


def main(argv: list[str] | None = None, *, geteuid: Callable[[], int] = os.geteuid) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    stage_parser = commands.add_parser("stage", help="read the secrets from a source and write the files")
    stage_parser.add_argument("--source", choices=["keyvault", "env-file"], required=True)
    stage_parser.add_argument("--vault", help="the Key Vault name (keyvault source)")
    stage_parser.add_argument("--env-file", type=Path, help="the server env file (env-file source)")
    check_parser = commands.add_parser("check", help="verify the staged files without reading them")
    for sub in (stage_parser, check_parser):
        sub.add_argument("--dest", type=Path, default=DEFAULT_DEST)
        sub.add_argument(
            "--no-chown",
            action="store_true",
            help="keep the files owned by the caller (Docker Desktop test hosts only; a Linux host needs the owners)",
        )
    arguments = parser.parse_args(argv)
    chown = not arguments.no_chown
    try:
        if arguments.command == "check":
            problems = check(arguments.dest, chown=chown)
            for problem in problems:
                say(problem)
            if problems:
                return 1
            say(f"every secret file under {arguments.dest} is in place")
            return 0
        if chown and geteuid() != 0:
            raise StageError("run as root (sudo) so the files can be given to each container's user")
        source: Source
        if arguments.source == "keyvault":
            if not arguments.vault:
                raise StageError("--vault is required with --source keyvault")
            source = KeyVaultSource(arguments.vault)
        else:
            if arguments.env_file is None:
                raise StageError("--env-file is required with --source env-file")
            source = EnvFileSource(arguments.env_file)
        values = collect(source)
        written = stage(values, arguments.dest, chown=chown)
        empty = sorted({secret.variable for secret in SECRETS if not values[secret.variable]})
        note = f"; empty optional secrets: {', '.join(empty)}" if empty else ""
        say(f"staged {len(written)} files from {source.label} under {arguments.dest}{note}")
        return 0
    except StageError as error:
        say(f"error: {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
