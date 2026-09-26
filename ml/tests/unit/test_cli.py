from typer.testing import CliRunner

from bank_ml import __version__
from bank_ml.cli import app

runner = CliRunner()


def test_help_lists_the_version_command() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "version" in result.output


def test_no_arguments_shows_help() -> None:
    result = runner.invoke(app, [])

    assert "Usage" in result.output


def test_version_prints_distribution_name_and_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"bank-ml {__version__}"
