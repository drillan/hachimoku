"""Contract: AgentRunner — 単一エージェントの実行.

FR-RE-003, FR-RE-004: タイムアウト・ターン数制御・失敗許容を担当する。
"""

from __future__ import annotations

from hachimoku.models.agent_result import AgentResult

# 注: 実装時は engine._context.AgentExecutionContext を使用
# ここでは循環 import を避けるため TYPE_CHECKING ガード内で import する想定
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hachimoku.engine._context import AgentExecutionContext


async def run_agent(
    context: AgentExecutionContext,
) -> AgentResult:
    """単一エージェントを実行し、AgentResult を返す.

    実行フロー:
        1. pydantic-ai Agent を構築（model, tools, system_prompt, output_type）
        2. UsageLimits(request_limit=max_turns) でターン数制御
        3. run_agent_safe() で実行（agent.iter() ベース、CancelScope 衝突ガード付き）
        4. 結果を AgentResult に変換

    例外ハンドリング:
        - CLIExecutionError(error_type="timeout") → AgentTimeout
        - UsageLimitExceeded → AgentTruncated（部分結果あり）
        - その他の例外 → AgentError

    Args:
        context: エージェント実行コンテキスト。

    Returns:
        AgentResult: AgentSuccess / AgentTruncated / AgentError / AgentTimeout。
    """
    ...
