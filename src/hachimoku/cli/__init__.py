"""hachimoku CLI パッケージ。

公開 API:
    app: Typer アプリケーションインスタンス。
    main: CLI エントリポイント。pyproject.toml から参照される。
"""

import typer

app = typer.Typer(
    name="8moku",
    help="Multi-agent code review CLI tool.",
    add_completion=False,
)


def main() -> None:
    """CLI エントリポイント。

    pyproject.toml の [project.scripts] から呼び出される。
    8moku と hachimoku の両方で同一の関数が呼ばれる。
    """
    app()


__all__ = ["app", "main"]
