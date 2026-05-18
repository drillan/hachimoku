"""変更内容計算 — レビュー対象から変更ファイルと内容を取得する。

select コマンドが applicability 評価の入力（変更ファイル basename 集合と
diff 内容）を得るために使用する。git / gh を subprocess で呼び出す。
"""

from __future__ import annotations

import subprocess
from pathlib import Path, PurePath
from typing import Final

from hachimoku.cli._file_resolver import FileResolutionError, resolve_files
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.review.target import (
    CommitTarget,
    DiffTarget,
    FileTarget,
    PRTarget,
    ReviewTarget,
)

_SUBPROCESS_TIMEOUT_SECONDS: Final[int] = 120


class ChangeSetError(Exception):
    """変更内容計算のエラー。git/gh 実行失敗・未インストール・タイムアウト等。"""


class ChangeSet(HachimokuBaseModel):
    """レビュー対象の変更内容。

    Attributes:
        changed_basenames: 変更ファイルの basename 集合。
        content: 変更内容テキスト（diff またはファイル内容）。
    """

    changed_basenames: frozenset[str]
    content: str


def _run(cmd: list[str]) -> str:
    """サブプロセスを実行し stdout を返す。失敗時は ChangeSetError。"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise ChangeSetError(
            f"Command not found: {cmd[0]}. Ensure it is installed and in PATH."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise ChangeSetError(
            f"{' '.join(cmd)} timed out after {_SUBPROCESS_TIMEOUT_SECONDS}s."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise ChangeSetError(f"{' '.join(cmd)} failed: {exc.stderr.strip()}") from exc
    return result.stdout


def _basenames(name_only_output: str) -> frozenset[str]:
    """git/gh の --name-only 出力から basename 集合を作る。"""
    return frozenset(
        PurePath(line).name for line in name_only_output.splitlines() if line
    )


def _changeset_from_git(diff_args: list[str]) -> ChangeSet:
    """git diff の引数（範囲指定）から ChangeSet を構築する。"""
    name_only = _run(["git", "diff", "--name-only", *diff_args])
    content = _run(["git", "diff", *diff_args])
    return ChangeSet(changed_basenames=_basenames(name_only), content=content)


def _changeset_diff(target: DiffTarget) -> ChangeSet:
    return _changeset_from_git([f"{target.base_branch}...HEAD"])


def _changeset_commit(target: CommitTarget) -> ChangeSet:
    return _changeset_from_git([target.from_ref, target.to_ref])


def _changeset_pr(target: PRTarget) -> ChangeSet:
    pr = str(target.pr_number)
    name_only = _run(["gh", "pr", "diff", pr, "--name-only"])
    content = _run(["gh", "pr", "diff", pr])
    return ChangeSet(changed_basenames=_basenames(name_only), content=content)


def _changeset_file(target: FileTarget) -> ChangeSet:
    try:
        resolved, _warnings = resolve_files(target.paths, filter_extensions=())
    except FileResolutionError as exc:
        raise ChangeSetError(str(exc)) from exc
    if resolved is None:
        raise ChangeSetError(f"No files found matching: {', '.join(target.paths)}.")
    basenames = frozenset(PurePath(p).name for p in resolved.paths)
    parts: list[str] = []
    for path in resolved.paths:
        try:
            parts.append(Path(path).read_text(encoding="utf-8"))
        except OSError as exc:
            raise ChangeSetError(f"Failed to read {path}: {exc}") from exc
    return ChangeSet(changed_basenames=basenames, content="\n".join(parts))


def compute_changeset(target: ReviewTarget) -> ChangeSet:
    """レビュー対象から ChangeSet を計算する。

    Args:
        target: レビュー対象（diff / commit / pr / file のいずれか）。

    Returns:
        変更ファイル basename 集合と変更内容を保持する ChangeSet。

    Raises:
        ChangeSetError: git/gh 実行失敗、ファイル解決失敗、読み取り失敗時。
    """
    if isinstance(target, DiffTarget):
        return _changeset_diff(target)
    if isinstance(target, CommitTarget):
        return _changeset_commit(target)
    if isinstance(target, PRTarget):
        return _changeset_pr(target)
    if isinstance(target, FileTarget):
        return _changeset_file(target)
    raise AssertionError(f"unreachable: unknown target type {type(target)}")
