"""Contract: ReviewInstructionBuilder — レビュー指示情報の構築.

FR-RE-001: 入力モードに応じたプロンプトコンテキストの生成。
FR-RE-011: --issue オプションの Issue 番号注入。
FR-RE-012: PR モードでの PR メタデータ注入。
Issue #129: エンジンが事前解決したコンテンツをインストラクションに埋め込む。

ReviewEngine と SelectorAgent の両方から参照される。
"""

from __future__ import annotations

# 注: ReviewTarget は実装時に engine._target から import
# 注: AgentDefinition は agents.models から import


def build_review_instruction(
    # target: ReviewTarget,
    # resolved_content: str,
) -> str:
    """ReviewTarget からエージェント向けのユーザーメッセージを構築する.

    入力モードに応じたヘッダーと、事前解決されたコンテンツを含む
    プロンプト文字列を返す。

    - **diff モード**: base_branch 名と事前解決された差分
    - **PR モード**: PR 番号、メタデータ取得指示、事前解決された差分
    - **file モード**: ファイルパスリストと事前解決されたファイル内容

    共通:
    - issue_number が指定されている場合、Issue 番号と取得指示を追加

    Args:
        target: レビュー対象（DiffTarget / PRTarget / FileTarget）。
        resolved_content: 事前解決されたコンテンツ（diff テキスト、ファイル内容等）。

    Returns:
        エージェントに渡すユーザーメッセージ文字列。
    """
    ...


def build_selector_instruction(
    # target: ReviewTarget,
    # available_agents: Sequence[AgentDefinition],
    # resolved_content: str,
) -> str:
    """セレクターエージェント向けのユーザーメッセージを構築する.

    レビュー指示情報に加えて、利用可能なエージェント定義一覧
    （名前・説明・適用ルール・フェーズ）を含む。

    Args:
        target: レビュー対象。
        available_agents: 利用可能なエージェント定義リスト。
        resolved_content: 事前解決されたコンテンツ。

    Returns:
        セレクターエージェントに渡すユーザーメッセージ文字列。
    """
    ...
