"""ReviewEngine のテスト。

T026: EngineResult モデル検証、_filter_disabled_agents、
run_review パイプラインの統合テスト。
FR-RE-002: エージェント実行パイプライン全体の統括。
FR-RE-009: 全エージェント失敗時の exit_code=3。
FR-RE-010: 空選択時の正常終了（exit_code=0）。
FR-RE-014: load_errors のレポート記録。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hachimoku.agents.models import (
    AgentDefinition,
    ApplicabilityRule,
    LoadError,
    LoadResult,
    Phase,
)
from hachimoku.engine._engine import EngineResult, _filter_disabled_agents, run_review
from hachimoku.engine._selector import SelectorError, SelectorOutput
from hachimoku.engine._target import DiffTarget
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.agent_result import AgentError, AgentSuccess
from hachimoku.models.config import HachimokuConfig
from hachimoku.models.report import ReviewReport
from hachimoku.models.review import ReviewIssue
from hachimoku.models.severity import Severity


def _make_agent(
    name: str = "test-agent",
    phase: Phase = Phase.MAIN,
) -> AgentDefinition:
    """テスト用 AgentDefinition を生成するヘルパー。"""
    return AgentDefinition(  # type: ignore[call-arg]
        name=name,
        description="Test agent",
        model="test",
        output_schema="scored_issues",
        system_prompt="You are a test agent.",
        applicability=ApplicabilityRule(always=True),
        phase=phase,
    )


def _make_target() -> DiffTarget:
    """テスト用 DiffTarget を生成するヘルパー。"""
    return DiffTarget(base_branch="main")


def _make_success(
    agent_name: str = "test-agent",
    issues: list[ReviewIssue] | None = None,
) -> AgentSuccess:
    """テスト用 AgentSuccess を生成するヘルパー。"""
    return AgentSuccess(
        agent_name=agent_name,
        issues=issues or [],
        elapsed_time=1.0,
    )


def _make_error(agent_name: str = "test-agent") -> AgentError:
    """テスト用 AgentError を生成するヘルパー。"""
    return AgentError(
        agent_name=agent_name,
        error_message="test error",
    )


def _make_issue(severity: Severity = Severity.SUGGESTION) -> ReviewIssue:
    """テスト用 ReviewIssue を生成するヘルパー。"""
    return ReviewIssue(
        agent_name="test-agent",
        severity=severity,
        description="Test issue",
    )


# =============================================================================
# EngineResult モデル — 正常系
# =============================================================================


class TestEngineResultValid:
    """EngineResult モデルの正常系テスト。"""

    def test_valid_construction(self) -> None:
        """正常なデータで構築できる。"""
        from hachimoku.models.report import ReviewSummary

        report = ReviewReport(
            results=[],
            summary=ReviewSummary(
                total_issues=0,
                max_severity=None,
                total_elapsed_time=0.0,
            ),
        )
        result = EngineResult(report=report, exit_code=0)
        assert result.exit_code == 0
        assert result.report is report

    def test_inherits_base_model(self) -> None:
        """HachimokuBaseModel を継承している。"""
        assert issubclass(EngineResult, HachimokuBaseModel)

    def test_frozen(self) -> None:
        """frozen=True で不変である。"""
        from hachimoku.models.report import ReviewSummary

        report = ReviewReport(
            results=[],
            summary=ReviewSummary(
                total_issues=0,
                max_severity=None,
                total_elapsed_time=0.0,
            ),
        )
        result = EngineResult(report=report, exit_code=0)
        with pytest.raises(Exception):
            result.exit_code = 1  # type: ignore[misc]

    def test_all_exit_codes_valid(self) -> None:
        """exit_code の全有効値（0, 1, 2, 3）が構築できる。"""
        from hachimoku.models.report import ReviewSummary

        report = ReviewReport(
            results=[],
            summary=ReviewSummary(
                total_issues=0,
                max_severity=None,
                total_elapsed_time=0.0,
            ),
        )
        for code in (0, 1, 2, 3):
            result = EngineResult(
                report=report,
                exit_code=code,  # type: ignore[arg-type]
            )
            assert result.exit_code == code


# =============================================================================
# _filter_disabled_agents
# =============================================================================


class TestFilterDisabledAgents:
    """_filter_disabled_agents のテスト。"""

    def test_filters_disabled(self) -> None:
        """disabled エージェントが除外される。"""
        agents = (
            _make_agent("agent-a"),
            _make_agent("agent-b"),
            _make_agent("agent-c"),
        )
        load_result = LoadResult(agents=agents)
        disabled = frozenset({"agent-b"})

        filtered, removed = _filter_disabled_agents(load_result, disabled)

        agent_names = [a.name for a in filtered.agents]
        assert "agent-a" in agent_names
        assert "agent-b" not in agent_names
        assert "agent-c" in agent_names
        assert removed == ["agent-b"]

    def test_no_disabled(self) -> None:
        """全有効 → 全通過。"""
        agents = (_make_agent("agent-a"), _make_agent("agent-b"))
        load_result = LoadResult(agents=agents)
        disabled: frozenset[str] = frozenset()

        filtered, removed = _filter_disabled_agents(load_result, disabled)

        assert len(filtered.agents) == 2
        assert removed == []

    def test_all_disabled(self) -> None:
        """全無効 → 空。"""
        agents = (_make_agent("agent-a"), _make_agent("agent-b"))
        load_result = LoadResult(agents=agents)
        disabled = frozenset({"agent-a", "agent-b"})

        filtered, removed = _filter_disabled_agents(load_result, disabled)

        assert len(filtered.agents) == 0
        assert set(removed) == {"agent-a", "agent-b"}

    def test_preserves_errors(self) -> None:
        """フィルタ後も load_errors が保持される。"""
        agents = (_make_agent("agent-a"),)
        errors = (LoadError(source="bad.toml", message="parse error"),)
        load_result = LoadResult(agents=agents, errors=errors)
        disabled: frozenset[str] = frozenset()

        filtered, _ = _filter_disabled_agents(load_result, disabled)

        assert filtered.errors == errors

    def test_returns_removed_names(self) -> None:
        """除外されたエージェント名がリストで返される。"""
        agents = (
            _make_agent("agent-a"),
            _make_agent("agent-b"),
            _make_agent("agent-c"),
        )
        load_result = LoadResult(agents=agents)
        disabled = frozenset({"agent-a", "agent-c"})

        _, removed = _filter_disabled_agents(load_result, disabled)

        assert set(removed) == {"agent-a", "agent-c"}


# =============================================================================
# run_review — パイプライン統合テスト
# =============================================================================


class TestRunReviewPipeline:
    """run_review パイプラインの統合テスト。

    内部依存をモック化し、パイプラインのオーケストレーションロジックを検証する。
    """

    @patch("hachimoku.engine._engine.execute_sequential")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_full_pipeline_success(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        """全ステップが正常に完了し、EngineResult が返される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Applicable",
        )
        mock_execute.return_value = [_make_success("agent-a")]

        result = await run_review(target=_make_target())

        assert isinstance(result, EngineResult)
        assert result.exit_code == 0
        assert len(result.report.results) == 1

    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_selector_failure_exit_code_3(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        mock_selector: AsyncMock,
    ) -> None:
        """セレクター失敗時に exit_code=3 が返される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_selector.side_effect = SelectorError("Selector timeout")

        result = await run_review(target=_make_target())

        assert result.exit_code == 3
        assert len(result.report.results) == 0

    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_empty_selection_exit_code_0(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        mock_selector: AsyncMock,
    ) -> None:
        """空選択で exit_code=0 が返される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_selector.return_value = SelectorOutput(
            selected_agents=[],
            reasoning="No applicable agents",
        )

        result = await run_review(target=_make_target())

        assert result.exit_code == 0
        assert len(result.report.results) == 0

    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_load_errors_in_report(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        mock_selector: AsyncMock,
    ) -> None:
        """読み込みエラーがレポートに記録される。"""
        mock_config.return_value = HachimokuConfig()
        errors = (LoadError(source="broken.toml", message="parse error"),)
        mock_load.return_value = LoadResult(
            agents=(_make_agent("agent-a"),),
            errors=errors,
        )
        mock_selector.return_value = SelectorOutput(
            selected_agents=[],
            reasoning="No match",
        )

        result = await run_review(target=_make_target())

        assert len(result.report.load_errors) == 1
        assert result.report.load_errors[0].source == "broken.toml"

    @patch("hachimoku.engine._engine.execute_sequential")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_all_agents_failed_exit_code_3(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        """全エージェント失敗で exit_code=3 が返される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Selected",
        )
        mock_execute.return_value = [_make_error("agent-a")]

        result = await run_review(target=_make_target())

        assert result.exit_code == 3

    @patch("hachimoku.engine._engine.execute_sequential")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_severity_determines_exit_code(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        """Critical issue があると exit_code=1 が返される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Selected",
        )
        critical_issue = _make_issue(Severity.CRITICAL)
        mock_execute.return_value = [
            _make_success("agent-a", issues=[critical_issue]),
        ]

        result = await run_review(target=_make_target())

        assert result.exit_code == 1

    @patch("hachimoku.engine._engine.execute_sequential")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_disabled_agents_excluded(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        """disabled エージェントがセレクターに渡されない。"""
        from hachimoku.models.config import AgentConfig

        config = HachimokuConfig(
            agents={"agent-b": AgentConfig(enabled=False)},
        )
        mock_config.return_value = config
        mock_load.return_value = LoadResult(
            agents=(_make_agent("agent-a"), _make_agent("agent-b")),
        )
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Selected",
        )
        mock_execute.return_value = [_make_success("agent-a")]

        result = await run_review(target=_make_target())

        # run_selector に渡された available_agents を確認
        call_args = mock_selector.call_args
        available = call_args.kwargs.get("available_agents") or call_args.args[1]
        agent_names = [a.name for a in available]
        assert "agent-b" not in agent_names
        assert "agent-a" in agent_names
        assert result.exit_code == 0
