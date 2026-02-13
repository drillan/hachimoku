"""RichProgressReporter のテスト。

FR-CLI-015: TTY 環境向け Rich Live テーブル進捗表示。
"""

import io

import pytest
from rich.console import Console

from hachimoku.engine._live_progress import RichProgressReporter
from hachimoku.models.agent_result import (
    AgentError,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
)


def _make_reporter() -> tuple[RichProgressReporter, io.StringIO]:
    """テスト用 RichProgressReporter を生成する。

    Returns:
        (reporter, output_buffer) のタプル。
    """
    buf = io.StringIO()
    console = Console(file=buf, force_terminal=True, width=80)
    reporter = RichProgressReporter(console=console)
    return reporter, buf


# =============================================================================
# on_agent_pending
# =============================================================================


class TestOnAgentPending:
    """on_agent_pending のテスト。"""

    def test_registers_agent(self) -> None:
        """pending 状態のエージェントが内部に登録される。"""
        reporter, _ = _make_reporter()
        reporter.on_agent_pending("security-reviewer", "main")
        assert "security-reviewer" in reporter.agents

    def test_pending_status(self) -> None:
        """登録されたエージェントは pending ステータスを持つ。"""
        reporter, _ = _make_reporter()
        reporter.on_agent_pending("security-reviewer", "main")
        assert reporter.agents["security-reviewer"].status == "pending"

    def test_phase_recorded(self) -> None:
        """登録されたエージェントにフェーズが記録される。"""
        reporter, _ = _make_reporter()
        reporter.on_agent_pending("security-reviewer", "main")
        assert reporter.agents["security-reviewer"].phase == "main"


# =============================================================================
# on_agent_start
# =============================================================================


class TestOnAgentStart:
    """on_agent_start のテスト。"""

    def test_updates_status_to_running(self) -> None:
        """start でステータスが running に更新される。"""
        reporter, _ = _make_reporter()
        reporter.on_agent_pending("test-agent", "main")
        reporter.on_agent_start("test-agent")
        assert reporter.agents["test-agent"].status == "running"


# =============================================================================
# on_agent_complete
# =============================================================================


class TestOnAgentComplete:
    """on_agent_complete のテスト。"""

    def test_success_status(self) -> None:
        """成功完了時のステータス文字列を検証。"""
        reporter, _ = _make_reporter()
        reporter.on_agent_pending("test", "main")
        result = AgentSuccess(agent_name="test", issues=[], elapsed_time=1.0)
        reporter.on_agent_complete("test", result)
        assert "✓" in reporter.agents["test"].status
        assert "0 issues" in reporter.agents["test"].status

    def test_success_with_issues(self) -> None:
        """issue 検出ありの成功ステータス。"""
        from hachimoku.models.review import ReviewIssue
        from hachimoku.models.severity import Severity

        reporter, _ = _make_reporter()
        reporter.on_agent_pending("test", "main")
        issues = [
            ReviewIssue(
                agent_name="test", severity=Severity.IMPORTANT, description="Issue"
            ),
            ReviewIssue(
                agent_name="test", severity=Severity.SUGGESTION, description="Issue 2"
            ),
        ]
        result = AgentSuccess(agent_name="test", issues=issues, elapsed_time=2.0)
        reporter.on_agent_complete("test", result)
        assert "2 issues" in reporter.agents["test"].status

    def test_error_status(self) -> None:
        """エラー完了時のステータス文字列を検証。"""
        reporter, _ = _make_reporter()
        reporter.on_agent_pending("test", "main")
        result = AgentError(agent_name="test", error_message="Connection failed")
        reporter.on_agent_complete("test", result)
        assert "✗" in reporter.agents["test"].status

    def test_timeout_status(self) -> None:
        """タイムアウト完了時のステータス文字列を検証。"""
        reporter, _ = _make_reporter()
        reporter.on_agent_pending("test", "main")
        result = AgentTimeout(agent_name="test", timeout_seconds=30.0)
        reporter.on_agent_complete("test", result)
        assert "⏱" in reporter.agents["test"].status

    def test_truncated_status(self) -> None:
        """切り詰め完了時のステータス文字列を検証。"""
        reporter, _ = _make_reporter()
        reporter.on_agent_pending("test", "main")
        result = AgentTruncated(
            agent_name="test", issues=[], elapsed_time=5.0, turns_consumed=10
        )
        reporter.on_agent_complete("test", result)
        assert "⚠" in reporter.agents["test"].status

    def test_unknown_result_type_raises_type_error(self) -> None:
        """未知の result 型で TypeError を送出する。"""
        reporter, _ = _make_reporter()
        reporter.on_agent_pending("test", "main")
        with pytest.raises(TypeError, match="Unknown result type"):
            reporter.on_agent_complete("test", "not_a_result")  # type: ignore[arg-type]


# =============================================================================
# build_table
# =============================================================================


class TestBuildTable:
    """テーブル構築のテスト。"""

    def test_row_ordering_by_phase_then_name(self) -> None:
        """行が phase 順 → 名前順でソートされる。"""
        reporter, _ = _make_reporter()
        reporter.on_agent_pending("z-reviewer", "main")
        reporter.on_agent_pending("a-reviewer", "main")
        reporter.on_agent_pending("early-agent", "early")
        reporter.on_agent_pending("final-agent", "final")

        table = reporter.build_table()
        assert table.row_count == 4
        # Agent 列（index 0）の行順序を検証
        agent_names = [str(cell) for cell in table.columns[0]._cells]
        assert agent_names == [
            "early-agent",
            "a-reviewer",
            "z-reviewer",
            "final-agent",
        ]

    def test_table_has_correct_columns(self) -> None:
        """テーブルに Agent, Phase, Status 列が存在する。"""
        reporter, _ = _make_reporter()
        reporter.on_agent_pending("test", "main")

        table = reporter.build_table()
        column_names = [col.header for col in table.columns]
        assert "Agent" in column_names
        assert "Phase" in column_names
        assert "Status" in column_names


# =============================================================================
# start / stop ライフサイクル
# =============================================================================


class TestLifecycle:
    """start / stop ライフサイクルのテスト。"""

    def test_start_stop_no_exception(self) -> None:
        """start/stop が例外なく動作する。"""
        reporter, _ = _make_reporter()
        reporter.on_agent_pending("test", "main")
        reporter.start()
        reporter.stop()

    def test_stop_without_start_no_exception(self) -> None:
        """start なしで stop を呼んでも例外が発生しない。"""
        reporter, _ = _make_reporter()
        reporter.stop()

    def test_output_goes_to_console(self) -> None:
        """テーブル出力が Console の file に書き込まれる。"""
        reporter, buf = _make_reporter()
        reporter.on_agent_pending("test-agent", "main")
        reporter.start()
        reporter.stop()
        output = buf.getvalue()
        assert "test-agent" in output
