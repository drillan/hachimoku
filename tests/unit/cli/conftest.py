"""CLI テスト共通フィクスチャ・ヘルパー。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from hachimoku.engine._engine import EngineResult
from hachimoku.models.config import HachimokuConfig
from hachimoku.models.exit_code import ExitCode
from hachimoku.models.report import ReviewReport, ReviewSummary

PATCH_RUN_REVIEW = "hachimoku.cli._app.run_review"
PATCH_RESOLVE_CONFIG = "hachimoku.cli._app.resolve_config"


def make_engine_result(exit_code: ExitCode = ExitCode.SUCCESS) -> EngineResult:
    """テスト用の最小 EngineResult を生成する。"""
    return EngineResult(
        report=ReviewReport(
            results=[],
            summary=ReviewSummary(
                total_issues=0,
                max_severity=None,
                total_elapsed_time=0.0,
            ),
        ),
        exit_code=exit_code,
    )


def setup_mocks(
    mock_config: MagicMock,
    mock_run_review: AsyncMock,
    exit_code: ExitCode = ExitCode.SUCCESS,
) -> None:
    """共通のモックセットアップ。"""
    mock_config.return_value = HachimokuConfig()
    mock_run_review.return_value = make_engine_result(exit_code)
