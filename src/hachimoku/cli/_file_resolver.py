"""FileResolver — file モードのファイル解決。

FR-CLI-009: ファイル・ディレクトリ・glob パターンの展開。
"""

from __future__ import annotations

import glob as glob_module
from pathlib import Path
from typing import Annotated

from pydantic import Field

from hachimoku.models._base import HachimokuBaseModel

_GLOB_SPECIAL_CHARS = frozenset("*?[")
_BINARY_CHECK_SIZE = 8192  # 8KB — git と同じヒューリスティクス


def _is_binary_file(file_path: Path) -> bool:
    """ファイルがバイナリかどうかを判定する。

    ファイル先頭の 8KB を読み込み、NULL バイト（0x00）が含まれていれば
    バイナリと判定する（git と同じヒューリスティクス）。

    Args:
        file_path: チェック対象のファイルパス。

    Returns:
        バイナリファイルの場合 True。
    """
    with file_path.open("rb") as f:
        chunk = f.read(_BINARY_CHECK_SIZE)
    return b"\x00" in chunk


class ResolvedFiles(HachimokuBaseModel):
    """ファイル解決結果。

    resolve_files() が構築する。paths は以下の不変条件を持つ:
    - 全要素が絶対パス
    - ソート済み（辞書順）
    - 重複排除済み
    - 通常ファイルのみ（ディレクトリは含まない）

    Attributes:
        paths: 展開・正規化済みのファイルパスリスト（文字列）。
        warnings: 循環参照等の警告メッセージ。
    """

    paths: tuple[Annotated[str, Field(min_length=1)], ...] = Field(min_length=1)
    warnings: tuple[str, ...] = ()


class FileResolutionError(Exception):
    """ファイル解決エラー。

    指定されたパスが存在しない場合等。
    エラーメッセージは解決方法のヒントを含む（憲法 Art.3）。
    """


def _is_glob_pattern(path_str: str) -> bool:
    """パス文字列が glob パターンかどうかを判定する。

    glob 特殊文字: *, ?, [
    """
    return bool(path_str) and bool(set(path_str) & _GLOB_SPECIAL_CHARS)


def _expand_directory(
    dir_path: Path,
    seen_real_dirs: set[Path],
) -> tuple[list[str], list[str]]:
    """ディレクトリを再帰探索する。シンボリックリンク循環参照を検出する。

    rglob("*") ではなく iterdir() + 手動再帰を使用する。
    rglob はシンボリックリンクを自動追従するため、循環参照で無限ループのリスクがある。

    Args:
        dir_path: 探索対象ディレクトリパス。
        seen_real_dirs: 既に探索した実体ディレクトリパスの集合（循環参照検出用）。

    Returns:
        (展開済みファイルパスリスト, 警告メッセージリスト)
    """
    real_dir = dir_path.resolve()
    if real_dir in seen_real_dirs:
        return [], [f"Skipping symlink cycle: {dir_path} -> {real_dir}"]

    seen_real_dirs.add(real_dir)
    file_paths: list[str] = []
    warnings: list[str] = []

    try:
        entries = sorted(dir_path.iterdir())
    except PermissionError as e:
        raise FileResolutionError(
            f"Permission denied: '{dir_path}'. "
            "Check directory permissions and try again."
        ) from e

    for entry in entries:
        if entry.is_file():
            if _is_binary_file(entry):
                warnings.append(f"Skipping binary file: {entry.resolve()}")
            else:
                file_paths.append(str(entry.resolve()))
        elif entry.is_dir():
            sub_files, sub_warnings = _expand_directory(entry, seen_real_dirs)
            file_paths.extend(sub_files)
            warnings.extend(sub_warnings)

    return file_paths, warnings


def _expand_single_path(
    raw_path: str,
    seen_real_dirs: set[Path],
) -> tuple[list[str], list[str]]:
    """単一パスを展開する。

    ディスパッチ順序:
    1. glob パターン → glob.glob() で展開
    2. 存在確認 → ファイル or ディレクトリ
    3. 不存在 → FileResolutionError

    Args:
        raw_path: 未展開のパス文字列。
        seen_real_dirs: 既に探索した実体ディレクトリパスの集合（循環参照検出用）。

    Returns:
        (展開済みファイルパスリスト, 警告メッセージリスト)

    Raises:
        FileResolutionError: 指定パスが存在しない場合。
    """
    # 1. glob パターン → glob.glob() で展開
    if _is_glob_pattern(raw_path):
        matched = glob_module.glob(raw_path, recursive=True)
        files: list[str] = []
        warnings: list[str] = []
        for m in matched:
            p = Path(m)
            if p.is_file():
                if _is_binary_file(p):
                    warnings.append(f"Skipping binary file: {p.resolve()}")
                else:
                    files.append(str(p.resolve()))
            elif p.is_dir():
                sub_files, sub_warnings = _expand_directory(p, seen_real_dirs)
                files.extend(sub_files)
                warnings.extend(sub_warnings)
        return files, warnings

    # 2. 存在確認
    path = Path(raw_path)
    if not path.exists():
        raise FileResolutionError(
            f"File or directory not found: '{raw_path}'. "
            "Check the file path and try again."
        )

    resolved = path.resolve()

    # 3. ファイル → 解決済み絶対パス（バイナリはスキップ）
    if resolved.is_file():
        if _is_binary_file(resolved):
            return [], [f"Skipping binary file: {resolved}"]
        return [str(resolved)], []

    # 4. ディレクトリ → 再帰探索
    if resolved.is_dir():
        return _expand_directory(path, seen_real_dirs)

    # 5. 通常ファイルでもディレクトリでもない（ソケット、パイプ等）
    raise FileResolutionError(
        f"Unsupported file type: '{raw_path}' (not a regular file or directory). "
        "Only regular files and directories are supported."
    )


def resolve_files(raw_paths: tuple[str, ...]) -> ResolvedFiles | None:
    """入力パス群を具体的なファイルパスリストに展開する。

    Args:
        raw_paths: 未展開のパス文字列タプル。

    Returns:
        ResolvedFiles: 展開済みファイルパスと警告。空結果の場合は None。

    Raises:
        FileResolutionError: 指定パスが存在しない場合。
    """
    all_files: list[str] = []
    all_warnings: list[str] = []

    for raw_path in raw_paths:
        seen_real_dirs: set[Path] = set()
        files, warnings = _expand_single_path(raw_path, seen_real_dirs)
        all_files.extend(files)
        all_warnings.extend(warnings)

    unique_files = sorted(set(all_files))

    if not unique_files:
        return None

    return ResolvedFiles(
        paths=tuple(unique_files),
        warnings=tuple(all_warnings),
    )
