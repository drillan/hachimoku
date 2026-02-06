"""プロジェクト探索。

FR-CF-003: .hachimoku/ ディレクトリのカレント→親探索
FR-CF-005: pyproject.toml のカレント→親探索
FR-CF-006: ユーザーグローバル設定パス
"""

from __future__ import annotations

from pathlib import Path

_PROJECT_DIR_NAME: str = ".hachimoku"
_CONFIG_FILE_NAME: str = "config.toml"
_PYPROJECT_FILE_NAME: str = "pyproject.toml"


def find_project_root(start: Path) -> Path | None:
    """カレントディレクトリから親方向に .hachimoku/ を探索しプロジェクトルートを返す。

    FR-CF-003: ファイルシステムルートまで遡っても見つからない場合は None を返す。

    Args:
        start: 探索開始ディレクトリ。

    Returns:
        .hachimoku/ ディレクトリを含むパス。見つからなければ None。
    """
    current = start.resolve()
    while True:
        if (current / _PROJECT_DIR_NAME).is_dir():
            return current
        parent = current.parent
        if parent == current:
            return None
        current = parent


def find_config_file(start: Path) -> Path | None:
    """探索開始ディレクトリから .hachimoku/ を探索し config.toml のパスを返す。

    内部で find_project_root() を呼び出してプロジェクトルートを特定し、
    config.toml の存在チェックは行わない（パスのみ構築）。

    Args:
        start: 探索開始ディレクトリ。

    Returns:
        config.toml のフルパス。プロジェクトルートが見つからなければ None。
    """
    project_root = find_project_root(start)
    if project_root is None:
        return None
    return project_root / _PROJECT_DIR_NAME / _CONFIG_FILE_NAME


def find_pyproject_toml(start: Path) -> Path | None:
    """カレントディレクトリから親方向に pyproject.toml を探索する。

    FR-CF-005: pyproject.toml はカレントディレクトリから親ディレクトリへ遡って探索する。
    pyproject.toml が存在しない場合は None を返す。

    Args:
        start: 探索開始ディレクトリ。

    Returns:
        最初に見つかった pyproject.toml のフルパス。見つからなければ None。
    """
    current = start.resolve()
    while True:
        candidate = current / _PYPROJECT_FILE_NAME
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def get_user_config_path() -> Path:
    """ユーザーグローバル設定ファイルのパスを返す。

    FR-CF-006: ~/.config/hachimoku/config.toml を固定パスとして返す。

    Returns:
        ユーザーグローバル設定ファイルのパス（存在チェックは行わない）。
    """
    return Path.home() / ".config" / "hachimoku" / _CONFIG_FILE_NAME
