"""SelectorContextPrefetch — セレクターエージェント向けコンテキスト事前取得。

Issue #187: セレクターのツール呼び出し削減のため、
Issue コンテキスト、PR メタデータ、プロジェクト規約を事前取得しプロンプトに埋め込む。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Final

from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models._base import HachimokuBaseModel

_SUBPROCESS_TIMEOUT_SECONDS: Final[int] = 120
"""subprocess のタイムアウト秒数。_resolver.py と統一。"""

ISSUE_CONTEXT_MAX_CHARS: Final[int] = 5000
"""Issue コンテキストの最大文字数。"""

PR_METADATA_MAX_CHARS: Final[int] = 3000
"""PR メタデータの最大文字数。"""

CONVENTIONS_MAX_CHARS: Final[int] = 5000
"""プロジェクト規約ファイルの最大文字数（ファイルごと）。"""

DEFAULT_CONVENTION_FILES: Final[tuple[str, ...]] = (
    "CLAUDE.md",
    ".hachimoku/config.toml",
)
"""プロジェクト規約ファイルのデフォルト候補（CWD からの相対パス）。"""


class PrefetchError(Exception):
    """コンテキスト事前取得の失敗。

    明示的に指定された対象（issue_number, pr_number）の取得失敗を表す。
    """


class PrefetchedContext(HachimokuBaseModel):
    """セレクターエージェント向けの事前取得コンテキスト。

    各フィールドが空文字列の場合、対応する事前取得が
    不要だったことを意味する。
    """

    issue_context: str = ""
    pr_metadata: str = ""
    project_conventions: str = ""


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
    except FileNotFoundError as exc:
        raise PrefetchError(
            "gh command not found. Ensure gh is installed and available in PATH."
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_SUBPROCESS_TIMEOUT_SECONDS
        )
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise PrefetchError(
            f"{cmd_display} timed out after {_SUBPROCESS_TIMEOUT_SECONDS}s"
        ) from exc
    except BaseException:
        proc.kill()
        await proc.wait()
        raise

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


async def prefetch_selector_context(
    target: DiffTarget | PRTarget | FileTarget,
    convention_files: tuple[str, ...] = DEFAULT_CONVENTION_FILES,
) -> PrefetchedContext:
    """セレクターエージェント向けのコンテキストを事前取得する。

    パイプラインの Step 3.7 として実行される。

    Args:
        target: レビュー対象。
        convention_files: 読み込む規約ファイルのパス（CWD からの相対パス）。

    Returns:
        事前取得されたコンテキスト。

    Raises:
        PrefetchError: 明示的な対象の取得に失敗した場合。
    """
    coros: list[asyncio.Task[str]] = []

    fetch_issue = target.issue_number is not None
    fetch_pr = isinstance(target, PRTarget)

    if fetch_issue:
        assert target.issue_number is not None  # for type narrowing
        coros.append(asyncio.ensure_future(_fetch_issue_context(target.issue_number)))
    if fetch_pr:
        assert isinstance(target, PRTarget)  # for type narrowing
        coros.append(asyncio.ensure_future(_fetch_pr_metadata(target.pr_number)))

    results = await asyncio.gather(*coros) if coros else []

    idx = 0
    issue_context = ""
    if fetch_issue:
        issue_context = results[idx]
        idx += 1

    pr_metadata = ""
    if fetch_pr:
        pr_metadata = results[idx]

    project_conventions = _read_project_conventions(convention_files)

    return PrefetchedContext(
        issue_context=issue_context,
        pr_metadata=pr_metadata,
        project_conventions=project_conventions,
    )
