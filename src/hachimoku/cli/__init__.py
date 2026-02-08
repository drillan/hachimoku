"""hachimoku CLI パッケージ。

公開 API:
    app: Typer アプリケーションインスタンス。
    main: CLI エントリポイント。pyproject.toml から参照される。
"""

from hachimoku.cli._app import app, main

__all__ = ["app", "main"]
