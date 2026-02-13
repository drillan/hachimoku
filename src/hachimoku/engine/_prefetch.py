"""SelectorContextPrefetch — セレクターエージェント向けコンテキスト事前取得。

Issue #187: セレクターのツール呼び出し削減のため、
Issue コンテキスト、PR メタデータ、プロジェクト規約を事前取得しプロンプトに埋め込む。
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Final

from pydantic import Field

from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models._base import HachimokuBaseModel

logger = logging.getLogger(__name__)

_ISSUE_REF_PATTERN: re.Pattern[str] = re.compile(r"#(\d+)")
"""diff テキスト内の Issue 番号参照パターン（#123 形式）。"""

_SUBPROCESS_TIMEOUT_SECONDS: Final[int] = 120
"""subprocess のタイムアウト秒数。_resolver.py と統一。"""

ISSUE_CONTEXT_MAX_CHARS: Final[int] = 5000
"""Issue コンテキストの最大文字数。"""

PR_METADATA_MAX_CHARS: Final[int] = 3000
"""PR メタデータの最大文字数。"""

CONVENTIONS_MAX_CHARS: Final[int] = 5000
"""プロジェクト規約ファイルの最大文字数（ファイルごと）。"""

REFERENCED_ISSUE_MAX_CHARS: Final[int] = 3000
"""参照 Issue コンテンツの最大文字数（Issue ごと）。"""

DEFAULT_CONVENTION_FILES: Final[tuple[str, ...]] = (
    "CLAUDE.md",
    ".hachimoku/config.toml",
)
"""プロジェクト規約ファイルのデフォルト候補（CWD からの相対パス）。"""


class PrefetchError(Exception):
    """コンテキスト事前取得の失敗。

    明示的に指定された対象（issue_number, pr_number）の取得失敗を表す。
    """


class PrefetchedReference(HachimokuBaseModel):
    """diff 内で検出された参照の事前取得結果。"""

    reference_type: str = Field(min_length=1)
    reference_id: str = Field(min_length=1)
    content: str = Field(min_length=1)


class PrefetchedContext(HachimokuBaseModel):
    """セレクターエージェント向けの事前取得コンテキスト。

    各フィールドが空文字列/空タプルの場合、対応する事前取得が
    不要だったことを意味する。
    """

    issue_context: str = ""
    pr_metadata: str = ""
    project_conventions: str = ""
    referenced_issues: tuple[PrefetchedReference, ...] = ()


def extract_issue_references(
    content: str,
    exclude_numbers: frozenset[int] = frozenset(),
) -> frozenset[int]:
    """diff テキストから Issue 番号参照（#NNN 形式）を抽出する。

    Args:
        content: diff テキストまたはその他のコンテンツ。
        exclude_numbers: 除外する Issue 番号（target.issue_number 等）。

    Returns:
        検出された Issue 番号の集合（exclude_numbers と #0 を除く）。
    """
    matches = _ISSUE_REF_PATTERN.findall(content)
    return frozenset(
        num for m in matches if (num := int(m)) > 0 and num not in exclude_numbers
    )


def _truncate(content: str, max_chars: int) -> str:
    """コンテンツを最大文字数で切り詰める。

    Args:
        content: 対象テキスト。
        max_chars: 最大文字数。

    Returns:
        切り詰め済みテキスト（超過時は truncated マーカー付き）。
    """
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + f"\n... (truncated, original: {len(content)} chars)"


async def _run_gh(*args: str) -> str:
    """gh コマンドを非同期で実行し stdout を返す。

    Args:
        *args: gh コマンドの引数（"gh" 自体は含まない）。

    Returns:
        stdout のテキスト出力。

    Raises:
        PrefetchError: コマンド失敗、未検出、タイムアウト時。
    """
    cmd_display = f"gh {' '.join(args)}"
    try:
        proc = await asyncio.create_subprocess_exec(
            "gh",
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_SUBPROCESS_TIMEOUT_SECONDS
        )
    except FileNotFoundError as exc:
        raise PrefetchError(
            "gh command not found. Ensure gh is installed and available in PATH."
        ) from exc
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise PrefetchError(
            f"{cmd_display} timed out after {_SUBPROCESS_TIMEOUT_SECONDS}s"
        ) from exc

    if proc.returncode != 0:
        stderr_text = stderr.decode(errors="replace").strip()
        raise PrefetchError(
            f"{cmd_display} failed (exit {proc.returncode}): {stderr_text}"
        )

    return stdout.decode(errors="replace")


