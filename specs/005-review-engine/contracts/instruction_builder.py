"""Contract: ReviewInstructionBuilder — レビュー指示情報の構築.

FR-RE-001: 入力モードに応じたプロンプトコンテキストの生成。
FR-RE-011: --issue オプションの Issue 番号注入。
FR-RE-012: PR モードでの PR メタデータ注入。

ReviewEngine と SelectorAgent の両方から参照される。
"""

from __future__ import annotations

# 注: ReviewTarget は実装時に engine._target から import
# 注: AgentDefinition は agents.models から import


def build_review_instruction(
    # target: ReviewTarget,
) -> str:
    """ReviewTarget からエージェント向けのユーザーメッセージを構築する.

    入力モードに応じて以下を含むプロンプト文字列を返す:

    - **diff モード**: base_branch 名、マージベースからの差分レビュー指示、
      推奨される diff 取得方法のガイダンス
    - **PR モード**: PR 番号、PR 差分・メタデータ取得指示
    - **file モード**: ファイルパスリスト、ファイル内容取得指示

    共通:
    - issue_number が指定されている場合、Issue 番号と取得指示を追加

    Args:
        target: レビュー対象（DiffTarget / PRTarget / FileTarget）。

    Returns:
        エージェントに渡すユーザーメッセージ文字列。
    """
    ...


def build_selector_instruction(
    # target: ReviewTarget,
    # available_agents: Sequence[AgentDefinition],
) -> str:
    """セレクターエージェント向けのユーザーメッセージを構築する.

    レビュー指示情報に加えて、利用可能なエージェント定義一覧
    （名前・説明・適用ルール・フェーズ）を含む。

    Args:
        target: レビュー対象。
        available_agents: 利用可能なエージェント定義リスト。

    Returns:
        セレクターエージェントに渡すユーザーメッセージ文字列。
    """
    ...
