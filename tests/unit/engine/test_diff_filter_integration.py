"""_engine.py の差分フィルタリング統合ヘルパーのテスト。

Issue #171: _should_filter_diff / _build_agent_user_message の
分岐パスを網羅的にテストする。
"""

from __future__ import annotations

from unittest.mock import patch

from hachimoku.agents.models import AgentDefinition, ApplicabilityRule
from hachimoku.engine._engine import _build_agent_user_message, _should_filter_diff
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget


def _make_agent(
    *,
    always: bool = False,
    file_patterns: tuple[str, ...] = (),
) -> AgentDefinition:
    """テスト用 AgentDefinition を生成するヘルパー。"""
    return AgentDefinition(  # type: ignore[call-arg]
        name="test-agent",
        description="Test agent",
        model="test",
        output_schema="scored_issues",
        system_prompt="You are a test agent.",
        applicability=ApplicabilityRule(
            always=always,
            file_patterns=file_patterns,
        ),
    )


_DIFF_TARGET = DiffTarget(base_branch="main")
_PR_TARGET = PRTarget(pr_number=1)
_FILE_TARGET = FileTarget(paths=("src/main.py",))


# =============================================================================
# _should_filter_diff — 4 分岐
# =============================================================================


class TestShouldFilterDiff:
    """_should_filter_diff の全分岐パステスト。"""

    def test_always_true_returns_false(self) -> None:
        """always=True → フィルタリング不要。"""
        agent = _make_agent(always=True, file_patterns=("*.py",))
        assert _should_filter_diff(agent, _DIFF_TARGET) is False

    def test_empty_file_patterns_returns_false(self) -> None:
        """file_patterns 空 → フィルタリング不要。"""
        agent = _make_agent(file_patterns=())
        assert _should_filter_diff(agent, _DIFF_TARGET) is False

    def test_file_target_returns_false(self) -> None:
        """FileTarget → フィルタリング不要。"""
        agent = _make_agent(file_patterns=("*.py",))
        assert _should_filter_diff(agent, _FILE_TARGET) is False

    def test_diff_target_with_patterns_returns_true(self) -> None:
        """DiffTarget + file_patterns 非空 + always=False → フィルタリング適用。"""
        agent = _make_agent(file_patterns=("*.py",))
        assert _should_filter_diff(agent, _DIFF_TARGET) is True

    def test_pr_target_with_patterns_returns_true(self) -> None:
        """PRTarget + file_patterns 非空 + always=False → フィルタリング適用。"""
        agent = _make_agent(file_patterns=("*.py",))
        assert _should_filter_diff(agent, _PR_TARGET) is True


# =============================================================================
# _build_agent_user_message — 4 動作パス
# =============================================================================


_PY_DIFF = (
    "diff --git a/src/auth.py b/src/auth.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/src/auth.py\n"
    "+++ b/src/auth.py\n"
    "@@ -1,3 +1,4 @@\n"
    " import os\n"
    "+import sys\n"
    " def func():\n"
    "     pass\n"
)


class TestBuildAgentUserMessage:
    """_build_agent_user_message の動作パステスト。"""

    def test_no_filter_without_selector_context(self) -> None:
        """フィルタリング不要 + selector_context 空 → base_user_message をそのまま返す。"""
        agent = _make_agent(always=True)
        result = _build_agent_user_message(
            agent_def=agent,
            target=_DIFF_TARGET,
            base_user_message="base message",
            resolved_content=_PY_DIFF,
            selector_context="",
        )
        assert result == "base message"

    def test_no_filter_with_selector_context(self) -> None:
        """フィルタリング不要 + selector_context あり → 連結して返す。"""
        agent = _make_agent(always=True)
        result = _build_agent_user_message(
            agent_def=agent,
            target=_DIFF_TARGET,
            base_user_message="base message",
            resolved_content=_PY_DIFF,
            selector_context="selector info",
        )
        assert result == "base message\n\nselector info"

    def test_filter_applied_builds_new_message(self) -> None:
        """フィルタリング適用 → build_review_instruction で新メッセージを構築。"""
        agent = _make_agent(file_patterns=("*.py",))
        with patch(
            "hachimoku.engine._engine.build_review_instruction",
            return_value="filtered instruction",
        ) as mock_build:
            result = _build_agent_user_message(
                agent_def=agent,
                target=_DIFF_TARGET,
                base_user_message="base message",
                resolved_content=_PY_DIFF,
                selector_context="",
            )
        assert result == "filtered instruction"
        mock_build.assert_called_once()
        # フィルタ後のコンテンツが渡される
        call_args = mock_build.call_args
        assert call_args[0][0] == _DIFF_TARGET

    def test_filter_applied_with_selector_context(self) -> None:
        """フィルタリング適用 + selector_context あり → 新メッセージに連結。"""
        agent = _make_agent(file_patterns=("*.py",))
        with patch(
            "hachimoku.engine._engine.build_review_instruction",
            return_value="filtered instruction",
        ):
            result = _build_agent_user_message(
                agent_def=agent,
                target=_DIFF_TARGET,
                base_user_message="base message",
                resolved_content=_PY_DIFF,
                selector_context="selector info",
            )
        assert result == "filtered instruction\n\nselector info"
