"""CLI テスト共通フィクスチャ・ヘルパー。"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import patch

import pytest

from hachimoku.agents import AgentDefinition, LoadError, LoadResult

PATCH_LOAD_AGENTS = "hachimoku.cli._app.load_agents"
PATCH_LOAD_BUILTIN_AGENTS = "hachimoku.cli._app.load_builtin_agents"
PATCH_FIND_PROJECT_ROOT = "hachimoku.cli._app.find_project_root"


@pytest.fixture(autouse=True)
def _mock_project_root() -> Iterator[None]:
    """テスト環境に依存しないプロジェクトルートを提供する。

    agents コマンドの find_project_root() が
    テスト実行環境のファイルシステムに依存しないようにする。
    個別テストで @patch(PATCH_FIND_PROJECT_ROOT, return_value=None) でオーバーライド可能。
    """
    with patch(PATCH_FIND_PROJECT_ROOT, return_value=None):
        yield


def make_agent_definition(
    name: str = "test-agent",
    model: str = "test-model",
    phase: str = "main",
    output_schema: str = "scored_issues",
    description: str = "Test agent description",
    system_prompt: str = "Test system prompt for testing purposes.",
    applicability: dict[str, object] | None = None,
    allowed_tools: tuple[str, ...] = (),
) -> AgentDefinition:
    """テスト用の最小 AgentDefinition を生成する。"""
    data: dict[str, object] = {
        "name": name,
        "description": description,
        "model": model,
        "output_schema": output_schema,
        "system_prompt": system_prompt,
        "phase": phase,
        "allowed_tools": allowed_tools,
    }
    if applicability is not None:
        data["applicability"] = applicability
    return AgentDefinition.model_validate(data)


def make_load_result(
    agents: tuple[AgentDefinition, ...] = (),
    errors: tuple[LoadError, ...] = (),
) -> LoadResult:
    """テスト用の LoadResult を生成する。"""
    return LoadResult(agents=agents, errors=errors)
