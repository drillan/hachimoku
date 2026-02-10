"""ReviewInstructionBuilder — レビュー指示情報の構築。

FR-RE-001: 入力モードに応じたプロンプトコンテキストの生成。
FR-RE-011: --issue オプションの Issue 番号注入。
FR-RE-012: PR モードでの PR メタデータ注入指示。
Issue #129: エンジンが事前解決したコンテンツをインストラクションに埋め込む。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from hachimoku.agents.models import AgentDefinition
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget


class _HasReferenceFields(Protocol):
    """参照先データの構造プロトコル。

    ReferencedContent モデルとの循環インポートを回避するための duck typing。
    """

    @property
    def reference_type(self) -> str: ...
    @property
    def reference_id(self) -> str: ...
    @property
    def content(self) -> str: ...


def build_review_instruction(
    target: DiffTarget | PRTarget | FileTarget,
    resolved_content: str,
) -> str:
    """ReviewTarget からエージェント向けのユーザーメッセージを構築する。

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
    parts: list[str] = [_build_mode_section(target, resolved_content)]

    if target.issue_number is not None:
        parts.append(
            f"\nRelated Issue: #{target.issue_number}\n"
            f"Use gh tools to fetch issue details for additional context."
        )

    return "\n".join(parts)


def build_selector_instruction(
    target: DiffTarget | PRTarget | FileTarget,
    available_agents: Sequence[AgentDefinition],
    resolved_content: str,
) -> str:
    """セレクターエージェント向けのユーザーメッセージを構築する。

    レビュー指示情報に加えて、利用可能なエージェント定義一覧
    （名前・説明・適用ルール・フェーズ）を含む。

    Args:
        target: レビュー対象。
        available_agents: 利用可能なエージェント定義リスト。
        resolved_content: 事前解決されたコンテンツ。

    Returns:
        セレクターエージェントに渡すユーザーメッセージ文字列。
    """
    review_section = build_review_instruction(target, resolved_content)
    agents_section = _build_agents_section(available_agents)

    return (
        f"{review_section}\n\n"
        f"## Available Agents\n\n"
        f"{agents_section}\n\n"
        f"Select the agents that are most applicable for this review."
    )


def build_selector_context_section(
    *,
    change_intent: str,
    affected_files: Sequence[str],
    relevant_conventions: Sequence[str],
    issue_context: str,
    referenced_content: Sequence[_HasReferenceFields] = (),
) -> str:
    """セレクターの分析結果をレビューエージェント向けマークダウンセクションに変換する。

    FR-RE-002 Step 5.5: セレクターメタデータのユーザーメッセージ拡張。
    メタデータが全て空（空文字列・空リスト）の場合は空文字列を返す。
    非空のフィールドのみ対応するサブセクションを出力する。

    Args:
        change_intent: 変更の意図・目的の要約。
        affected_files: diff 外で影響を受ける可能性のあるファイルパス。
        relevant_conventions: 当該変更に関連するプロジェクト規約。
        issue_context: Issue 関連情報の要約。
        referenced_content: diff 内で参照されている外部リソースの取得結果。

    Returns:
        マークダウンセクション文字列。全て空の場合は空文字列。
    """
    subsections: list[str] = []

    if change_intent:
        subsections.append(f"### Change Intent\n{change_intent}")

    if affected_files:
        files_list = "\n".join(f"- {f}" for f in affected_files)
        subsections.append(f"### Affected Files (Outside Diff)\n{files_list}")

    if relevant_conventions:
        conventions_list = "\n".join(f"- {c}" for c in relevant_conventions)
        subsections.append(f"### Relevant Project Conventions\n{conventions_list}")

    if issue_context:
        subsections.append(f"### Issue Context\n{issue_context}")

    if referenced_content:
        ref_parts: list[str] = []
        for ref in referenced_content:
            ref_parts.append(
                f"#### [{ref.reference_type}] {ref.reference_id}\n"
                f"```\n{ref.content}\n```"
            )
        subsections.append("### Referenced Content\n" + "\n\n".join(ref_parts))

    if not subsections:
        return ""

    return "## Selector Analysis Context\n\n" + "\n\n".join(subsections)


def _build_mode_section(
    target: DiffTarget | PRTarget | FileTarget,
    resolved_content: str,
) -> str:
    """入力モードに応じたプロンプトセクションを構築する。"""
    if isinstance(target, DiffTarget):
        return (
            f"Review the changes in the current branch compared to "
            f"'{target.base_branch}'.\n\n"
            f"{resolved_content}"
        )

    if isinstance(target, PRTarget):
        return (
            f"Review Pull Request #{target.pr_number}.\n"
            f"Use `gh pr view {target.pr_number}` to get PR metadata "
            f"(title, labels, linked issues).\n\n"
            f"{resolved_content}"
        )

    if isinstance(target, FileTarget):
        paths_list = "\n".join(f"- {p}" for p in target.paths)
        return f"Review the following files:\n{paths_list}\n\n{resolved_content}"

    raise TypeError(f"Unknown target type: {type(target)}")


def _build_agents_section(agents: Sequence[AgentDefinition]) -> str:
    """エージェント定義一覧のセクションを構築する。"""
    if not agents:
        return "No agents available."

    lines: list[str] = []
    for agent in agents:
        applicability_info = _format_applicability(agent)
        lines.append(
            f"- **{agent.name}**: {agent.description} "
            f"(phase={agent.phase.value}{applicability_info})"
        )

    return "\n".join(lines)


def _format_applicability(agent: AgentDefinition) -> str:
    """適用ルール情報をフォーマットする。"""
    parts: list[str] = []

    if agent.applicability.always:
        parts.append("always")
    if agent.applicability.file_patterns:
        patterns = ", ".join(agent.applicability.file_patterns)
        parts.append(f"files=[{patterns}]")
    if agent.applicability.content_patterns:
        patterns = ", ".join(agent.applicability.content_patterns)
        parts.append(f"content=[{patterns}]")

    if parts:
        return ", " + ", ".join(parts)
    return ""
