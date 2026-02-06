"""TOML 設定ファイルローダー。

FR-CF-004: .hachimoku/config.toml の TOML パース
FR-CF-005: pyproject.toml の [tool.hachimoku] セクション読み込み
R-009: アクセスエラーは例外として送出
"""

from __future__ import annotations

import tomllib
from pathlib import Path


def load_toml_config(path: Path) -> dict[str, object]:
    """TOML 設定ファイルを読み込み辞書として返す。

    Args:
        path: TOML ファイルのパス。

    Returns:
        パースされた設定辞書。

    Raises:
        tomllib.TOMLDecodeError: TOML 構文エラーの場合。
        PermissionError: 読み取り権限がない場合。
        FileNotFoundError: ファイルが存在しない場合。
    """
    with path.open("rb") as f:
        return tomllib.load(f)  # type: ignore[return-value]


def load_pyproject_config(path: Path) -> dict[str, object] | None:
    """pyproject.toml から [tool.hachimoku] セクションを読み込む。

    FR-CF-005: [tool.hachimoku] セクションが存在しない場合は None を返す。

    Args:
        path: pyproject.toml のパス。

    Returns:
        [tool.hachimoku] セクションの辞書。セクションが存在しなければ None。

    Raises:
        tomllib.TOMLDecodeError: TOML 構文エラーの場合。
        PermissionError: 読み取り権限がない場合。
    """
    with path.open("rb") as f:
        data = tomllib.load(f)
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    hachimoku = tool.get("hachimoku")
    if not isinstance(hachimoku, dict):
        return None
    return hachimoku  # type: ignore[return-value]
