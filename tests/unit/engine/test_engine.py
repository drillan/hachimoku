"""ReviewEngine のテスト。

T026: EngineResult モデル検証、_filter_disabled_agents、
run_review パイプラインの統合テスト。
T037: parallel 設定による実行モード切り替えテスト。
T042: SignalHandler の install/uninstall 統合テスト。
FR-RE-002: エージェント実行パイプライン全体の統括。
FR-RE-005: グレースフルシャットダウン。
FR-RE-006: parallel 設定に応じたフェーズ順序制御。
FR-RE-009: 全エージェント失敗時の exit_code=3。
FR-RE-010: 空選択時の正常終了（exit_code=0）。
FR-RE-014: load_errors のレポート記録。
"""

from __future__ import annotations

import asyncio

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hachimoku.agents.models import (
    AgentDefinition,
    ApplicabilityRule,
    LoadError,
    LoadResult,
    Phase,
)
from hachimoku.models.exit_code import ExitCode
from hachimoku.engine._aggregator import AggregatorError
from hachimoku.engine._engine import (
    SHUTDOWN_TIMEOUT_SECONDS,
    EngineResult,
    _execute_with_shutdown_timeout,
    _filter_disabled_agents,
    run_review,
)
from hachimoku.engine._resolver import ContentResolveError
from hachimoku.engine._selector import SelectorError, SelectorOutput
from hachimoku.models.config import AggregationConfig
from hachimoku.engine._target import DiffTarget
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.agent_result import (
    AgentError,
    AgentResult,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
)
from hachimoku.models.config import HachimokuConfig
from hachimoku.models.report import AggregatedReport, ReviewReport
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


def _make_timeout(
    agent_name: str = "test-agent",
    timeout_seconds: float = 300.0,
) -> AgentTimeout:
    """テスト用 AgentTimeout を生成するヘルパー。"""
    return AgentTimeout(
        agent_name=agent_name,
        timeout_seconds=timeout_seconds,
    )


