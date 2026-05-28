from pathlib import Path

from typer.testing import CliRunner

from do_my_work.cli import app

runner = CliRunner()


def test_hello_command_without_config_uses_defaults() -> None:
    result = runner.invoke(app, ["hello"])

    assert result.exit_code == 0
    assert "Hello, world!" in result.stdout


def test_hello_command_with_yaml_config(tmp_path: Path) -> None:
    config_file = tmp_path / "hello.yaml"
    config_file.write_text("greeting: Salut\ntarget: équipe\n", encoding="utf-8")

    result = runner.invoke(app, ["hello", "--config", str(config_file)])

    assert result.exit_code == 0
    assert "Salut, équipe!" in result.stdout