"""Contract: SelectorAgent — エージェント選択処理.

FR-RE-002 Step 5-6: セレクター定義読み込み・セレクターエージェントの構築・実行・結果解釈。
FR-RE-010: 空リスト返却時の正常終了。

SelectorDefinition（TOML 定義）からシステムプロンプト・モデル・ツールを取得し、
SelectorConfig（設定）によるオーバーライドを適用して pydantic-ai エージェントとして実行する。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from hachimoku.agents.models import AgentDefinition
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.config import SelectorConfig

if TYPE_CHECKING:
    from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget


class SelectorDefinition(HachimokuBaseModel):
    """セレクターエージェントの TOML 定義.

    レビューエージェントの AgentDefinition と同様に、TOML ファイルから構築される。
    AgentDefinition とは異なり output_schema・phase・applicability を持たない
    （セレクターの出力は SelectorOutput に固定、フェーズ・適用条件の概念なし）。

    Attributes:
        name: セレクター名（"selector" 固定）。
        description: セレクターの説明。
        model: 使用する LLM モデル名。
        system_prompt: セレクターのシステムプロンプト。
        allowed_tools: 許可するツールカテゴリのリスト。
    """

    name: Literal["selector"]
    description: str = Field(min_length=1)
    model: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)
    allowed_tools: tuple[str, ...] = ("git_read", "gh_read", "file_read")


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
    selector_definition: SelectorDefinition,
    selector_config: SelectorConfig,
    global_model: str,
    global_timeout: int,
    global_max_turns: int,
) -> SelectorOutput:
    """セレクターエージェントを実行し、実行すべきエージェントを選択する.

    実行フロー:
        1. モデルを解決（SelectorConfig.model > SelectorDefinition.model
           > global_model）。タイムアウト・ターン数は SelectorConfig > グローバル設定
           > デフォルト値の優先順で解決
        2. ToolCatalog から SelectorDefinition.allowed_tools のツールを解決
        3. SelectorDefinition.system_prompt でシステムプロンプトを設定し、
           build_selector_instruction() でユーザーメッセージを構築
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
        selector_definition: セレクターエージェントの TOML 定義（モデル・プロンプト・ツール）。
        selector_config: セレクター個別設定（モデル・タイムアウト・ターン数の上書き）。
        global_model: グローバルモデル名。
        global_timeout: グローバルタイムアウト秒数。
        global_max_turns: グローバル最大ターン数。

    Returns:
        SelectorOutput: 選択されたエージェント名リストと選択理由。

    Raises:
        SelectorError: セレクターエージェントの実行に失敗した場合。
    """
    ...
