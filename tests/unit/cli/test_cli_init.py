"""cli/__init__.py の公開 API テスト。

app インスタンスと main エントリポイントの基本動作を検証する。
"""

import typer
from typer.testing import CliRunner

from hachimoku.cli import app

runner = CliRunner()


class TestAppInstance:
    """app インスタンスの属性を検証する。"""

    def test_app_is_typer_instance(self) -> None:
        assert isinstance(app, typer.Typer)

    def test_app_info_name(self) -> None:
        assert app.info.name == "8moku"


class TestHelpOutput:
    """--help の動作を検証する。"""

    def test_help_exits_with_zero(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_help_contains_tool_description(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert "Multi-agent code review" in result.output

    def test_no_args_exits_with_zero(self) -> None:
        """引数なしで実行してもエラーにならない。"""
        result = runner.invoke(app)
        assert result.exit_code == 0
