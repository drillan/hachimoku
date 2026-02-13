"""ProgressReporter — stderr 進捗表示。

FR-RE-015: レビュー実行中の進捗情報を stderr に出力する。
FR-CLI-015: TTY 時は Rich Live テーブル、非 TTY 時はプレーンテキストで自動切替。
Art.3: 進捗表示・ログは stderr に出力。
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from hachimoku.agents.models import LoadError
from hachimoku.models.agent_result import (
    AgentError,
    AgentResult,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
)


# =============================================================================
# ProgressReporter Protocol
# =============================================================================


@runtime_checkable
class ProgressReporter(Protocol):
    """エージェント実行進捗を報告するプロトコル。

    FR-CLI-015: TTY/非 TTY で異なる実装を切り替える。
    """

    def on_agent_pending(self, agent_name: str, phase: str) -> None:
        """エージェントを pending 状態として登録する。"""
        ...

    def on_agent_start(self, agent_name: str) -> None:
        """エージェント実行開始を通知する。"""
        ...

    def on_agent_complete(self, agent_name: str, result: AgentResult) -> None:
        """エージェント実行完了を通知する。"""
        ...

    def start(self) -> None:
        """進捗表示を開始する。"""
        ...

    def stop(self) -> None:
        """進捗表示を停止する。"""
        ...


# =============================================================================
# PlainProgressReporter
# =============================================================================


class PlainProgressReporter:
    """非 TTY 環境向けプレーンテキスト進捗レポーター。

    既存の report_agent_start / report_agent_complete 関数に委譲する。
    """

    def on_agent_pending(self, agent_name: str, phase: str) -> None:
        """プレーンテキストでは pending 表示しない。"""

    def on_agent_start(self, agent_name: str) -> None:
        """report_agent_start に委譲する。"""
        report_agent_start(agent_name)

    def on_agent_complete(self, agent_name: str, result: AgentResult) -> None:
        """report_agent_complete に委譲する。"""
        report_agent_complete(agent_name, result)

    def start(self) -> None:
        """プレーンテキストでは開始処理なし。"""

    def stop(self) -> None:
        """プレーンテキストでは停止処理なし。"""


# =============================================================================
# ファクトリ関数
# =============================================================================


def create_progress_reporter() -> ProgressReporter:
    """stderr の TTY 状態に基づいて適切な ProgressReporter を生成する。

    FR-CLI-015: TTY の場合は RichProgressReporter、非 TTY の場合は
    PlainProgressReporter を返す。
    """
    if sys.stderr.isatty():
        from hachimoku.engine._live_progress import RichProgressReporter

        return RichProgressReporter()
    return PlainProgressReporter()


def report_agent_start(agent_name: str) -> None:
    """エージェント実行開始を stderr に表示する。

    出力フォーマット:
        "Running agent: {agent_name}..."

    Args:
        agent_name: 実行開始するエージェント名。
    """
    print(f"Running agent: {agent_name}...", file=sys.stderr)


def report_agent_complete(agent_name: str, result: AgentResult) -> None:
    """エージェント実行完了を stderr に表示する。

    出力フォーマット:
        成功: "Agent {agent_name}: completed ({N} issues found)"
        切り詰め: "Agent {agent_name}: truncated ({N} issues, {turns} turns)"
        エラー: "Agent {agent_name}: error ({error_message})"
        タイムアウト: "Agent {agent_name}: timeout ({timeout}s)"

    Args:
        agent_name: 完了したエージェント名。
        result: エージェント実行結果。
    """
    if isinstance(result, AgentSuccess):
        msg = f"Agent {agent_name}: completed ({len(result.issues)} issues found)"
    elif isinstance(result, AgentTruncated):
        msg = (
            f"Agent {agent_name}: truncated "
            f"({len(result.issues)} issues, {result.turns_consumed} turns)"
        )
    elif isinstance(result, AgentError):
        msg = f"Agent {agent_name}: error ({result.error_message})"
    elif isinstance(result, AgentTimeout):
        msg = f"Agent {agent_name}: timeout ({result.timeout_seconds}s)"
    else:
        raise TypeError(f"Unknown result type: {type(result)}")

    print(msg, file=sys.stderr)


def report_summary(
    total: int,
    success: int,
    truncated: int,
    errors: int,
    timeouts: int,
) -> None:
    """全体完了サマリーを stderr に表示する。

    出力フォーマット:
        "Review complete: {total} agents ({success} succeeded, {truncated} truncated,
         {errors} errors, {timeouts} timeouts)"

    Args:
        total: 実行されたエージェント総数。
        success: 成功数。
        truncated: 切り詰め数。
        errors: エラー数。
        timeouts: タイムアウト数。
    """
    msg = (
        f"Review complete: {total} agents "
        f"({success} succeeded, {truncated} truncated, "
        f"{errors} errors, {timeouts} timeouts)"
    )
    print(msg, file=sys.stderr)


def report_load_warnings(errors: Sequence[LoadError]) -> None:
    """エージェント読み込みエラーを stderr に警告表示する。

    FR-RE-014: LoadResult のスキップ情報を stderr に表示。

    出力フォーマット:
        "Warning: Failed to load agent '{source}': {message}"

    Args:
        errors: 読み込みエラーのシーケンス。
    """
    for error in errors:
        print(
            f"Warning: Failed to load agent '{error.source}': {error.message}",
            file=sys.stderr,
        )


def report_selector_result(selected_count: int, reasoning: str) -> None:
    """セレクター結果を stderr に表示する。

    出力フォーマット:
        "Selector: {selected_count} agents selected — {reasoning}"
        reasoning が空の場合: "Selector: {selected_count} agents selected"
        選択数が 0 の場合: "Selector: no applicable agents found — {reasoning}"

    Args:
        selected_count: 選択されたエージェント数。
        reasoning: 選択理由。空でない場合はメッセージ末尾に付加される。
    """
    if selected_count == 0:
        msg = "Selector: no applicable agents found"
    else:
        msg = f"Selector: {selected_count} agents selected"

    if reasoning:
        msg += f" — {reasoning}"

    print(msg, file=sys.stderr)
