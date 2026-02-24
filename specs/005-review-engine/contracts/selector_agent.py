"""Contract: SelectorAgent — エージェント選択処理.

FR-RE-002 Step 5-6: セレクター定義読み込み・セレクターエージェントの構築・実行・結果解釈。
FR-RE-010: 空リスト返却時の正常終了。
Issue #195: SelectorDeps 依存性注入 + _prefetch_guardrail 動的ガードレール。

SelectorDefinition（TOML 定義）からシステムプロンプト・モデル・ツールを取得し、
SelectorConfig（設定）によるオーバーライドを適用して pydantic-ai エージェントとして実行する。
PrefetchedContext の内容に応じて動的ガードレール（instructions）を注入し、
事前取得済みデータの再取得を抑制する。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import Field

from hachimoku.agents.models import AgentDefinition
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.config import SelectorConfig

if TYPE_CHECKING:
    from pydantic_ai import RunContext

    from hachimoku.engine._prefetch import PrefetchedContext
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


@dataclass
class SelectorDeps:
    """セレクターエージェントの依存性コンテナ.

    Issue #195: pydantic-ai の Dependencies 機構を利用し、
    PrefetchedContext を依存性として注入する。

    Attributes:
        prefetched: 事前取得されたコンテキスト（Issue #187）。
    """

    prefetched: PrefetchedContext | None


def _prefetch_guardrail(ctx: RunContext[SelectorDeps]) -> str:
    """事前取得済みデータがある場合に再取得禁止のガードレールを注入する.

    Issue #195: PrefetchedContext の各フィールドが非空の場合に、
    対応するデータの再取得を禁止する指示を動的に生成する。
    pydantic-ai の ``instructions`` パラメータとして Agent に渡される。

    Args:
        ctx: pydantic-ai の RunContext。deps に SelectorDeps を保持。

    Returns:
        ガードレール指示テキスト。事前取得データがない場合は空文字列。
    """
    ...


async def run_selector(
    target: DiffTarget | PRTarget | FileTarget,
    available_agents: Sequence[AgentDefinition],
    selector_definition: SelectorDefinition,
    selector_config: SelectorConfig,
    global_model: str,
    global_timeout: int,
    global_max_turns: int,
    resolved_content: str,
    prefetched_context: PrefetchedContext | None = None,
) -> SelectorOutput:
    """セレクターエージェントを実行し、実行すべきエージェントを選択する.

    実行フロー:
        1. モデルを解決（SelectorConfig.model > SelectorDefinition.model
           > global_model）。タイムアウト・ターン数は SelectorConfig > グローバル設定
           > デフォルト値の優先順で解決
        2. ToolCatalog から SelectorDefinition.allowed_tools のツールを解決
        3. SelectorDefinition.system_prompt でシステムプロンプトを設定し、
           build_selector_instruction() でユーザーメッセージを構築
        4. pydantic-ai Agent(output_type=SelectorOutput, deps_type=SelectorDeps,
           instructions=_prefetch_guardrail) を構築
        5. UsageLimits でエージェントを実行
           （タイムアウトは ClaudeCodeModelSettings 経由で SDK に委譲、
           deps=SelectorDeps(prefetched=prefetched_context) を渡す）
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
        resolved_content: 事前解決されたコンテンツ（diff テキスト、ファイル内容等）。
        prefetched_context: 事前取得されたコンテキスト（Issue #187）。

    Returns:
        SelectorOutput: 選択されたエージェント名リストと選択理由。

    Raises:
        SelectorError: セレクターエージェントの実行に失敗した場合。
    """
    ...
