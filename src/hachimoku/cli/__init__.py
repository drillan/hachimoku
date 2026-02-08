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


@app.callback(invoke_without_command=True)
def _review_callback(ctx: typer.Context) -> None:
    """マルチエージェントコードレビューを実行する。"""
    if ctx.invoked_subcommand is None:
        ctx.get_help()


def main() -> None:
    """CLI エントリポイント。

    pyproject.toml の [project.scripts] から呼び出される。
    8moku と hachimoku の両方で同一の関数が呼ばれる。
    """
    app()


__all__ = ["app", "main"]
