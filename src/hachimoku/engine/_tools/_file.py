"""file_read カテゴリのツール関数。

pydantic-ai エージェントがファイルシステムを読み取り専用で操作する。
"""

from __future__ import annotations

from pathlib import Path


def read_file(path: str) -> str:
    """ファイルの内容を読み込む。

    Args:
        path: ファイルパス。

    Returns:
        ファイルの内容（UTF-8）。

    Raises:
        FileNotFoundError: ファイルが存在しない場合。
        ValueError: ファイルが有効な UTF-8 テキストでない場合。
    """
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"File '{path}' is not a valid UTF-8 text file") from None


def list_directory(path: str, pattern: str | None = None) -> str:
    """ディレクトリ内のファイル一覧を取得する。

    Args:
        path: ディレクトリパス。
        pattern: glob パターン（例: "*.py"）。None の場合は全ファイル。

    Returns:
        ファイル名一覧を改行区切りで連結した文字列。

    Raises:
        NotADirectoryError: path がディレクトリでない場合。
    """
    dir_path = Path(path)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"{path} is not a directory")

    entries = dir_path.glob(pattern or "*")
    file_names = sorted(entry.name for entry in entries if entry.is_file())
    return "\n".join(file_names)
