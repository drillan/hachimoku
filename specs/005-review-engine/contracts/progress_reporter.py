"""Contract: ProgressReporter — stderr 進捗表示.

FR-RE-015: レビュー実行中の進捗情報を stderr に出力する。
Art.3: 進捗表示・ログは stderr に出力。
"""

from __future__ import annotations

from hachimoku.models.agent_result import AgentResult


def report_agent_start(agent_name: str) -> None:
    """エージェント実行開始を stderr に表示する.

    出力フォーマット:
        "Running agent: {agent_name}..."

    Args:
        agent_name: 実行開始するエージェント名。
    """
    ...


def report_agent_complete(agent_name: str, result: AgentResult) -> None:
    """エージェント実行完了を stderr に表示する.

    出力フォーマット:
        成功: "Agent {agent_name}: completed ({N} issues found)"
        切り詰め: "Agent {agent_name}: truncated ({N} issues, {turns} turns)"
        エラー: "Agent {agent_name}: error ({error_message})"
        タイムアウト: "Agent {agent_name}: timeout ({timeout}s)"

    Args:
        agent_name: 完了したエージェント名。
        result: エージェント実行結果。
    """
    ...


def report_summary(
    total: int,
    success: int,
    truncated: int,
    errors: int,
    timeouts: int,
) -> None:
    """全体完了サマリーを stderr に表示する.

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
    ...


def report_load_warnings(
    # errors: Sequence[LoadError],
) -> None:
    """エージェント読み込みエラーを stderr に警告表示する.

    FR-RE-014: LoadResult のスキップ情報を stderr に表示。

    出力フォーマット:
        "Warning: Failed to load agent '{source}': {message}"

    Args:
        errors: 読み込みエラーのリスト。
    """
    ...


def report_selector_result(
    selected_count: int,
    reasoning: str,
) -> None:
    """セレクター結果を stderr に表示する.

    出力フォーマット:
        "Selector: {selected_count} agents selected"
        空の場合: "Selector: no applicable agents found"

    Args:
        selected_count: 選択されたエージェント数。
        reasoning: 選択理由（デバッグ時に有用）。
    """
    ...