async def _fetch_issue_context(issue_number: int) -> str:
    """gh issue view で Issue コンテキストを取得する。

    Args:
        issue_number: Issue 番号。

    Returns:
        Issue のテキスト内容（truncation 適用済み）。

    Raises:
        PrefetchError: gh コマンドの実行に失敗した場合。
    """
    content = await _run_gh("issue", "view", str(issue_number))
    return _truncate(content, ISSUE_CONTEXT_MAX_CHARS)


async def _fetch_pr_metadata(pr_number: int) -> str:
    """gh pr view で PR メタデータを取得する。

    Args:
        pr_number: PR 番号。

    Returns:
        PR のメタデータテキスト（truncation 適用済み）。

    Raises:
        PrefetchError: gh コマンドの実行に失敗した場合。
    """
    content = await _run_gh("pr", "view", str(pr_number))
    return _truncate(content, PR_METADATA_MAX_CHARS)


def _read_project_conventions(
    convention_files: tuple[str, ...] = DEFAULT_CONVENTION_FILES,
) -> str:
    """プロジェクト規約ファイル（CLAUDE.md, config.toml）を読み込む。

    CWD から convention_files の各パスを読み込み、
    ファイルが存在する場合のみ内容を結合して返す。

    Args:
        convention_files: 読み込む規約ファイルのパス（CWD からの相対パス）。

    Returns:
        規約ファイルの内容を結合したテキスト。該当ファイルがない場合は空文字列。

    Raises:
        PrefetchError: ファイルの読み込みに失敗した場合（存在するが読めない等）。
    """
    parts: list[str] = []
    for rel_path in convention_files:
        file_path = Path(rel_path)
        if not file_path.is_file():
            continue
        try:
            content = file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise PrefetchError(
                f"Failed to read convention file '{rel_path}': {exc}"
            ) from exc
        parts.append(f"--- {rel_path} ---\n{_truncate(content, CONVENTIONS_MAX_CHARS)}")
    return "\n\n".join(parts)


async def _fetch_referenced_issues(
    issue_numbers: frozenset[int],
) -> tuple[PrefetchedReference, ...]:
    """diff 内で参照されている Issue を取得する。

    発見的に抽出された参照のため、個別の取得失敗は警告ログを出力しスキップする。

    Args:
        issue_numbers: 取得対象の Issue 番号集合。

    Returns:
        取得成功した参照のタプル。
    """
    if not issue_numbers:
        return ()

    results: list[PrefetchedReference] = []
    for num in sorted(issue_numbers):
        try:
            content = await _run_gh("issue", "view", str(num))
            truncated = _truncate(content, REFERENCED_ISSUE_MAX_CHARS)
            results.append(
                PrefetchedReference(
                    reference_type="issue",
                    reference_id=f"#{num}",
                    content=truncated,
                )
            )
        except PrefetchError:
            logger.warning(
                "Failed to fetch referenced issue #%d, skipping",
                num,
            )
    return tuple(results)


async def prefetch_selector_context(
    target: DiffTarget | PRTarget | FileTarget,
    resolved_content: str,
    convention_files: tuple[str, ...] = DEFAULT_CONVENTION_FILES,
) -> PrefetchedContext:
    """セレクターエージェント向けのコンテキストを事前取得する。

    パイプラインの Step 3.7 として実行される。

    Args:
        target: レビュー対象。
        resolved_content: 事前解決されたコンテンツ（diff テキスト等）。
        convention_files: 読み込む規約ファイルのパス（CWD からの相対パス）。

    Returns:
        事前取得されたコンテキスト。

    Raises:
        PrefetchError: 明示的な対象の取得に失敗した場合。
    """
    issue_context = ""
    pr_metadata = ""

    if target.issue_number is not None:
        issue_context = await _fetch_issue_context(target.issue_number)

    if isinstance(target, PRTarget):
        pr_metadata = await _fetch_pr_metadata(target.pr_number)

    project_conventions = _read_project_conventions(convention_files)

    exclude: frozenset[int] = frozenset()
    if target.issue_number is not None:
        exclude = frozenset({target.issue_number})
    ref_numbers = extract_issue_references(resolved_content, exclude_numbers=exclude)
    referenced_issues = await _fetch_referenced_issues(ref_numbers)

    return PrefetchedContext(
        issue_context=issue_context,
        pr_metadata=pr_metadata,
        project_conventions=project_conventions,
        referenced_issues=referenced_issues,
    )
