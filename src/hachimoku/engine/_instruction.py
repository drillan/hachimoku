"""ReviewInstructionBuilder — レビュー指示情報の構築。

FR-RE-001: 入力モードに応じたプロンプトコンテキストの生成。
FR-RE-011: --issue オプションの Issue 番号注入。
FR-RE-012: PR モードでの PR メタデータ注入指示。
"""

from __future__ import annotations

from collections.abc import Sequence

from hachimoku.agents.models import AgentDefinition
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget


def build_review_instruction(target: DiffTarget | PRTarget | FileTarget) -> str:
    """ReviewTarget からエージェント向けのユーザーメッセージを構築する。

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
    parts: list[str] = [_build_mode_section(target)]

    if target.issue_number is not None:
        parts.append(
            f"\nRelated Issue: #{target.issue_number}\n"
            f"Use gh tools to fetch issue details for additional context."
        )

    return "\n".join(parts)


def build_selector_instruction(
    target: DiffTarget | PRTarget | FileTarget,
    available_agents: Sequence[AgentDefinition],
) -> str:
    """セレクターエージェント向けのユーザーメッセージを構築する。

    レビュー指示情報に加えて、利用可能なエージェント定義一覧
    （名前・説明・適用ルール・フェーズ）を含む。

    Args:
        target: レビュー対象。
        available_agents: 利用可能なエージェント定義リスト。

    Returns:
        セレクターエージェントに渡すユーザーメッセージ文字列。
    """
    review_section = build_review_instruction(target)
    agents_section = _build_agents_section(available_agents)

    return (
        f"{review_section}\n\n"
        f"## Available Agents\n\n"
        f"{agents_section}\n\n"
        f"Select the agents that are most applicable for this review."
    )


def _build_mode_section(target: DiffTarget | PRTarget | FileTarget) -> str:
    """入力モードに応じたプロンプトセクションを構築する。"""
    if isinstance(target, DiffTarget):
        return (
            f"Review the changes in the current branch compared to '{target.base_branch}'.\n"
            f"Use `git merge-base {target.base_branch} HEAD` to find the common ancestor, "
            f"then `git diff <merge-base>` to get the diff."
        )

    if isinstance(target, PRTarget):
        return (
            f"Review Pull Request #{target.pr_number}.\n"
            f"Use `gh pr view {target.pr_number}` to get PR metadata "
            f"(title, labels, linked issues).\n"
            f"Use `gh pr diff {target.pr_number}` or git tools to get the diff."
        )

    if isinstance(target, FileTarget):
        paths_list = "\n".join(f"- {p}" for p in target.paths)
        return (
            f"Review the following files:\n{paths_list}\n\n"
            f"Use file tools to read the content of each file."
        )

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
