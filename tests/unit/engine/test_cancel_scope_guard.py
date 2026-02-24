"""CancelScope ガードのテスト。

Issue #274: pydantic-ai 内部の CancelScope と claude-agent-sdk の
CancelScope が衝突する問題への対策。

Layer 1: _run_tracked_task から CancelScope を除去するパッチ。
Layer 2: agent.iter() で結果を先に保存し、残存する CancelScope 衝突を処理。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
from unittest.mock import MagicMock

import pytest
from claudecode_model.exceptions import CLIExecutionError
from pydantic_ai.run import AgentRunResult

from hachimoku.engine._cancel_scope_guard import run_agent_safe


def _make_mock_agent_run(
    result: object | None = None,
    *,
    raise_on_exit: Exception | None = None,
    raise_during_iter: Exception | None = None,
) -> MagicMock:
    """テスト用 mock Agent を生成する。

    agent.iter() の async context manager と async iterator を模擬する。

    Args:
        result: agent_run.result に返す値。
        raise_on_exit: __aexit__ 時に発生させる例外。
        raise_during_iter: iteration 中に発生させる例外。
    """
    mock_agent = MagicMock()

    @asynccontextmanager
    async def mock_iter(**kwargs: object) -> AsyncIterator[MagicMock]:
        agent_run = MagicMock()
        agent_run.result = result

        async def mock_aiter(self: object) -> AsyncIterator[MagicMock]:
            if raise_during_iter is not None:
                raise raise_during_iter
            return
            yield  # make it an async generator

        agent_run.__aiter__ = mock_aiter

        try:
            yield agent_run
        finally:
            if raise_on_exit is not None:
                raise raise_on_exit

    mock_agent.iter = mock_iter
    return mock_agent


# =============================================================================
# 正常系: CancelScope 衝突なし
# =============================================================================


class TestRunAgentSafeSuccess:
    """cancel scope 衝突がない場合、結果がそのまま返される。"""

    async def test_returns_result_on_success(self) -> None:
        """正常完了時に RunResult が返される。"""
        mock_result = MagicMock(spec=AgentRunResult)
        agent = _make_mock_agent_run(result=mock_result)

        result = await run_agent_safe(agent, user_prompt="test")
        assert result is mock_result

    async def test_passes_kwargs_to_iter(self) -> None:
        """キーワード引数が agent.iter() に渡される。"""
        mock_result = MagicMock(spec=AgentRunResult)
        agent = MagicMock()
        captured_kwargs: dict[str, object] = {}

        @asynccontextmanager
        async def capturing_iter(**kwargs: object) -> AsyncIterator[MagicMock]:
            captured_kwargs.update(kwargs)
            agent_run = MagicMock()
            agent_run.result = mock_result

            async def mock_aiter(self: object) -> AsyncIterator[MagicMock]:
                return
                yield

            agent_run.__aiter__ = mock_aiter
            yield agent_run

        agent.iter = capturing_iter
        await run_agent_safe(agent, user_prompt="hello", timeout=60)
        assert captured_kwargs["user_prompt"] == "hello"
        assert captured_kwargs["timeout"] == 60


# =============================================================================
# CancelScope 衝突: 結果保存済みの場合は復旧
# =============================================================================


class TestRunAgentSafeCancelScopeRecovery:
    """__aexit__ で CancelScope RuntimeError が発生しても結果が返される。"""

    async def test_recovers_result_on_cancel_scope_error(self) -> None:
        """CancelScope 衝突時、保存済みの結果が返される。"""
        mock_result = MagicMock(spec=AgentRunResult)
        cancel_scope_error = RuntimeError(
            "Attempted to exit a cancel scope that isn't the current "
            "tasks's current cancel scope"
        )
        agent = _make_mock_agent_run(
            result=mock_result, raise_on_exit=cancel_scope_error
        )

        result = await run_agent_safe(agent, user_prompt="test")
        assert result is mock_result

    async def test_recovers_on_different_task_error(self) -> None:
        """'different task' メッセージの CancelScope 衝突でも結果が返される。"""
        mock_result = MagicMock(spec=AgentRunResult)
        cancel_scope_error = RuntimeError(
            "Attempted to exit cancel scope in a different task than it was entered in"
        )
        agent = _make_mock_agent_run(
            result=mock_result, raise_on_exit=cancel_scope_error
        )

        result = await run_agent_safe(agent, user_prompt="test")
        assert result is mock_result


# =============================================================================
# CancelScope 衝突: 結果なし → CLIExecutionError(error_type="timeout")
# =============================================================================


class TestRunAgentSafeCancelScopeNoResult:
    """結果が保存される前に CancelScope 衝突が発生した場合。

    CancelScope 衝突 + 結果なしは、ClaudeCodeModel の move_on_after() が
    timeout を発火させた結果。元の CLIExecutionError(error_type="timeout") が
    RuntimeError に上書きされているため、timeout エラーを復元して送出する。
    """

    async def test_raises_cli_timeout_when_no_result_on_exit(self) -> None:
        """__aexit__ で CancelScope 衝突 + 結果なし → CLIExecutionError(timeout)。"""
        cancel_scope_error = RuntimeError(
            "Attempted to exit a cancel scope that isn't the current "
            "tasks's current cancel scope"
        )
        agent = _make_mock_agent_run(result=None, raise_on_exit=cancel_scope_error)

        with pytest.raises(CLIExecutionError) as exc_info:
            await run_agent_safe(agent, user_prompt="test")
        assert exc_info.value.error_type == "timeout"
        assert exc_info.value.__cause__ is cancel_scope_error

    async def test_raises_cli_timeout_when_cancel_scope_during_iter(self) -> None:
        """イテレーション中の CancelScope 衝突 → CLIExecutionError(timeout)。

        実際のエラーパス: _run_tracked_task の CancelScope.__exit__ が
        イテレーション中に RuntimeError を発生させるケース。
        """
        cancel_scope_error = RuntimeError(
            "Attempted to exit cancel scope in a different task than it was entered in"
        )
        agent = _make_mock_agent_run(raise_during_iter=cancel_scope_error)

        with pytest.raises(CLIExecutionError) as exc_info:
            await run_agent_safe(agent, user_prompt="test")
        assert exc_info.value.error_type == "timeout"


# =============================================================================
# 非 CancelScope RuntimeError → 再送出
# =============================================================================


class TestRunAgentSafeNonCancelScopeError:
    """CancelScope 以外の RuntimeError は常に再送出される。"""

    async def test_reraises_non_cancel_scope_runtime_error(self) -> None:
        """CancelScope 以外の RuntimeError は再送出される。"""
        mock_result = MagicMock(spec=AgentRunResult)
        other_error = RuntimeError("something completely different")
        agent = _make_mock_agent_run(result=mock_result, raise_on_exit=other_error)

        with pytest.raises(RuntimeError, match="something completely different"):
            await run_agent_safe(agent, user_prompt="test")


# =============================================================================
# 非 RuntimeError 例外 → 再送出
# =============================================================================


class TestRunAgentSafeOtherExceptions:
    """RuntimeError 以外の例外は常に再送出される。"""

    async def test_reraises_value_error(self) -> None:
        """ValueError は再送出される。"""
        agent = _make_mock_agent_run(raise_during_iter=ValueError("bad input"))

        with pytest.raises(ValueError, match="bad input"):
            await run_agent_safe(agent, user_prompt="test")

    async def test_reraises_timeout_error(self) -> None:
        """TimeoutError は再送出される。"""
        agent = _make_mock_agent_run(raise_during_iter=TimeoutError("timed out"))

        with pytest.raises(TimeoutError, match="timed out"):
            await run_agent_safe(agent, user_prompt="test")


# =============================================================================
# Layer 1: _run_tracked_task パッチ
# =============================================================================


class TestGraphCancelScopePatch:
    """_run_tracked_task から CancelScope が除去されていることを検証する。"""

    def test_patch_removes_cancel_scope(self) -> None:
        """パッチ適用後、_run_tracked_task に CancelScope がない。"""
        import inspect

        from pydantic_graph.beta.graph import _GraphIterator

        src = inspect.getsource(_GraphIterator._run_tracked_task)
        assert "CancelScope" not in src

    def test_patch_preserves_stream_send(self) -> None:
        """パッチ後も iter_stream_sender.send が呼ばれる。"""
        import inspect

        from pydantic_graph.beta.graph import _GraphIterator

        src = inspect.getsource(_GraphIterator._run_tracked_task)
        assert "iter_stream_sender.send" in src
