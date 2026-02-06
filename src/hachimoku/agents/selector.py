"""エージェントセレクター。

レビュー対象（ファイルパス・差分内容）に基づいて ApplicabilityRule を評価し、
適用すべきエージェントを Phase 順でソートして返す。
"""

import fnmatch
import os
import re

from hachimoku.agents.models import (
    PHASE_ORDER,
    AgentDefinition,
    ApplicabilityRule,
)


def _matches(
    rule: ApplicabilityRule,
    file_paths: list[str],
    content: str,
) -> bool:
    """適用ルールを評価し、エージェントが適用されるかを判定する。

    評価ロジック（OR 条件、早期リターン）:
    1. always=True → True
    2. file_patterns のいずれかにファイル名（basename）がマッチ → True
    3. content_patterns のいずれかにコンテンツがマッチ → True
    4. いずれも該当しない → False

    Args:
        rule: 評価対象の適用ルール。
        file_paths: レビュー対象のファイルパスリスト。
        content: 差分内容またはファイル内容。

    Returns:
        エージェントが適用される場合 True。
    """
    if rule.always:
        return True

    for pattern in rule.file_patterns:
        for path in file_paths:
            if fnmatch.fnmatch(os.path.basename(path), pattern):
                return True

    for pattern in rule.content_patterns:
        if re.search(pattern, content):
            return True

    return False


def select_agents(
    agents: list[AgentDefinition],
    file_paths: list[str],
    content: str,
) -> list[AgentDefinition]:
    """適用ルールに基づいてエージェントを選択し、Phase 順でソートして返す。

    Args:
        agents: 選択候補のエージェント定義リスト。
        file_paths: レビュー対象のファイルパスリスト。
        content: 差分内容またはファイル内容。

    Returns:
        適用されるエージェントを Phase 順（early → main → final）、
        同 Phase 内は名前の辞書順でソートしたリスト。
    """
    matched = [a for a in agents if _matches(a.applicability, file_paths, content)]
    return sorted(matched, key=lambda a: (PHASE_ORDER[a.phase], a.name))
