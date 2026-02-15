"""HistoryWriter -- レビュー結果の JSONL 自動蓄積。

FR-025: レビュー結果を .hachimoku/reviews/ に JSONL 形式で自動蓄積。
FR-026: ReviewHistoryRecord の各バリアントを1行の JSON オブジェクトとして書き出す。
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, assert_never

from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models.history import (
    DiffReviewRecord,
    FileReviewRecord,
    PRReviewRecord,
)
from hachimoku.models.report import ReviewReport


class HistoryWriteError(Exception):
    """JSONL 書き込みエラー。ディレクトリ作成失敗、I/O エラー等。"""


class GitInfoError(Exception):
    """git 情報取得エラー。git コマンド失敗等。"""


_GIT_TIMEOUT_SECONDS: Final[int] = 5
"""git コマンドのタイムアウト秒数。"""

_DIFF_FILENAME: Final[str] = "diff.jsonl"
_FILES_FILENAME: Final[str] = "files.jsonl"
_PR_FILENAME_TEMPLATE: Final[str] = "pr-{pr_number}.jsonl"


def _resolve_jsonl_path(
    reviews_dir: Path,
    target: DiffTarget | PRTarget | FileTarget,
) -> Path:
    """ターゲットに応じた JSONL ファイルパスを解決する。

    Args:
        reviews_dir: .hachimoku/reviews/ ディレクトリのパス。
        target: レビュー対象。

    Returns:
        JSONL ファイルの絶対パス。
    """
    if isinstance(target, DiffTarget):
        return reviews_dir / _DIFF_FILENAME
    if isinstance(target, PRTarget):
        return reviews_dir / _PR_FILENAME_TEMPLATE.format(pr_number=target.pr_number)
    if isinstance(target, FileTarget):
        return reviews_dir / _FILES_FILENAME
    assert_never(target)


def _run_git_command(args: list[str]) -> str:
    """git コマンドを実行し、stdout を返す共通ヘルパー。

    Args:
        args: git サブコマンドと引数のリスト（例: ``["rev-parse", "HEAD"]``）。

    Returns:
        コマンドの stdout（前後空白除去済み）。

    Raises:
        GitInfoError: git コマンド失敗・未インストール・タイムアウト時。
    """
    cmd = ["git", *args]
    cmd_str = " ".join(cmd)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        raise GitInfoError(
            "git command not found. Ensure git is installed and available in PATH."
        ) from None
    except subprocess.TimeoutExpired as exc:
        raise GitInfoError(
            f"{cmd_str} timed out after {_GIT_TIMEOUT_SECONDS}s."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise GitInfoError(f"{cmd_str} failed: {exc.stderr.strip()}") from exc
    return result.stdout.strip()


def get_commit_hash() -> str:
    """現在の HEAD コミットハッシュ（40文字16進小文字）を取得する。

    Returns:
        40文字のコミットハッシュ。

    Raises:
        GitInfoError: git コマンド失敗・未インストール・タイムアウト時。
    """
    return _run_git_command(["rev-parse", "HEAD"])


def get_branch_name() -> str:
    """現在のブランチ名を取得する。

    detached HEAD の場合は ``"HEAD"`` を返す。

    Returns:
        ブランチ名文字列。

    Raises:
        GitInfoError: git コマンド失敗・未インストール・タイムアウト時。
    """
    return _run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])


def _build_record(
    target: DiffTarget | PRTarget | FileTarget,
    report: ReviewReport,
    commit_hash: str,
    branch_name: str,
    reviewed_at: datetime,
) -> DiffReviewRecord | PRReviewRecord | FileReviewRecord:
    """ターゲットと結果から ReviewHistoryRecord バリアントを構築する。

    Args:
        target: レビュー対象。
        report: レビューレポート。
        commit_hash: コミットハッシュ（diff/PR モード用）。
        branch_name: ブランチ名（diff/PR モード用）。
        reviewed_at: レビュー実行日時。

    Returns:
        構築された ReviewHistoryRecord バリアント。
    """
    if isinstance(target, DiffTarget):
        return DiffReviewRecord(
            commit_hash=commit_hash,
            branch_name=branch_name,
            reviewed_at=reviewed_at,
            results=report.results,
            summary=report.summary,
        )
    if isinstance(target, PRTarget):
        return PRReviewRecord(
            commit_hash=commit_hash,
            pr_number=target.pr_number,
            branch_name=branch_name,
            reviewed_at=reviewed_at,
            results=report.results,
            summary=report.summary,
        )
    if isinstance(target, FileTarget):
        return FileReviewRecord(
            file_paths=frozenset(target.paths),
            reviewed_at=reviewed_at,
            working_directory=str(Path.cwd()),
            results=report.results,
            summary=report.summary,
        )
    assert_never(target)


def save_review_history(
    reviews_dir: Path,
    target: DiffTarget | PRTarget | FileTarget,
    report: ReviewReport,
) -> Path:
    """レビュー結果を JSONL ファイルに追記する。

    FR-025 のメインエントリポイント。
    1. git 情報取得（diff/PR モードのみ）
    2. ReviewHistoryRecord 構築
    3. JSONL ファイルへの追記

    Args:
        reviews_dir: .hachimoku/reviews/ ディレクトリのパス。
        target: レビュー対象。
        report: レビューレポート。

    Returns:
        書き込み先 JSONL ファイルのパス。

    Raises:
        HistoryWriteError: ディレクトリ作成失敗、I/O エラー時。
        GitInfoError: git 情報取得失敗時（diff/PR モード）。
    """
    try:
        reviews_dir.mkdir(exist_ok=True)
    except OSError as exc:
        raise HistoryWriteError(
            f"Failed to create reviews directory: {reviews_dir}: {exc}\n"
            "Check directory permissions and available disk space."
        ) from exc

    commit_hash = ""
    branch_name = ""
    if isinstance(target, (DiffTarget, PRTarget)):
        commit_hash = get_commit_hash()
        branch_name = get_branch_name()

    reviewed_at = datetime.now(timezone.utc)
    record = _build_record(target, report, commit_hash, branch_name, reviewed_at)
    jsonl_path = _resolve_jsonl_path(reviews_dir, target)

    try:
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(record.model_dump_json())
            f.write("\n")
    except OSError as exc:
        raise HistoryWriteError(
            f"Failed to write review history to {jsonl_path}: {exc}\n"
            "Check file permissions and available disk space."
        ) from exc

    return jsonl_path
