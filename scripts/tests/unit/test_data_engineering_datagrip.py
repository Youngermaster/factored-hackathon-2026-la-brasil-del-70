"""Inspection authentication fails closed without disclosing credentials."""

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest


def helper() -> ModuleType:
    path = Path(__file__).resolve().parents[3] / "deploy/data-engineering/datagrip.py"
    spec = importlib.util.spec_from_file_location("datagrip", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "address",
    [
        "10.0.0.1",
        "127.0.0.1",
        "181.140.234.12/32",
        "0.0.0.0",  # noqa: S104
        "::1",
    ],
)
def test_nonpublic_or_broad_sources_are_refused(address: str) -> None:
    with pytest.raises(ValueError, match=r"."):
        helper().public_ipv4(address)


def test_tls_only_inspection_does_not_replace_local_application_authentication() -> None:
    module = helper()
    original = "local all all trust\nhost all all 172.16.0.0/12 scram-sha-256\n"
    rules = module.hba_rules(original, "181.140.234.12")
    assert rules.index("hostssl bank_agent bank_datagrip 181.140.234.12/32 scram-sha-256") < rules.index(
        "host all bank_datagrip 0.0.0.0/0 reject"
    )
    assert "host all bank_datagrip ::/0 reject" in rules
    assert "host all all 181.140.234.12/32 reject" in rules
    assert rules.endswith(original)
    assert module.hba_rules(rules, "181.140.234.12") == rules
    changed = module.hba_rules(rules, "8.8.8.8")
    assert "181.140.234.12" not in changed
    assert changed.endswith(original)


def test_unfinished_authentication_configuration_is_refused() -> None:
    module = helper()
    with pytest.raises(ValueError, match="incomplete"):
        module.hba_rules(module.HBA_BEGIN, "181.140.234.12")


def test_terminal_is_required_before_any_password_or_cloud_operation(monkeypatch: pytest.MonkeyPatch) -> None:
    module = helper()
    monkeypatch.setattr(module.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(module, "execute", lambda *_args: pytest.fail("noninteractive setup reached Azure"))
    with pytest.raises(ValueError, match="interactive"):
        module.client_password()


def test_failed_subprocess_diagnostics_never_expose_authentication(monkeypatch: pytest.MonkeyPatch) -> None:
    module = helper()
    marker = b"private-authentication-material"
    monkeypatch.setattr(
        module.subprocess, "run", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 1, marker, marker)
    )
    with pytest.raises(RuntimeError) as failure:
        module.execute(["unused"], marker)
    assert marker.decode() not in str(failure.value)


@pytest.mark.parametrize("candidate", ["short", "a" * 129, "has spaces" * 3, "nonascii-contraseña-123"])
def test_unsupported_passwords_are_refused(candidate: str) -> None:
    with pytest.raises(ValueError, match=r"."):
        helper().scram_verifier(candidate, b"fixed-salt")


def test_password_validation_explains_the_requirement_without_showing_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = helper()
    monkeypatch.setattr(module.sys, "argv", ["datagrip.py", "password"])
    monkeypatch.setattr(module, "client_password", lambda: module.scram_verifier("short", b"salt"))
    with pytest.raises(SystemExit, match="1"):
        module.main()
    message = capsys.readouterr().err
    assert "16 y 128" in message
    assert "short" not in message


def test_existing_releases_remain_readable_and_new_names_take_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = helper()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    revision = "a" * 40
    legacy = tmp_path / "releases" / revision / "deploy/azure-data/compose.yml"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("previous release")
    assert module.release_compose(revision) == legacy
    current = legacy.parents[1] / "data-engineering/compose.yml"
    current.parent.mkdir()
    current.write_text("current release")
    assert module.release_compose(revision) == current
    with pytest.raises(ValueError, match="invalid committed release"):
        module.release_compose("../another-release")
