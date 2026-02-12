"""ReviewInstructionBuilder — レビュー指示情報の構築。

FR-RE-001: 入力モードに応じたプロンプトコンテキストの生成。
FR-RE-011: --issue オプションの Issue 番号注入。
FR-RE-012: PR モードでの PR メタデータ注入指示。
Issue #129: エンジンが事前解決したコンテンツをインストラクションに埋め込む。
Issue #172: referenced_content のサイズ上限と truncation。
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING

from hachimoku.agents.models import AgentDefinition
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models.config import DEFAULT_REFERENCED_CONTENT_MAX_CHARS

if TYPE_CHECKING:
    from hachimoku.engine._selector import ReferencedContent

# Issue #172: コードフェンス検出パターン（``` or ~~~、3文字以上）
_FENCE_PATTERN: re.Pattern[str] = re.compile(r"^(`{3,}|~{3,})", re.MULTILINE)


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


def _close_unclosed_fences(text: str) -> str:
    """切り詰めテキスト内の未閉鎖 Markdown コードフェンスを閉じる。

    Issue #172: truncation でコードブロック構文が破壊されないよう、
    未閉鎖のフェンス（``` or ~~~）を検出して対応する閉鎖マーカーを追加する。

    Args:
        text: 切り詰め済みテキスト。

    Returns:
        未閉鎖フェンスがあれば閉鎖マーカーを追加したテキスト。
        全フェンスが閉鎖済みの場合は元のまま。
    """
    open_fence: str | None = None
    for match in _FENCE_PATTERN.finditer(text):
        marker = match.group(1)
        if open_fence is None:
            # フェンス開始
            open_fence = marker
        elif marker[0] == open_fence[0] and len(marker) >= len(open_fence):
            # 同種かつ同等以上の長さ → フェンス閉鎖
            open_fence = None
        # それ以外はフェンス内のリテラルテキスト（無視）
    if open_fence is not None:
        return f"{text}\n{open_fence}"
    return text


def _truncate_content(content: str, max_chars: int) -> str:
    """referenced_content の個別コンテンツを切り詰める。

    Issue #172: 大きなドキュメントによるトークン消費を抑制するため、
    指定文字数を超えるコンテンツを末尾切り詰め + truncation マーカー追加。

    Args:
        content: 切り詰め対象のテキスト。
        max_chars: 最大文字数（正の整数）。

    Returns:
        上限以下の場合は元のまま。超過時は切り詰め + フェンス閉鎖 + マーカー付き。

    Raises:
        ValueError: max_chars が 1 未満の場合。
    """
    if max_chars < 1:
        msg = f"max_chars must be positive, got {max_chars}"
        raise ValueError(msg)
    if len(content) <= max_chars:
        return content
    truncated = _close_unclosed_fences(content[:max_chars])
    return f"{truncated}\n\n... (truncated, original: {len(content)} chars)"


def build_selector_context_section(
    *,
    change_intent: str,
    affected_files: Sequence[str],
    relevant_conventions: Sequence[str],
    issue_context: str,
    referenced_content: Sequence[ReferencedContent] = (),
    max_referenced_content_chars: int = DEFAULT_REFERENCED_CONTENT_MAX_CHARS,
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
        max_referenced_content_chars: referenced_content の各 content の最大文字数。
            Issue #172: 大きなドキュメントによるトークン消費を抑制。

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
            content = _truncate_content(ref.content, max_referenced_content_chars)
            fence = "```"
            while fence in content:
                fence += "`"
            ref_parts.append(
                f"#### [{ref.reference_type}] {ref.reference_id}\n"
                f"{fence}\n{content}\n{fence}"
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
