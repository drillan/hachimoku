"""FileResolver contract — file モードのファイル解決。

FR-CLI-009: ファイル・ディレクトリ・glob パターンの展開。
FR-CLI-011: max_files_per_review 超過時の確認プロンプト。
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from pydantic import Field

from hachimoku.models._base import HachimokuBaseModel


class ResolvedFiles(HachimokuBaseModel):
    """ファイル解決結果。

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


def resolve_files(raw_paths: tuple[str, ...]) -> ResolvedFiles:
    """入力パス群を具体的なファイルパスリストに展開する。

    処理内容:
    - 単一ファイル: そのまま追加（存在確認）
    - ディレクトリ: 再帰探索（pathlib.Path.rglob("*")）
    - glob パターン: glob.glob() で展開
    - 相対パス: cwd から解決
    - 絶対パス: そのまま使用
    - シンボリックリンク: resolve() で実体パス取得、循環参照検出

    Args:
        raw_paths: 未展開のパス文字列タプル。

    Returns:
        ResolvedFiles: 展開済みファイルパスと警告。

    Raises:
        FileResolutionError: 指定パスが存在しない場合。
    """
    ...


def _expand_single_path(
    raw_path: str,
    seen_real_dirs: set[Path],
) -> tuple[list[str], list[str]]:
    """単一パスを展開する。

    Args:
        raw_path: 未展開のパス文字列。
        seen_real_dirs: 既に探索した実体ディレクトリパスの集合（循環参照検出用）。

    Returns:
        (展開済みファイルパスリスト, 警告メッセージリスト)
    """
    ...


def _is_glob_pattern(path_str: str) -> bool:
    """パス文字列が glob パターンかどうかを判定する。

    glob 特殊文字: *, ?, [
    """
    ...
