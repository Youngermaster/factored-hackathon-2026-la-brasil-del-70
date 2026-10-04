"""Rehearse a private backup in a disposable PostgreSQL container without exposing a network port."""

import argparse
import hashlib
import json
import secrets
import subprocess
import time
from pathlib import Path

IMAGE = "postgres:16.15-alpine3.24@sha256:721873c34ceb9f8d8fc265984940dc982404c105f19ad51be9fdc5970a6080ea"
TABLES = ("customers", "products", "transactions", "historical_complaints", "credit_profiles")


def run(arguments: list[str], payload: bytes | None = None) -> bytes:
    result = subprocess.run(arguments, input=payload, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("restore verification failed; database values and diagnostics withheld")
    return result.stdout


def verify(backup: Path, manifest: Path, output: Path | None = None) -> None:
    expected = json.loads(manifest.read_text())["backup"]
    with backup.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != expected["backup_sha256"]:
            raise ValueError("backup SHA-256 mismatch; restore refused")
    name = "data-engineering-restore-" + secrets.token_hex(6)

    def sql(statement: str) -> str:
        return (
            run(
                [
                    "docker",
                    "exec",
                    "-i",
                    name,
                    "psql",
                    "-X",
                    "-q",
                    "-v",
                    "ON_ERROR_STOP=1",
                    "-U",
                    "postgres",
                    "-d",
                    "bank_agent",
                    "-At",
                ],
                statement.encode(),
            )
            .decode()
            .strip()
        )

    try:
        run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                name,
                "--network",
                "none",
                "--user",
                "70:70",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges:true",
                "--tmpfs",
                "/var/run/postgresql:uid=70,gid=70,mode=0775,size=8m",
                "--tmpfs",
                "/tmp:uid=70,gid=70,size=64m",  # noqa: S108 -- private container tmpfs, no host temporary file.
                "-e",
                "POSTGRES_HOST_AUTH_METHOD=trust",
                "-e",
                "POSTGRES_DB=bank_agent",
                IMAGE,
            ]
        )
        for _ in range(60):
            ready = subprocess.run(
                ["docker", "exec", name, "pg_isready", "-U", "postgres", "-d", "bank_agent"],
                capture_output=True,
                check=False,
            )
            if ready.returncode == 0:
                break
            time.sleep(1)
        else:
            raise RuntimeError("disposable restore database did not become ready")
        for role in ("bank_owner", "bank_app", "bank_evaluator", "bank_datagrip"):
            sql(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;")
        with backup.open("rb") as source:
            restored = subprocess.run(
                ["docker", "exec", "-i", name, "pg_restore", "-U", "postgres", "-d", "bank_agent", "--exit-on-error"],
                stdin=source,
                capture_output=True,
                check=False,
            )
        if restored.returncode:
            raise RuntimeError("backup restore failed; raw database diagnostics withheld")
        if sql("SELECT version_num FROM app.alembic_version;") != expected["schema"]:
            raise ValueError("restored schema mismatch")
        for table in TABLES:
            query = "SELECT json_build_object('count',count(*),'md5',md5(string_agg(row_to_json(t)::text,'' "
            query += f"ORDER BY row_to_json(t)::text))) FROM app.{table} t;"
            if json.loads(sql(query)) != expected["references"][table]:
                raise ValueError("restored reference values mismatch")
        if sql("SET ROLE bank_app; SELECT count(*) FROM app.customers; RESET ROLE;") != "0":
            raise ValueError("restored application isolation failed")
        inspector = sql("SET ROLE bank_datagrip; SELECT count(*) FROM app.customers; RESET ROLE;")
        if int(inspector) != expected["references"]["customers"]["count"]:
            raise ValueError("restored inspection grants failed")
        if output is not None:
            record = {
                "verified": True,
                "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
                "backup_sha256": expected["backup_sha256"],
            }
            output.write_text(json.dumps(record) + "\n")
            output.chmod(0o600)
        print("Restore verified: schema, five reference hashes/counts, application RLS, and inspection grants.")
    finally:
        run(["docker", "rm", "-f", "-v", name])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        verify(args.backup, args.manifest, args.output)
    except Exception as error:
        raise SystemExit(f"Restore verification failed ({type(error).__name__}); no database values printed.") from None


if __name__ == "__main__":
    main()
