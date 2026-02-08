"""cli/__init__.py の公開 API テスト。

app インスタンスと main エントリポイントの基本動作を検証する。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import typer
from typer.testing import CliRunner

from hachimoku.cli import app
from hachimoku.engine._engine import EngineResult
from hachimoku.models.config import HachimokuConfig
from hachimoku.models.exit_code import ExitCode
from hachimoku.models.report import ReviewReport, ReviewSummary

runner = CliRunner()

_PATCH_RUN_REVIEW = "hachimoku.cli._app.run_review"
_PATCH_RESOLVE_CONFIG = "hachimoku.cli._app.resolve_config"


def _make_engine_result() -> EngineResult:
    return EngineResult(
        report=ReviewReport(
            results=[],
            summary=ReviewSummary(
                total_issues=0,
                max_severity=None,
                total_elapsed_time=0.0,
            ),
        ),
        exit_code=ExitCode.SUCCESS,
    )


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

    @patch(_PATCH_RUN_REVIEW, new_callable=AsyncMock)
    @patch(_PATCH_RESOLVE_CONFIG)
    def test_no_args_exits_with_zero(
        self, mock_config: MagicMock, mock_run_review: AsyncMock
    ) -> None:
        """引数なしで実行してもエラーにならない。"""
        mock_config.return_value = HachimokuConfig()
        mock_run_review.return_value = _make_engine_result()
        result = runner.invoke(app)
        assert result.exit_code == 0
