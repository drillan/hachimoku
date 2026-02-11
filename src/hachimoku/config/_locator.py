"""プロジェクト探索。

FR-CF-003: .hachimoku/ ディレクトリのカレント→親探索
FR-CF-005: pyproject.toml のカレント→親探索
FR-CF-006: ユーザーグローバル設定パス
"""

from __future__ import annotations

import stat as stat_module
from collections.abc import Callable
from pathlib import Path

_PROJECT_DIR_NAME: str = ".hachimoku"
_CONFIG_FILE_NAME: str = "config.toml"
_PYPROJECT_FILE_NAME: str = "pyproject.toml"


def _find_ancestor(
    start: Path,
    target_name: str,
    check: Callable[[int], bool],
) -> Path | None:
    """start から親方向に target_name を探索し、最初にマッチした候補パスを返す。

    Args:
        start: 探索開始ディレクトリ。
        target_name: 探索対象の名前（例: ".hachimoku", "pyproject.toml"）。
        check: stat.st_mode に適用する種別チェック関数（例: stat.S_ISDIR）。

    Returns:
        最初にマッチした候補パス（start/…/target_name）。見つからなければ None。

    Raises:
        OSError: 探索パス上のアクセス権限エラー等。
    """
    current = start.resolve()
    while True:
        candidate = current / target_name
        try:
            st = candidate.stat()
        except FileNotFoundError:
            pass
        else:
            if check(st.st_mode):
                return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def find_project_root(start: Path) -> Path | None:
    """start ディレクトリから親方向に .hachimoku/ を探索しプロジェクトルートを返す。

    FR-CF-003: ファイルシステムルートまで遡っても見つからない場合は None を返す。

    Args:
        start: 探索開始ディレクトリ。

    Returns:
        .hachimoku/ ディレクトリを含むパス。見つからなければ None。

    Raises:
        OSError: 探索パス上のアクセス権限エラー等。
    """
    result = _find_ancestor(start, _PROJECT_DIR_NAME, stat_module.S_ISDIR)
    return result.parent if result is not None else None


def find_config_file(start: Path) -> Path | None:
    """start ディレクトリから .hachimoku/ を探索し config.toml のパスを返す。

    FR-CF-003: 内部で find_project_root() を呼び出してプロジェクトルートを特定し、
    config.toml の存在チェックは行わない（パスのみ構築）。

    Args:
        start: 探索開始ディレクトリ。

    Returns:
        config.toml のフルパス。プロジェクトルートが見つからなければ None。

    Raises:
        OSError: 探索パス上のアクセス権限エラー等。
    """
    project_root = find_project_root(start)
    if project_root is None:
        return None
    return project_root / _PROJECT_DIR_NAME / _CONFIG_FILE_NAME


def find_pyproject_toml(start: Path) -> Path | None:
    """start ディレクトリから親方向に pyproject.toml を探索する。

    FR-CF-005: pyproject.toml は start ディレクトリから親ディレクトリへ遡って探索する。
    pyproject.toml が存在しない場合は None を返す。

    Args:
        start: 探索開始ディレクトリ。

    Returns:
        最初に見つかった pyproject.toml のフルパス。見つからなければ None。

    Raises:
        OSError: 探索パス上のアクセス権限エラー等。
    """
    return _find_ancestor(start, _PYPROJECT_FILE_NAME, stat_module.S_ISREG)


def get_user_config_path() -> Path:
    """ユーザーグローバル設定ファイルのパスを返す。

    FR-CF-006: ~/.config/hachimoku/config.toml を固定パスとして返す。

    Returns:
        ユーザーグローバル設定ファイルのパス（存在チェックは行わない）。

    Raises:
        RuntimeError: ホームディレクトリを特定できない場合。
    """
    return Path.home() / ".config" / "hachimoku" / _CONFIG_FILE_NAME
