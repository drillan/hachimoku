"""差分フィルタリング — エージェント別 file_patterns ベースの差分抽出。

Issue #171: エージェントの file_patterns にマッチするファイルの差分のみを抽出し、
関係ないファイルの差分を除外することで入力トークンを削減する。
"""

from __future__ import annotations

import fnmatch
import re
from os.path import basename
from typing import Final

_DIFF_SECTION_RE: Final[re.Pattern[str]] = re.compile(r"^diff --git ", re.MULTILINE)
"""unified diff のファイル単位セクション区切りパターン。"""

_FILE_PATH_RE: Final[re.Pattern[str]] = re.compile(r"diff --git a/.+ b/(.+)")
"""diff --git ヘッダーからファイルパス（b/側）を抽出するパターン。"""


def filter_diff_by_file_patterns(
    diff_text: str,
    file_patterns: tuple[str, ...],
) -> str:
    """unified diff をファイル単位で分割し、file_patterns にマッチするファイルのみ抽出する。

    fnmatch でファイルの basename に対してマッチングを行う。
    マッチするファイルがない場合は diff_text をそのまま返す（リカバリ動作）。
    diff_text が空、unified diff フォーマットでない、またはパターンが空の場合は
    そのまま返す。

    Args:
        diff_text: unified diff テキスト（git diff / gh pr diff の出力）。
        file_patterns: fnmatch 互換のファイルパターンタプル。

    Returns:
        フィルタリング後の diff テキスト。
    """
    if not diff_text or not file_patterns:
        return diff_text

    positions = [m.start() for m in _DIFF_SECTION_RE.finditer(diff_text)]
    if not positions:
        return diff_text

    matched_sections: list[str] = []
    seen_paths: set[str] = set()

    for idx, pos in enumerate(positions):
        end = positions[idx + 1] if idx + 1 < len(positions) else len(diff_text)
        section = diff_text[pos:end]

        file_path = _extract_file_path(section)
        if not file_path:
            continue

        if file_path in seen_paths:
            continue

        file_basename = basename(file_path)
        if any(fnmatch.fnmatch(file_basename, p) for p in file_patterns):
            matched_sections.append(section)
            seen_paths.add(file_path)

    if not matched_sections:
        return diff_text

    return "".join(matched_sections)


def _extract_file_path(diff_section: str) -> str:
    """diff --git ヘッダーからファイルパス（b/側）を抽出する。

    Args:
        diff_section: ``diff --git`` で始まる単一ファイルのセクション。

    Returns:
        ファイルパス文字列。抽出できない場合は空文字列。
    """
    first_line = diff_section.split("\n", 1)[0]
    match = _FILE_PATH_RE.match(first_line)
    return match.group(1) if match else ""
