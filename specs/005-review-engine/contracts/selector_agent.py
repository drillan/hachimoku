"""Contract: SelectorAgent — エージェント選択処理.

FR-RE-002 Step 5: セレクターエージェントの構築・実行・結果解釈。
FR-RE-010: 空リスト返却時の正常終了。

pydantic-ai エージェントとして実行し、構造化出力で選択結果を返す。
"""

from __future__ import annotations

from collections.abc import Sequence

from hachimoku.agents.models import AgentDefinition
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.config import SelectorConfig

# 注: 実装時は engine._target から import
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget


class SelectorOutput(HachimokuBaseModel):
    """セレクターエージェントの構造化出力.

    Attributes:
        selected_agents: 実行すべきエージェント名リスト。
        reasoning: 選択理由（デバッグ・監査用）。
    """

    selected_agents: list[str]
    reasoning: str


async def run_selector(
    target: DiffTarget | PRTarget | FileTarget,
    available_agents: Sequence[AgentDefinition],
    selector_config: SelectorConfig,
    global_model: str,
    global_timeout: int,
    global_max_turns: int,
) -> SelectorOutput:
    """セレクターエージェントを実行し、実行すべきエージェントを選択する.

    実行フロー:
        1. SelectorConfig からモデル・タイムアウト・ターン数を解決
           （selector 個別設定 > グローバル設定 > デフォルト値）
        2. ToolCatalog から SelectorConfig.allowed_tools のツールを解決
        3. build_selector_instruction() でユーザーメッセージを構築
        4. pydantic-ai Agent(output_type=SelectorOutput) を構築
        5. asyncio.timeout() + UsageLimits でエージェントを実行
        6. SelectorOutput を返す

    エラー時の挙動（仕様 Edge Cases より）:
        - セレクター失敗（タイムアウト・実行エラー・不正出力）→ 例外送出
          （呼び出し元がキャッチして exit_code=3 を返す）
        - 空の selected_agents → 正常に SelectorOutput を返す
          （呼び出し元が空リストを判定して正常終了）

    Args:
        target: レビュー対象。
        available_agents: 利用可能なエージェント定義リスト。
        selector_config: セレクター個別設定。
        global_model: グローバルモデル名。
        global_timeout: グローバルタイムアウト秒数。
        global_max_turns: グローバル最大ターン数。

    Returns:
        SelectorOutput: 選択されたエージェント名リストと選択理由。

    Raises:
        SelectorError: セレクターエージェントの実行に失敗した場合。
    """
    ...
