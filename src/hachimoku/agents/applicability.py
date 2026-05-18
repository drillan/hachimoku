"""applicability 評価器 — コード変更に対する ApplicabilityRule の決定的評価。

select（SP1-2b-2）が、変更ファイル集合と diff 内容から実行対象エージェントを
フェーズ別に決定するために使用する。LLM を用いない純関数群。
"""

from __future__ import annotations

import re
from fnmatch import fnmatch

from hachimoku.agents.manifest import Manifest
from hachimoku.agents.models import ApplicabilityRule, Phase


def change_matches(
    rule: ApplicabilityRule,
    changed_basenames: frozenset[str],
    content: str,
) -> bool:
    """単一の ApplicabilityRule をコード変更に対して評価する。

    評価セマンティクス（ApplicabilityRule の定義に準拠）:
        1. always=True なら常に適用。
        2. file_patterns のいずれかが changed_basenames の要素に
           fnmatch でマッチすれば適用。
        3. content_patterns のいずれかが content に re.search でマッチすれば適用。
        4. いずれも該当しなければ不適用。条件 2・3 は OR。

    Args:
        rule: 評価対象の適用ルール。
        changed_basenames: 変更ファイルの basename 集合。
        content: 変更内容（diff テキスト）。

    Returns:
        適用すべきなら True。
    """
    if rule.always:
        return True
    for pattern in rule.file_patterns:
        if any(fnmatch(basename, pattern) for basename in changed_basenames):
            return True
    for pattern in rule.content_patterns:
        if re.search(pattern, content):
            return True
    return False


def select_agent_names(
    manifest: Manifest,
    changed_basenames: frozenset[str],
    content: str,
) -> dict[Phase, list[str]]:
    """Manifest 全体を評価し、適用対象エージェント名をフェーズ別に返す。

    Args:
        manifest: 評価対象の Manifest。
        changed_basenames: 変更ファイルの basename 集合。
        content: 変更内容（diff テキスト）。

    Returns:
        フェーズをキー、適用対象エージェント名の昇順リストを値とする辞書。
        全 3 フェーズ（EARLY / MAIN / FINAL）を必ずキーに含む（該当なしは空リスト）。
    """
    result: dict[Phase, list[str]] = {phase: [] for phase in Phase}
    for entry in manifest.entries:
        if change_matches(entry.applicability, changed_basenames, content):
            result[entry.phase].append(entry.name)
    for phase in result:
        result[phase].sort()
    return result
