"""TLS inspection access and interactive encrypted password provisioning for the dedicated data VM."""

import argparse
import base64
import fcntl
import getpass
import hashlib
import hmac
import ipaddress
import json
import re
import secrets
import socket
import ssl
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path("/opt/la70-data")
SUBSCRIPTION = "32847dfa-5fd4-4276-8bdf-243d72b35119"
TENANT = "4a5e7334-7901-444c-964b-3e6100209fd1"
TABLES = ("customers", "products", "transactions", "historical_complaints", "credit_profiles")
HBA_BEGIN = "# BEGIN la70 DataGrip\n"
HBA_END = "# END la70 DataGrip\n"


class PasswordInputError(ValueError):
    """A fixed validation message that contains no user input or authentication material."""


def execute(arguments: list[str], payload: bytes | None = None) -> bytes:
    """Never echo subprocess inputs or diagnostics that could contain authentication material."""
    result = subprocess.run(arguments, input=payload, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError("administrative operation failed; no credentials were printed")
    return result.stdout


def psql(statement: str) -> bytes:
    # Password updates pass only a SCRAM verifier through stdin; suppress statement logging before that update.
    return execute(
        [
            "docker",
            "exec",
            "-i",
            "la70-data-postgres-1",
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


def public_ipv4(value: str) -> str:
    address = ipaddress.IPv4Address(value)
    if not address.is_global:
        raise ValueError("a public IPv4 address is required")
    return str(address)


def hba_rules(previous: str, client: str) -> str:
    client = public_ipv4(client)
    if HBA_BEGIN in previous:
        if HBA_END not in previous:
            raise ValueError("incomplete managed authentication block")
        prefix, remainder = previous.split(HBA_BEGIN, 1)
        previous = prefix + remainder.split(HBA_END, 1)[1]
    return (
        HBA_BEGIN
        + f"hostssl bank_agent bank_datagrip {client}/32 scram-sha-256\n"
        + "host all bank_datagrip 0.0.0.0/0 reject\n"
        + "host all bank_datagrip ::/0 reject\n"
        + f"host all all {client}/32 reject\n"
        + HBA_END
        + previous
    )


def scram_verifier(password: str, salt: bytes) -> bytes:
    if not 16 <= len(password) <= 128 or any(not 33 <= ord(char) <= 126 for char in password):
        raise PasswordInputError("Usa entre 16 y 128 caracteres ASCII, sin espacios, tildes ni ñ.")
    iterations = 16384
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    client_key = hmac.digest(salted, b"Client Key", "sha256")
    stored_key = hashlib.sha256(client_key).digest()
    server_key = hmac.digest(salted, b"Server Key", "sha256")
    encoded = [base64.b64encode(item).decode() for item in (salt, stored_key, server_key)]
    return f"SCRAM-SHA-256${iterations}:{encoded[0]}${encoded[1]}:{encoded[2]}".encode()


def release_compose(revision: str) -> Path:
    if re.fullmatch(r"[0-9a-f]{40}", revision) is None:
        raise ValueError("invalid committed release")
    release = ROOT / "releases" / revision / "deploy"
    current = release / "data-engineering/compose.yml"
    if current.is_file():
        return current
    # Existing immutable releases predate the repository naming convention.
    legacy = release / "azure-data/compose.yml"
    if legacy.is_file():
        return legacy
    raise ValueError("release Compose file unavailable")


def configure(host: str, client: str) -> None:
    host, client = public_ipv4(host), public_ipv4(client)
    with (ROOT / "pipeline.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        tls = ROOT / "tls"
        tls.mkdir(mode=0o700, exist_ok=True)
        key, certificate = tls / "server.key", tls / "server.crt"
        if key.exists() != certificate.exists():
            raise ValueError("incomplete server TLS configuration")
        renew = not certificate.exists()
        if not renew:
            try:
                execute(["openssl", "x509", "-in", str(certificate), "-noout", "-checkip", host])
                execute(["openssl", "x509", "-in", str(certificate), "-noout", "-checkend", "3600"])
            except RuntimeError:
                renew = True
        if renew:
            next_key, next_certificate = tls / "server.key.next", tls / "server.crt.next"
            execute(
                [
                    "openssl",
                    "req",
                    "-x509",
                    "-newkey",
                    "rsa:4096",
                    "-nodes",
                    "-sha256",
                    "-days",
                    "90",
                    "-keyout",
                    str(next_key),
                    "-out",
                    str(next_certificate),
                    "-subj",
                    f"/CN={host}",
                    "-addext",
                    f"subjectAltName=IP:{host}",
                ]
            )
            next_key.replace(key)
            next_certificate.replace(certificate)
        execute(["openssl", "x509", "-in", str(certificate), "-noout", "-checkip", host])
        execute(["chown", "-R", "70:70", str(tls)])
        tls.chmod(0o700)
        key.chmod(0o600)
        certificate.chmod(0o644)
        run = (ROOT / "latest-run").read_text().strip()
        revision = json.loads((ROOT / "runs" / run / "result.json").read_text())["code_revision"]
        base = release_compose(revision)
        override = ROOT / "datagrip.compose.yml"
        override.write_text(
            'services:\n  postgres:\n    ports: !override ["0.0.0.0:5432:5432"]\n'
            "    volumes:\n      - /opt/la70-data/tls:/run/la70-postgres-tls:ro\n"
            '    command: ["postgres", "-c", "ssl=on", "-c", '
            '"ssl_cert_file=/run/la70-postgres-tls/server.crt", "-c", '
            '"ssl_key_file=/run/la70-postgres-tls/server.key", "-c", "ssl_min_protocol_version=TLSv1.2"]\n'
        )
        override.chmod(0o600)
        execute(["docker", "compose", "-f", str(base), "-f", str(override), "config", "--quiet"])
        execute(["docker", "compose", "-f", str(base), "-f", str(override), "up", "-d", "--wait"])
        hba_path = "/var/lib/postgresql/data/pg_hba.conf"
        previous = execute(["docker", "exec", "la70-data-postgres-1", "cat", hba_path]).decode()
        backup = ROOT / "datagrip.original-hba.conf"
        if not backup.exists():
            backup.write_text(previous)
            backup.chmod(0o600)
        execute(
            ["docker", "exec", "-i", "la70-data-postgres-1", "sh", "-c", f"cat > {hba_path}"],
            hba_rules(previous, client).encode(),
        )
        psql("SELECT pg_reload_conf();")
        psql(Path(__file__).with_name("datagrip-readonly.sql").read_text())
        config = ROOT / "datagrip.json"
        config.write_text(json.dumps({"host": host, "client_ipv4": client, "user": "bank_datagrip"}) + "\n")
        config.chmod(0o600)
        print(
            json.dumps(
                {
                    "host": host,
                    "port": 5432,
                    "database": "bank_agent",
                    "user": "bank_datagrip",
                    "tls": True,
                    "client_ipv4": client,
                    "password": "set interactively by operator",
                }
            )
        )


def apply_password(ciphertext: str) -> None:
    encrypted = base64.b64decode(ciphertext, validate=True)
    if len(encrypted) != 512:
        raise ValueError("invalid encrypted verifier size")
    verifier = execute(
        [
            "openssl",
            "pkeyutl",
            "-decrypt",
            "-inkey",
            str(ROOT / "tls/server.key"),
            "-pkeyopt",
            "rsa_padding_mode:oaep",
            "-pkeyopt",
            "rsa_oaep_md:sha256",
            "-pkeyopt",
            "rsa_mgf1_md:sha256",
        ],
        encrypted,
    ).decode()
    if re.fullmatch(r"SCRAM-SHA-256\$16384:[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+:[A-Za-z0-9+/=]+", verifier) is None:
        raise ValueError("invalid SCRAM verifier")
    psql(
        "SET log_statement='none'; SET log_min_error_statement='panic'; "
        "SET log_parameter_max_length_on_error=0; "
        f"ALTER ROLE bank_datagrip LOGIN PASSWORD '{verifier}';"
    )
    print("DataGrip password configured; plaintext never reached Azure Run Command.")


def invoke(script: str) -> str:
    raw = execute(
        [
            "az",
            "vm",
            "run-command",
            "invoke",
            "-g",
            "rg-bank-agent",
            "-n",
            "vm-bank-database",
            "--subscription",
            SUBSCRIPTION,
            "--command-id",
            "RunShellScript",
            "--scripts",
            script,
            "--only-show-errors",
            "-o",
            "json",
        ]
    )
    result = json.loads(raw)
    messages = "\n".join(item["message"] for item in result["value"])
    return str(messages)


def connection_info() -> tuple[str, Path]:
    account = json.loads(execute(["az", "account", "show", "--subscription", SUBSCRIPTION, "-o", "json"]))
    if account["tenantId"] != TENANT or account["user"]["name"] != "valenciajuliann@hotmail.com":
        raise ValueError("use the authorized Azure account and tenant")
    output = invoke("cat /opt/la70-data/tls/server.crt; cat /opt/la70-data/datagrip.json")
    found = re.search(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", output, re.S)
    if found is None:
        raise RuntimeError("server certificate unavailable")
    destination = Path("data/data-engineering/datagrip")
    destination.mkdir(parents=True, exist_ok=True)
    certificate = destination / "server.crt"
    certificate.write_text(found.group() + "\n")
    settings = next(json.loads(line) for line in output.splitlines() if line.startswith('{"host":'))
    if settings["user"] != "bank_datagrip":
        raise ValueError("unexpected inspection user")
    return public_ipv4(settings["host"]), certificate


def check_connection() -> None:
    host, certificate = connection_info()
    context = ssl.create_default_context(cafile=str(certificate))
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    with socket.create_connection((host, 5432), timeout=10) as connection:
        connection.sendall(struct.pack("!II", 8, 80877103))  # PostgreSQL SSLRequest, no authentication data.
        if connection.recv(1) != b"S":
            raise RuntimeError("PostgreSQL refused TLS")
        with context.wrap_socket(connection, server_hostname=host) as secured:
            print(f"TLS verified: {host}:5432, {secured.version()}; no password used.")
    print(f"CA certificate: {certificate.resolve()}")


def client_password() -> None:
    if not sys.stdin.isatty():
        raise ValueError("run password setup in an interactive terminal")
    host, certificate = connection_info()
    public_key = execute(["openssl", "x509", "-pubkey", "-noout", "-in", str(certificate)])
    password = getpass.getpass("Contraseña para DataGrip (16-128 caracteres ASCII, oculta): ")
    if password != getpass.getpass("Repite la contraseña (oculta): "):
        raise PasswordInputError("Las contraseñas no coinciden. Ejecuta el comando e inténtalo de nuevo.")
    verifier = scram_verifier(password, secrets.token_bytes(16))
    with tempfile.TemporaryDirectory() as temporary:
        public_path = Path(temporary) / "public.pem"
        public_path.write_bytes(public_key)
        encrypted = execute(
            [
                "openssl",
                "pkeyutl",
                "-encrypt",
                "-pubin",
                "-inkey",
                str(public_path),
                "-pkeyopt",
                "rsa_padding_mode:oaep",
                "-pkeyopt",
                "rsa_oaep_md:sha256",
                "-pkeyopt",
                "rsa_mgf1_md:sha256",
            ],
            verifier,
        )
    encoded = base64.b64encode(encrypted).decode()
    message = invoke(f"python3 /opt/la70-data/datagrip.py apply-password {encoded}")
    if "DataGrip password configured;" not in message:
        raise RuntimeError("password setup did not complete; no authentication material was printed")
    print(f"Password configured. DataGrip: {host}:5432 / bank_agent / bank_datagrip.")
    print(f"SSL mode: verify-full. CA certificate: {certificate.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("configure", "apply-password", "password", "check"))
    parser.add_argument("values", nargs="*")
    args = parser.parse_args()
    try:
        if args.action == "configure" and len(args.values) == 2:
            configure(args.values[0], args.values[1])
        elif args.action == "apply-password" and len(args.values) == 1:
            apply_password(args.values[0])
        elif args.action == "password" and not args.values:
            client_password()
        elif args.action == "check" and not args.values:
            check_connection()
        else:
            raise ValueError("invalid arguments")
    except PasswordInputError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1) from None
    except Exception as error:
        print(f"Operation failed ({type(error).__name__}); no credentials printed.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
