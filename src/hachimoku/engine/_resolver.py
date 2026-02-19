"""ContentResolver — レビュー対象コンテンツの事前解決。

Issue #129: エンジンが diff を事前解決して全エージェントのインストラクションに埋め込む。
ターゲットタイプに応じて subprocess またはファイル読み込みでコンテンツを取得する。
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Final

from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget

_SUBPROCESS_TIMEOUT_SECONDS: Final[int] = 120
"""subprocess のタイムアウト秒数。既存 _tools/_git.py と同一。"""


class ContentResolveError(Exception):
    """コンテンツ事前解決の失敗。

    git/gh コマンドの失敗、コマンド未検出、ファイル不存在など
    コンテンツ取得に関するあらゆる失敗を表す。
    """


async def resolve_content(target: DiffTarget | PRTarget | FileTarget) -> str:
    """ターゲットに応じてレビュー対象コンテンツを事前解決する。

    Args:
        target: レビュー対象（DiffTarget / PRTarget / FileTarget）。

    Returns:
        解決されたコンテンツ文字列。空 diff の場合は空文字列。

    Raises:
        ContentResolveError: コンテンツ取得に失敗した場合。
        TypeError: 未知のターゲット型の場合。
    """
    if isinstance(target, DiffTarget):
        return await _resolve_diff(target)
    if isinstance(target, PRTarget):
        return await _resolve_pr_diff(target)
    if isinstance(target, FileTarget):
        return _resolve_file_content(target)
    raise TypeError(f"Unknown target type: {type(target)}")


async def _resolve_diff(target: DiffTarget) -> str:
    """DiffTarget の差分を取得する。

    git merge-base でマージベースを取得し、git diff で差分を取得する。
    """
    merge_base = (
        await _run_subprocess("git", "merge-base", target.base_branch, "HEAD")
    ).strip()
    if not merge_base:
        raise ContentResolveError(
            f"git merge-base returned empty output for branch '{target.base_branch}'"
        )
    return await _run_subprocess("git", "diff", merge_base)


async def _resolve_pr_diff(target: PRTarget) -> str:
    """PRTarget の差分を取得する。"""
    return await _run_subprocess("gh", "pr", "diff", str(target.pr_number))


def _resolve_file_content(target: FileTarget) -> str:
    """FileTarget のファイル内容を取得する。

    各ファイルをパスヘッダー付きで結合して返す。
    """
    sections: list[str] = []
    for path_str in target.paths:
        file_path = Path(path_str)
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ContentResolveError(
                f"File '{path_str}' is not a valid UTF-8 text file"
            ) from exc
        except OSError as exc:
            raise ContentResolveError(f"Cannot read file '{path_str}': {exc}") from exc
        sections.append(f"--- {path_str} ---\n{content}")
    return "\n\n".join(sections)


async def _run_subprocess(*args: str) -> str:
    """subprocess を非同期で実行し、stdout を返す。

    Args:
        *args: 実行するコマンドと引数。

    Returns:
        stdout のテキスト出力。

    Raises:
        ContentResolveError: コマンド失敗、未検出、タイムアウト、デコード失敗時。
    """
    cmd_display = " ".join(args)
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ContentResolveError(
            f"Command not found: {args[0]}. "
            f"Ensure {args[0]} is installed and available in PATH."
        ) from exc

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=_SUBPROCESS_TIMEOUT_SECONDS
        )
    except TimeoutError as exc:
        proc.kill()
        await proc.wait()
        raise ContentResolveError(
            f"Command timed out after {_SUBPROCESS_TIMEOUT_SECONDS}s: {cmd_display}"
        ) from exc
    except BaseException:
        proc.kill()
        await proc.wait()
        raise

    if proc.returncode != 0:
        stderr_text = stderr.decode(errors="replace").strip()
        raise ContentResolveError(f"Command failed ({cmd_display}): {stderr_text}")

    try:
        return stdout.decode(errors="strict")
    except UnicodeDecodeError as exc:
        raise ContentResolveError(
            f"Command output contains non-UTF-8 bytes: {cmd_display}"
        ) from exc