def _make_truncated(agent_name: str = "test-agent") -> AgentTruncated:
    """テスト用 AgentTruncated を生成するヘルパー。"""
    return AgentTruncated(
        agent_name=agent_name,
        issues=[],
        elapsed_time=1.0,
        turns_consumed=5,
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
        result = EngineResult(report=report, exit_code=ExitCode.SUCCESS)
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
        result = EngineResult(report=report, exit_code=ExitCode.SUCCESS)
        with pytest.raises(Exception):
            result.exit_code = ExitCode.CRITICAL  # type: ignore[misc]

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
    デフォルト config.parallel=True のため execute_parallel をモック化する。
    """

    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_full_pipeline_success(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        """全ステップが正常に完了し、EngineResult が返される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
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
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_selector_failure_exit_code_3(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
    ) -> None:
        """セレクター失敗時に exit_code=3 が返される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.side_effect = SelectorError("Selector timeout")

        result = await run_review(target=_make_target())

        assert result.exit_code == 3
        assert len(result.report.results) == 0

    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_load_selector_failure_exit_code_3(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        mock_load_selector: MagicMock,
    ) -> None:
        """load_selector 失敗時に exit_code=3 とエラーメッセージが返される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_load_selector.side_effect = FileNotFoundError(
            "Builtin selector definition not found: selector.toml"
        )

        result = await run_review(target=_make_target())

        assert result.exit_code == 3

    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_empty_selection_exit_code_0(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
    ) -> None:
        """空選択で exit_code=0 が返される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=[],
            reasoning="No applicable agents",
        )

        result = await run_review(target=_make_target())

        assert result.exit_code == 0
        assert len(result.report.results) == 0

    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_load_errors_in_report(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
    ) -> None:
        """読み込みエラーがレポートに記録される。"""
        mock_config.return_value = HachimokuConfig()
        mock_resolve_content.return_value = "test diff"
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

    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_all_agents_failed_exit_code_3(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        """全エージェント失敗で exit_code=3 が返される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Selected",
        )
        mock_execute.return_value = [_make_error("agent-a")]

        result = await run_review(target=_make_target())

        assert result.exit_code == 3

    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_severity_determines_exit_code(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        """Critical issue があると exit_code=1 が返される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
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

    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_disabled_agents_excluded(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        """disabled エージェントがセレクターに渡されない。"""
        from hachimoku.models.config import AgentConfig

        config = HachimokuConfig(
            agents={"agent-b": AgentConfig(enabled=False)},
        )
        mock_config.return_value = config
        mock_resolve_content.return_value = "test diff"
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

    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_multiple_agents_all_fail_mixed_errors_exit_code_3(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        """複数エージェントが全て失敗（AgentError + AgentTimeout 混在）で exit_code=3。"""
        mock_config.return_value = HachimokuConfig()
        mock_resolve_content.return_value = "test diff"
        mock_load.return_value = LoadResult(
            agents=(
                _make_agent("agent-a"),
                _make_agent("agent-b"),
                _make_agent("agent-c"),
            ),
        )
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a", "agent-b", "agent-c"],
            reasoning="Selected all",
        )
        mock_execute.return_value = [
            _make_error("agent-a"),
            _make_timeout("agent-b"),
            _make_error("agent-c"),
        ]

        result = await run_review(target=_make_target())

        assert result.exit_code == 3
        assert len(result.report.results) == 3
        assert isinstance(result.report.results[0], AgentError)
        assert isinstance(result.report.results[1], AgentTimeout)
        assert isinstance(result.report.results[2], AgentError)

    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_partial_failure_with_truncated_not_exit_code_3(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        """AgentTruncated が含まれる部分失敗では exit_code != 3。

        AgentTruncated は有効な結果として扱われる（FR-RE-003）ため、
        AgentError や AgentTimeout と混在しても exit_code=3 にはならない。
        """
        mock_config.return_value = HachimokuConfig()
        mock_resolve_content.return_value = "test diff"
        mock_load.return_value = LoadResult(
            agents=(
                _make_agent("agent-a"),
                _make_agent("agent-b"),
                _make_agent("agent-c"),
            ),
        )
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a", "agent-b", "agent-c"],
            reasoning="Selected all",
        )
        mock_execute.return_value = [
            _make_error("agent-a"),
            _make_truncated("agent-b"),
            _make_timeout("agent-c"),
        ]

        result = await run_review(target=_make_target())

        assert result.exit_code != 3
        # truncated の issues が空 → max_severity=None → exit_code=0
        assert result.exit_code == 0

    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_content_resolve_error_exit_code_3(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        mock_resolve_content: AsyncMock,
    ) -> None:
        """ContentResolveError 発生時に exit_code=3 が返される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.side_effect = ContentResolveError("git merge-base failed")

        result = await run_review(target=_make_target())

        assert result.exit_code == 3
        assert len(result.report.results) == 0

    @patch("hachimoku.engine._engine.execute_parallel", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.install_signal_handlers")
    @patch("hachimoku.engine._engine.uninstall_signal_handlers")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.build_review_instruction")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_resolved_content_forwarded_to_instruction_and_selector(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        mock_build_instruction: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        _mock_uninstall: MagicMock,
        _mock_install: MagicMock,
        mock_execute: AsyncMock,
    ) -> None:
        """resolved_content が build_review_instruction と run_selector に渡される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "resolved diff content"
        mock_build_instruction.return_value = "user message"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Applicable",
        )
        mock_execute.return_value = [_make_success("agent-a")]

        await run_review(target=_make_target())

        # build_review_instruction に resolved_content が渡される
        mock_build_instruction.assert_called_once()
        instruction_args = mock_build_instruction.call_args
        assert instruction_args[0][1] == "resolved diff content"

        # run_selector に resolved_content が渡される
        mock_selector.assert_called_once()
        assert mock_selector.call_args[1]["resolved_content"] == "resolved diff content"


# =============================================================================
# run_review — セレクターメタデータ伝播（Issue #148）
# =============================================================================


class TestRunReviewSelectorMetadata:
    """run_review がセレクターメタデータを user_message に伝播するテスト。

    Issue #148: FR-RE-002 Step 6.5 セレクターメタデータ伝播。
    """

    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_metadata_enriches_user_message(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        """セレクターのメタデータが user_message に追記される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Selected",
            change_intent="Fix authentication bug",
            affected_files=["src/config.py"],
        )
        mock_execute.return_value = [_make_success("agent-a")]

        await run_review(target=_make_target())

        # build_execution_context に渡される user_message を検証
        mock_execute.assert_called_once()
        contexts = mock_execute.call_args[0][0]
        assert len(contexts) == 1
        user_msg = contexts[0].user_message
        assert "Selector Analysis Context" in user_msg
        assert "Fix authentication bug" in user_msg
        assert "src/config.py" in user_msg

    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_empty_metadata_does_not_modify_user_message(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
    ) -> None:
        """メタデータが空の場合、user_message は変更されない。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Selected",
            # メタデータフィールドは全てデフォルト（空）
        )
        mock_execute.return_value = [_make_success("agent-a")]

        await run_review(target=_make_target())

        contexts = mock_execute.call_args[0][0]
        user_msg = contexts[0].user_message
        assert "Selector Analysis Context" not in user_msg


# =============================================================================
# run_review — parallel 設定による実行モード切り替え
# =============================================================================


class TestRunReviewParallelSwitch:
    """T037: parallel 設定による execute_parallel / execute_sequential の切り替え。

    FR-RE-006: parallel=true で並列実行、parallel=false で逐次実行。
    """

    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.execute_sequential")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_parallel_true_calls_execute_parallel(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_seq: AsyncMock,
        mock_par: AsyncMock,
    ) -> None:
        """parallel=true で execute_parallel が呼ばれる。"""
        mock_config.return_value = HachimokuConfig(parallel=True)
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Selected",
        )
        mock_par.return_value = [_make_success("agent-a")]

        result = await run_review(target=_make_target())

        mock_par.assert_called_once()
        mock_seq.assert_not_called()
        assert result.exit_code == 0

    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.execute_sequential")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_parallel_false_calls_execute_sequential(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_seq: AsyncMock,
        mock_par: AsyncMock,
    ) -> None:
        """parallel=false で execute_sequential が呼ばれる。"""
        mock_config.return_value = HachimokuConfig(parallel=False)
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Selected",
        )
        mock_seq.return_value = [_make_success("agent-a")]

        result = await run_review(target=_make_target())

        mock_seq.assert_called_once()
        mock_par.assert_not_called()
        assert result.exit_code == 0

    def test_default_config_parallel_is_true(self) -> None:
        """HachimokuConfig のデフォルトで parallel=True。"""
        config = HachimokuConfig()
        assert config.parallel is True


# =============================================================================
# run_review — SignalHandler 統合テスト
# =============================================================================


class TestRunReviewSignalIntegration:
    """T042: SignalHandler の install/uninstall 統合テスト。

    FR-RE-005: グレースフルシャットダウン。
    run_review() が executor 前後で install/uninstall を呼ぶことを検証する。
    """

    @patch("hachimoku.engine._engine.uninstall_signal_handlers")
    @patch("hachimoku.engine._engine.install_signal_handlers")
    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_signal_handlers_installed_and_uninstalled(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
        mock_install: MagicMock,
        mock_uninstall: MagicMock,
    ) -> None:
        """シグナルハンドラが executor 前後で install/uninstall される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Selected",
        )
        mock_execute.return_value = [_make_success("agent-a")]

        # 呼び出し順序を記録するトラッカー
        call_order: list[str] = []
        mock_install.side_effect = lambda *a, **kw: call_order.append("install")

        async def track_execute(*a: object, **kw: object) -> list[object]:
            call_order.append("execute")
            return [_make_success("agent-a")]

        mock_execute.side_effect = track_execute
        mock_uninstall.side_effect = lambda *a, **kw: call_order.append("uninstall")

        await run_review(target=_make_target())

        # S1: install → execute → uninstall の順序を検証
        assert call_order == ["install", "execute", "uninstall"]
        mock_install.assert_called_once()
        mock_uninstall.assert_called_once()

    @patch("hachimoku.engine._engine.uninstall_signal_handlers")
    @patch("hachimoku.engine._engine.install_signal_handlers")
    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_same_shutdown_event_passed_to_install_and_executor(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
        mock_install: MagicMock,
        mock_uninstall: MagicMock,
    ) -> None:
        """install と executor に同一の shutdown_event が渡される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Selected",
        )
        mock_execute.return_value = [_make_success("agent-a")]

        await run_review(target=_make_target())

        # install_signal_handlers(shutdown_event, loop) の第1引数
        install_event = mock_install.call_args[0][0]
        assert isinstance(install_event, asyncio.Event)

        # executor(contexts, shutdown_event) の第2引数
        executor_event = mock_execute.call_args[0][1]
        assert isinstance(executor_event, asyncio.Event)

        # S2: 同一の shutdown_event オブジェクト
        assert install_event is executor_event

    @patch("hachimoku.engine._engine.uninstall_signal_handlers")
    @patch("hachimoku.engine._engine.install_signal_handlers")
    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_signal_handlers_uninstalled_on_executor_error(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
        mock_install: MagicMock,
        mock_uninstall: MagicMock,
    ) -> None:
        """executor がエラーでも finally で uninstall が呼ばれる。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"],
            reasoning="Selected",
        )
        mock_execute.side_effect = RuntimeError("executor crashed")

        with pytest.raises(RuntimeError, match="executor crashed"):
            await run_review(target=_make_target())

        mock_install.assert_called_once()
        mock_uninstall.assert_called_once()

    @patch("hachimoku.engine._engine.uninstall_signal_handlers")
    @patch("hachimoku.engine._engine.install_signal_handlers")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_signal_handlers_not_installed_when_no_agents_selected(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_install: MagicMock,
        mock_uninstall: MagicMock,
    ) -> None:
        """空選択時はシグナルハンドラが install されない。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=[],
            reasoning="No applicable agents",
        )

        result = await run_review(target=_make_target())

        assert result.exit_code == 0
        mock_install.assert_not_called()
        mock_uninstall.assert_not_called()


# =============================================================================
# _execute_with_shutdown_timeout — 3秒シャットダウンタイムアウト
# =============================================================================


class TestExecuteWithShutdownTimeout:
    """_execute_with_shutdown_timeout のテスト。

    SC-RE-005: SIGINT 受信後3秒以内に全プロセス終了。
    """

    async def test_normal_completion_no_shutdown(self) -> None:
        """シャットダウンなしで正常完了 → 全結果返却。"""

        async def mock_executor(
            contexts: list[object],
            shutdown_event: asyncio.Event,
            collected_results: list[AgentResult] | None = None,
        ) -> list[AgentResult]:
            results: list[AgentResult] = (
                collected_results if collected_results is not None else []
            )
            results.append(_make_success("agent-a"))
            return results

        event = asyncio.Event()
        results = await _execute_with_shutdown_timeout(mock_executor, [], event)  # type: ignore[arg-type]

        assert len(results) == 1
        assert results[0].agent_name == "agent-a"

    async def test_shutdown_executor_finishes_within_deadline(self) -> None:
        """シャットダウン後、executor が期限内に完了 → 正常結果。"""

        async def mock_executor(
            contexts: list[object],
            shutdown_event: asyncio.Event,
            collected_results: list[AgentResult] | None = None,
        ) -> list[AgentResult]:
            results: list[AgentResult] = (
                collected_results if collected_results is not None else []
            )
            results.append(_make_success("agent-a"))
            return results

        event = asyncio.Event()
        event.set()
        results = await _execute_with_shutdown_timeout(mock_executor, [], event)  # type: ignore[arg-type]

        assert len(results) == 1
        assert results[0].agent_name == "agent-a"

    @patch("hachimoku.engine._engine.SHUTDOWN_TIMEOUT_SECONDS", 0.1)
    async def test_shutdown_timeout_returns_partial_results(self) -> None:
        """3秒タイムアウト → 完了済み結果のみ返却。"""

        async def mock_executor(
            contexts: list[object],
            shutdown_event: asyncio.Event,
            collected_results: list[AgentResult] | None = None,
        ) -> list[AgentResult]:
            results: list[AgentResult] = (
                collected_results if collected_results is not None else []
            )
            results.append(_make_success("agent-a"))
            await asyncio.sleep(100)
            results.append(_make_success("agent-b"))
            return results

        event = asyncio.Event()
        event.set()
        results = await _execute_with_shutdown_timeout(mock_executor, [], event)  # type: ignore[arg-type]

        assert len(results) == 1
        assert results[0].agent_name == "agent-a"

    @patch("hachimoku.engine._engine.SHUTDOWN_TIMEOUT_SECONDS", 0.1)
    async def test_shutdown_timeout_cancels_executor(self) -> None:
        """タイムアウトで executor タスクがキャンセルされる。"""

        cancelled = False

        async def mock_executor(
            contexts: list[object],
            shutdown_event: asyncio.Event,
            collected_results: list[AgentResult] | None = None,
        ) -> list[AgentResult]:
            nonlocal cancelled
            results: list[AgentResult] = (
                collected_results if collected_results is not None else []
            )
            try:
                await asyncio.sleep(100)
            except asyncio.CancelledError:
                cancelled = True
                raise
            return results

        event = asyncio.Event()
        event.set()
        await _execute_with_shutdown_timeout(mock_executor, [], event)  # type: ignore[arg-type]

        assert cancelled

    async def test_shutdown_before_any_agent_starts(self) -> None:
        """executor が即座に空リストを返す → 空結果。"""

        async def mock_executor(
            contexts: list[object],
            shutdown_event: asyncio.Event,
            collected_results: list[AgentResult] | None = None,
        ) -> list[AgentResult]:
            results: list[AgentResult] = (
                collected_results if collected_results is not None else []
            )
            if shutdown_event.is_set():
                return results
            return results

        event = asyncio.Event()
        event.set()
        results = await _execute_with_shutdown_timeout(mock_executor, [], event)  # type: ignore[arg-type]

        assert results == []

    def test_shutdown_timeout_constant_value(self) -> None:
        """SHUTDOWN_TIMEOUT_SECONDS が 3.0 である。"""
        assert SHUTDOWN_TIMEOUT_SECONDS == 3.0

    async def test_executor_exception_propagates(self) -> None:
        """executor が例外を送出した場合、そのまま伝播する。"""

        async def mock_executor(
            contexts: list[object],
            shutdown_event: asyncio.Event,
            collected_results: list[AgentResult] | None = None,
        ) -> list[AgentResult]:
            raise RuntimeError("executor crashed")

        event = asyncio.Event()
        with pytest.raises(RuntimeError, match="executor crashed"):
            await _execute_with_shutdown_timeout(mock_executor, [], event)  # type: ignore[arg-type]

    @patch("hachimoku.engine._engine.SHUTDOWN_TIMEOUT_SECONDS", 0.1)
    async def test_shutdown_timeout_prints_stderr_warning(self) -> None:
        """タイムアウト時に stderr に警告が出力される。"""

        async def mock_executor(
            contexts: list[object],
            shutdown_event: asyncio.Event,
            collected_results: list[AgentResult] | None = None,
        ) -> list[AgentResult]:
            results: list[AgentResult] = (
                collected_results if collected_results is not None else []
            )
            results.append(_make_success("agent-a"))
            await asyncio.sleep(100)
            return results

        event = asyncio.Event()
        event.set()

        import io

        captured = io.StringIO()
        with patch("sys.stderr", captured):
            await _execute_with_shutdown_timeout(mock_executor, [], event)  # type: ignore[arg-type]

        assert "Shutdown timeout" in captured.getvalue()
        assert "1 partial result(s)" in captured.getvalue()


# =============================================================================
# run_review — Step 9.5: 集約エージェント統合 (Issue #152)
# =============================================================================


class TestRunReviewAggregation:
    """run_review の Step 9.5 集約エージェント統合テスト。

    Issue #152: LLM ベース結果集約。
    """

    @patch("hachimoku.engine._engine.run_aggregator")
    @patch("hachimoku.engine._engine.load_aggregator")
    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_aggregation_success_populates_aggregated(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
        mock_load_aggregator: MagicMock,
        mock_run_aggregator: AsyncMock,
    ) -> None:
        """集約成功時に report.aggregated が設定される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"], reasoning="Applicable"
        )
        mock_execute.return_value = [_make_success("agent-a")]

        agg_report = AggregatedReport(
            issues=[],
            strengths=["Good code"],
            recommended_actions=[],
            agent_failures=[],
        )
        mock_run_aggregator.return_value = agg_report

        result = await run_review(target=_make_target())

        assert result.report.aggregated is not None
        assert result.report.aggregated.strengths == ["Good code"]
        assert result.report.aggregation_error is None

    @patch("hachimoku.engine._engine.run_aggregator")
    @patch("hachimoku.engine._engine.load_aggregator")
    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_aggregation_disabled_skips(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
        mock_load_aggregator: MagicMock,
        mock_run_aggregator: AsyncMock,
    ) -> None:
        """aggregation.enabled=False の場合、集約がスキップされる。"""
        mock_config.return_value = HachimokuConfig(
            aggregation=AggregationConfig(enabled=False),
        )
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"], reasoning="Applicable"
        )
        mock_execute.return_value = [_make_success("agent-a")]

        result = await run_review(target=_make_target())

        assert result.report.aggregated is None
        assert result.report.aggregation_error is None
        mock_load_aggregator.assert_not_called()
        mock_run_aggregator.assert_not_called()

    @patch("hachimoku.engine._engine.run_aggregator")
    @patch("hachimoku.engine._engine.load_aggregator")
    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_aggregation_skipped_when_no_valid_results(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
        mock_load_aggregator: MagicMock,
        mock_run_aggregator: AsyncMock,
    ) -> None:
        """有効結果なし（全エージェント失敗）の場合、集約がスキップされる。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"], reasoning="Applicable"
        )
        mock_execute.return_value = [_make_error("agent-a")]

        result = await run_review(target=_make_target())

        assert result.report.aggregated is None
        mock_load_aggregator.assert_not_called()
        mock_run_aggregator.assert_not_called()

    @patch("hachimoku.engine._engine.run_aggregator")
    @patch("hachimoku.engine._engine.load_aggregator")
    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_aggregation_failure_sets_error(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
        mock_load_aggregator: MagicMock,
        mock_run_aggregator: AsyncMock,
    ) -> None:
        """集約エージェント失敗時に aggregation_error が設定される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"], reasoning="Applicable"
        )
        mock_execute.return_value = [_make_success("agent-a")]
        mock_run_aggregator.side_effect = AggregatorError("Aggregator timeout")

        result = await run_review(target=_make_target())

        assert result.report.aggregated is None
        assert result.report.aggregation_error is not None
        assert "Aggregator timeout" in result.report.aggregation_error
        # パイプライン自体は失敗しない（exit_code は集約前と同じ）
        assert result.exit_code == ExitCode.SUCCESS

    @patch("hachimoku.engine._engine.run_aggregator")
    @patch("hachimoku.engine._engine.load_aggregator")
    @patch("hachimoku.engine._engine.execute_parallel")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_load_aggregator_failure_sets_error(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute: AsyncMock,
        mock_load_aggregator: MagicMock,
        mock_run_aggregator: AsyncMock,
    ) -> None:
        """load_aggregator 失敗時に aggregation_error が設定される。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"], reasoning="Applicable"
        )
        mock_execute.return_value = [_make_success("agent-a")]
        mock_load_aggregator.side_effect = FileNotFoundError(
            "aggregator.toml not found"
        )

        result = await run_review(target=_make_target())

        assert result.report.aggregated is None
        assert result.report.aggregation_error is not None
        assert "aggregator.toml" in result.report.aggregation_error
        mock_run_aggregator.assert_not_called()

    @patch("hachimoku.engine._engine.run_aggregator")
    @patch("hachimoku.engine._engine.load_aggregator")
    @patch("hachimoku.engine._engine._execute_with_shutdown_timeout")
    @patch("hachimoku.engine._engine.run_selector")
    @patch("hachimoku.engine._engine.resolve_content", new_callable=AsyncMock)
    @patch("hachimoku.engine._engine.load_selector")
    @patch("hachimoku.engine._engine.load_agents")
    @patch("hachimoku.engine._engine.resolve_config")
    async def test_aggregation_skipped_on_shutdown_signal(
        self,
        mock_config: MagicMock,
        mock_load: MagicMock,
        _mock_load_selector: MagicMock,
        mock_resolve_content: AsyncMock,
        mock_selector: AsyncMock,
        mock_execute_with_timeout: AsyncMock,
        mock_load_aggregator: MagicMock,
        mock_run_aggregator: AsyncMock,
    ) -> None:
        """SIGINT/SIGTERM 受信後は集約がスキップされる。"""
        mock_config.return_value = HachimokuConfig()
        mock_load.return_value = LoadResult(agents=(_make_agent("agent-a"),))
        mock_resolve_content.return_value = "test diff"
        mock_selector.return_value = SelectorOutput(
            selected_agents=["agent-a"], reasoning="Applicable"
        )

        async def _set_shutdown_and_return(
            executor_fn: object,
            contexts: object,
            shutdown_event: asyncio.Event,
        ) -> list[AgentResult]:
            shutdown_event.set()
            return [_make_success("agent-a")]

        mock_execute_with_timeout.side_effect = _set_shutdown_and_return

        result = await run_review(target=_make_target())

        assert result.report.aggregated is None
        assert result.report.aggregation_error is None
        mock_load_aggregator.assert_not_called()
        mock_run_aggregator.assert_not_called()
