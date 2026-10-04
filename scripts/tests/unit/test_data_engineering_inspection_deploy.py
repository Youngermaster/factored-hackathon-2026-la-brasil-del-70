"""The CLI opens inspection ingress only after verifying TLS configuration and the exact source."""

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("verified", [True, False])
def test_inspection_ingress_requires_verified_server_configuration(tmp_path: Path, verified: bool) -> None:
    project = tmp_path / "project"
    entrypoint = project / "deploy/data-engineering/deploy.sh"
    entrypoint.parent.mkdir(parents=True)
    entrypoint.write_bytes((ROOT / "deploy/data-engineering/deploy.sh").read_bytes())
    tools = tmp_path / "bin"
    tools.mkdir()
    trace = tmp_path / "azure-operations"
    metadata = json.dumps({"host": "13.66.169.189", "client_ipv4": "181.140.234.12", "tls": verified})
    az = tools / "az"
    az.write_text(
        "#!/usr/bin/python3\nimport sys\nfrom pathlib import Path\n"
        f"args = ' '.join(sys.argv[1:])\ntrace = Path({str(trace)!r})\n"
        "with trace.open('a') as output: output.write(args + '\\n')\n"
        "if 'tenantId' in args: print('4a5e7334-7901-444c-964b-3e6100209fd1')\n"
        "elif 'user.name' in args: print('valenciajuliann@hotmail.com')\n"
        "elif 'group show' in args: print('westus2')\n"
        "elif 'public-ip show' in args: print('13.66.169.189')\n"
        f"elif 'run-command invoke' in args: print({metadata!r})\n"
    )
    az.chmod(0o700)
    git = tools / "git"
    git.write_text("#!/bin/sh\ncase \"$1\" in rev-parse) printf '%040d\\n' 1 ;; show) printf '# code\\n' ;; esac\n")
    git.chmod(0o700)
    result = subprocess.run(
        ["bash", str(entrypoint), "datagrip", "181.140.234.12"],
        env={"PATH": f"{tools}:/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    operations = trace.read_text().splitlines()
    network = [line for line in operations if "nsg rule" in line]
    if not verified:
        assert result.returncode != 0
        assert not network
        assert "ingress was not changed" in result.stderr
    else:
        assert result.returncode == 0
        assert len(network) == 2
        assert "--priority 200" in network[0]
        assert "--source-address-prefixes 181.140.234.12/32" in network[1]
        assert "--destination-port-ranges 5432" in network[1]
        assert "--protocol Tcp" in network[1]
        assert all("-g rg-data-engineering-test" in line for line in network)
        assert "Data engineering inspection ready" in result.stdout
