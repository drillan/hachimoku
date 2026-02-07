"""ProgressReporter のテスト。

FR-RE-015: stderr 進捗表示。
"""

import pytest

from hachimoku.agents.models import LoadError
from hachimoku.engine._progress import (
    report_agent_complete,
    report_agent_start,
    report_load_warnings,
    report_selector_result,
    report_summary,
)
from hachimoku.models.agent_result import (
    AgentError,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
)


# =============================================================================
# report_agent_start
# =============================================================================


class TestReportAgentStart:
    """report_agent_start の stderr 出力を検証。"""

    def test_outputs_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        """stderr に出力される。"""
        report_agent_start("test-agent")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Running agent: test-agent..." in captured.err

    def test_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        """正確なフォーマットで出力される。"""
        report_agent_start("code-reviewer")
        captured = capsys.readouterr()
        assert captured.err.strip() == "Running agent: code-reviewer..."


# =============================================================================
# report_agent_complete
# =============================================================================


class TestReportAgentCompleteSuccess:
    """report_agent_complete の AgentSuccess 出力を検証。"""

    def test_success_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        """成功時の出力フォーマットを検証。"""
        result = AgentSuccess(agent_name="test", issues=[], elapsed_time=1.0)
        report_agent_complete("test", result)
        captured = capsys.readouterr()
        assert "Agent test: completed (0 issues found)" in captured.err

    def test_success_with_issues(self, capsys: pytest.CaptureFixture[str]) -> None:
        """問題検出ありの成功出力を検証。"""
        from hachimoku.models.review import ReviewIssue
        from hachimoku.models.severity import Severity

        issues = [
            ReviewIssue(
                agent_name="test",
                severity=Severity.IMPORTANT,
                description="Issue 1",
            ),
            ReviewIssue(
                agent_name="test",
                severity=Severity.SUGGESTION,
                description="Issue 2",
            ),
        ]
        result = AgentSuccess(agent_name="test", issues=issues, elapsed_time=2.0)
        report_agent_complete("test", result)
        captured = capsys.readouterr()
        assert "Agent test: completed (2 issues found)" in captured.err


class TestReportAgentCompleteTruncated:
    """report_agent_complete の AgentTruncated 出力を検証。"""

    def test_truncated_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        """切り詰め時の出力フォーマットを検証。"""
        result = AgentTruncated(
            agent_name="test", issues=[], elapsed_time=5.0, turns_consumed=10
        )
        report_agent_complete("test", result)
        captured = capsys.readouterr()
        assert "Agent test: truncated (0 issues, 10 turns)" in captured.err


class TestReportAgentCompleteError:
    """report_agent_complete の AgentError 出力を検証。"""

    def test_error_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        """エラー時の出力フォーマットを検証。"""
        result = AgentError(agent_name="test", error_message="Connection failed")
        report_agent_complete("test", result)
        captured = capsys.readouterr()
        assert "Agent test: error (Connection failed)" in captured.err


class TestReportAgentCompleteTimeout:
    """report_agent_complete の AgentTimeout 出力を検証。"""

    def test_timeout_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        """タイムアウト時の出力フォーマットを検証。"""
        result = AgentTimeout(agent_name="test", timeout_seconds=30.0)
        report_agent_complete("test", result)
        captured = capsys.readouterr()
        assert "Agent test: timeout (30.0s)" in captured.err


class TestReportAgentCompleteStderr:
    """report_agent_complete が stdout に出力しないことを検証。"""

    def test_no_stdout_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """全バリアントで stdout が空である。"""
        results: list[AgentSuccess | AgentTruncated | AgentError | AgentTimeout] = [
            AgentSuccess(agent_name="a", issues=[], elapsed_time=1.0),
            AgentError(agent_name="b", error_message="err"),
            AgentTimeout(agent_name="c", timeout_seconds=10.0),
            AgentTruncated(
                agent_name="d", issues=[], elapsed_time=2.0, turns_consumed=5
            ),
        ]
        for result in results:
            report_agent_complete(result.agent_name, result)

        captured = capsys.readouterr()
        assert captured.out == ""


# =============================================================================
# report_summary
# =============================================================================


class TestReportSummary:
    """report_summary の出力フォーマットを検証。"""

    def test_summary_format(self, capsys: pytest.CaptureFixture[str]) -> None:
        """全体サマリーのフォーマットを検証。"""
        report_summary(total=5, success=3, truncated=1, errors=1, timeouts=0)
        captured = capsys.readouterr()
        assert "Review complete: 5 agents" in captured.err
        assert "3 succeeded" in captured.err
        assert "1 truncated" in captured.err
        assert "1 errors" in captured.err
        assert "0 timeouts" in captured.err

    def test_no_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        """stdout が空である。"""
        report_summary(total=1, success=1, truncated=0, errors=0, timeouts=0)
        captured = capsys.readouterr()
        assert captured.out == ""


# =============================================================================
# report_load_warnings
# =============================================================================


class TestReportLoadWarnings:
    """report_load_warnings の出力フォーマットを検証。"""

    def test_single_warning(self, capsys: pytest.CaptureFixture[str]) -> None:
        """単一の読み込みエラー警告を出力する。"""
        errors = [LoadError(source="broken.toml", message="parse error")]
        report_load_warnings(errors)
        captured = capsys.readouterr()
        assert (
            "Warning: Failed to load agent 'broken.toml': parse error" in captured.err
        )

    def test_multiple_warnings(self, capsys: pytest.CaptureFixture[str]) -> None:
        """複数の読み込みエラー警告を出力する。"""
        errors = [
            LoadError(source="a.toml", message="error a"),
            LoadError(source="b.toml", message="error b"),
        ]
        report_load_warnings(errors)
        captured = capsys.readouterr()
        assert "Warning: Failed to load agent 'a.toml': error a" in captured.err
        assert "Warning: Failed to load agent 'b.toml': error b" in captured.err

    def test_empty_errors_no_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        """エラーなし時は何も出力しない。"""
        report_load_warnings([])
        captured = capsys.readouterr()
        assert captured.err == ""
        assert captured.out == ""


# =============================================================================
# report_selector_result
# =============================================================================


class TestReportSelectorResult:
    """report_selector_result の出力フォーマットを検証。"""

    def test_agents_selected(self, capsys: pytest.CaptureFixture[str]) -> None:
        """エージェント選択ありの出力を検証。"""
        report_selector_result(selected_count=3, reasoning="test reasoning")
        captured = capsys.readouterr()
        assert "Selector: 3 agents selected" in captured.err

    def test_no_agents_selected(self, capsys: pytest.CaptureFixture[str]) -> None:
        """エージェント選択なし時のメッセージを検証。"""
        report_selector_result(selected_count=0, reasoning="none applicable")
        captured = capsys.readouterr()
        assert "Selector: no applicable agents found" in captured.err

    def test_no_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        """stdout が空である。"""
        report_selector_result(selected_count=1, reasoning="test")
        captured = capsys.readouterr()
        assert captured.out == ""
