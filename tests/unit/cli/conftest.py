"""CLI テスト共通フィクスチャ・ヘルパー。"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from hachimoku.agents import AgentDefinition, LoadError, LoadResult
from hachimoku.engine._engine import EngineResult
from hachimoku.models.config import HachimokuConfig
from hachimoku.models.exit_code import ExitCode
from hachimoku.models.report import ReviewReport, ReviewSummary

PATCH_RUN_REVIEW = "hachimoku.cli._app.run_review"
PATCH_RESOLVE_CONFIG = "hachimoku.cli._app.resolve_config"
PATCH_RESOLVE_FILES = "hachimoku.cli._app.resolve_files"
PATCH_LOAD_AGENTS = "hachimoku.cli._app.load_agents"
PATCH_LOAD_BUILTIN_AGENTS = "hachimoku.cli._app.load_builtin_agents"
PATCH_FIND_PROJECT_ROOT = "hachimoku.cli._app.find_project_root"


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


def make_agent_definition(
    name: str = "test-agent",
    model: str = "test-model",
    phase: str = "main",
    output_schema: str = "scored_issues",
    description: str = "Test agent description",
) -> AgentDefinition:
    """テスト用の最小 AgentDefinition を生成する。"""
    return AgentDefinition.model_validate(
        {
            "name": name,
            "description": description,
            "model": model,
            "output_schema": output_schema,
            "system_prompt": "Test system prompt for testing purposes.",
            "phase": phase,
        }
    )


def make_load_result(
    agents: tuple[AgentDefinition, ...] = (),
    errors: tuple[LoadError, ...] = (),
) -> LoadResult:
    """テスト用の LoadResult を生成する。"""
    return LoadResult(agents=agents, errors=errors)
