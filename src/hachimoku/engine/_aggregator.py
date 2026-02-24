"""AggregatorAgent — 結果集約処理。

FR-RE-002 Step 9.5: 集約エージェントの構築・実行。
Issue #152: LLM ベース結果集約。
"""

from __future__ import annotations

import logging

from anyio import fail_after
from claudecode_model import ClaudeCodeModelSettings
from pydantic_ai import Agent
from pydantic_ai.usage import UsageLimits

from hachimoku.agents.models import AggregatorDefinition
from hachimoku.engine._context import _resolve_with_agent_def
from hachimoku.engine._model_resolver import resolve_model
from hachimoku.models.agent_result import (
    AgentError,
    AgentResult,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
)
from hachimoku.models.config import AggregationConfig
from hachimoku.models.report import AggregatedReport

logger = logging.getLogger(__name__)


class AggregatorError(Exception):
    """集約エージェントの実行失敗。

    タイムアウト・実行エラー・不正な出力など、集約エージェント実行中の
    あらゆる失敗を表す。
    """


def _build_aggregator_message(
    results: list[AgentResult],
) -> str:
    """エージェント結果から集約エージェント向けユーザーメッセージを構築する。

    AgentSuccess / AgentTruncated の issues を抽出し、
    AgentError / AgentTimeout の情報を失敗エージェントとして含める。

    Args:
        results: エージェント結果のリスト。

    Returns:
        集約エージェントへのユーザーメッセージ文字列。
    """
    sections: list[str] = []

    # 有効結果（Success + Truncated）から issues を収集
    sections.append("# Agent Review Results\n")
    for r in results:
        if isinstance(r, (AgentSuccess, AgentTruncated)):
            sections.append(f"## Agent: {r.agent_name}")
            if r.issues:
                for issue in r.issues:
                    location_str = ""
                    if issue.location is not None:
                        location_str = (
                            f" ({issue.location.file_path}"
                            f":{issue.location.line_number})"
                        )
                    line = (
                        f"- [{issue.severity.value}]{location_str} {issue.description}"
                    )
                    if issue.suggestion:
                        line += f"\n  Suggestion: {issue.suggestion}"
                    if issue.category:
                        line += f"\n  Category: {issue.category}"
                    sections.append(line)
            else:
                sections.append("- No issues found.")
            sections.append("")

    # 失敗エージェント情報
    failed: list[str] = []
    for r in results:
        if isinstance(r, AgentError):
            failed.append(f"- {r.agent_name}: error — {r.error_message}")
        elif isinstance(r, AgentTimeout):
            failed.append(f"- {r.agent_name}: timeout ({r.timeout_seconds}s)")

    if failed:
        sections.append("# Failed Agents\n")
        sections.extend(failed)
        sections.append("")

    return "\n".join(sections)


async def run_aggregator(
    results: list[AgentResult],
    aggregator_definition: AggregatorDefinition,
    aggregation_config: AggregationConfig,
    global_model: str,
    global_timeout: int,
    global_max_turns: int,
) -> AggregatedReport:
    """集約エージェントを実行し、結果を統合する。

    実行フロー:
        1. モデル解決（3層: config > definition > global）
        2. AggregationConfig からタイムアウト・ターン数を解決
        3. エージェント結果からユーザーメッセージを構築
        4. resolve_model() でモデルオブジェクトを生成
        5. pydantic-ai Agent(output_type=AggregatedReport, tools=[]) を構築
        6. anyio.fail_after() + UsageLimits でエージェントを実行
        7. AggregatedReport を返す

    Args:
        results: 全エージェントの実行結果。
        aggregator_definition: 集約エージェント定義（system_prompt, model）。
        aggregation_config: 集約個別設定（model, timeout, max_turns オーバーライド）。
        global_model: グローバルモデル名。
        global_timeout: グローバルタイムアウト秒数。
        global_max_turns: グローバル最大ターン数。

    Returns:
        AggregatedReport: 統合された集約レポート。

    Raises:
        AggregatorError: 集約エージェントの実行に失敗した場合。
    """
    # 3層モデル解決: config > definition > global
    model = _resolve_with_agent_def(
        aggregation_config.model, aggregator_definition.model, global_model
    )
    timeout = _resolve_with_agent_def(aggregation_config.timeout, None, global_timeout)
    max_turns = _resolve_with_agent_def(
        aggregation_config.max_turns, None, global_max_turns
    )

    try:
        user_message = _build_aggregator_message(results)
        resolved = resolve_model(model)
        agent = Agent(
            model=resolved,
            output_type=AggregatedReport,
            tools=[],
            system_prompt=aggregator_definition.system_prompt,
        )

        with fail_after(timeout):
            result = await agent.run(
                user_message,
                usage_limits=UsageLimits(request_limit=max_turns),
                model_settings=ClaudeCodeModelSettings(
                    max_turns=max_turns,
                    timeout=timeout,
                ),
            )

        return result.output

    except Exception as exc:
        logger.warning(
            "Aggregator agent failed with %s: %s",
            type(exc).__name__,
            exc,
            exc_info=True,
        )
        raise AggregatorError(
            f"Aggregator agent failed: {exc}",
        ) from exc
