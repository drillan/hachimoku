"""CliApp — Typer アプリケーション定義。

FR-CLI-001: デュアルコマンド名。
FR-CLI-002: 位置引数からの入力モード判定。
FR-CLI-013: --help 対応。
FR-CLI-014: エラーメッセージに解決方法を含む。
"""

from __future__ import annotations

import sys

import click
import typer
from typer.core import TyperGroup

from hachimoku.cli._input_resolver import InputError, resolve_input

_REVIEW_ARGS_KEY = "_review_args"


class _ReviewGroup(TyperGroup):
    """Typer Group のサブコマンド解決をオーバーライドし、位置引数との共存を実現する。

    Click の Group はサブコマンド名にマッチしない引数を UsageError にするが、
    hachimoku CLI ではサブコマンドでない引数を InputResolver に渡す必要がある。
    このクラスは resolve_command が失敗した場合に callback へ引数を渡す。
    """

    # click.Group.invoke の戻り値型が object であり、オーバーライドのため合わせている
    def invoke(self, ctx: click.Context) -> object:
        if not ctx._protected_args:
            if self.invoke_without_command:
                with ctx:
                    return click.Command.invoke(self, ctx)
            ctx.fail("Missing command.")

        args = [*ctx._protected_args, *ctx.args]
        ctx.args = []
        ctx._protected_args = []

        try:
            cmd_name, cmd, remaining = self.resolve_command(ctx, args)
        except click.UsageError as exc:
            if "No such command" not in str(exc):
                raise
            ctx.ensure_object(dict)
            ctx.obj[_REVIEW_ARGS_KEY] = args
            ctx.invoked_subcommand = None
            with ctx:
                return click.Command.invoke(self, ctx)

        if cmd is None:
            ctx.fail(f"Could not resolve command: {args}")
        with ctx:
            ctx.invoked_subcommand = cmd_name
            click.Command.invoke(self, ctx)
            sub_ctx = cmd.make_context(
                cmd_name,  # type: ignore[arg-type]
                remaining,
                parent=ctx,
            )
            with sub_ctx:
                return sub_ctx.command.invoke(sub_ctx)


app = typer.Typer(
    name="8moku",
    cls=_ReviewGroup,
    help="Multi-agent code review CLI tool.",
    add_completion=False,
    invoke_without_command=True,
)


def main() -> None:
    """CLI エントリポイント。pyproject.toml の [project.scripts] から呼び出される。

    8moku と hachimoku の両方で同一の関数が呼ばれる。
    """
    app()


@app.callback()
def review_callback(
    ctx: typer.Context,
) -> None:
    """Execute a code review (default command).

    Without arguments: diff mode (review current branch changes).
    With an integer: PR mode (review specified PR).
    With file paths: file mode (review specified files).
    """
    if ctx.invoked_subcommand is not None:
        return

    obj = ctx.ensure_object(dict)
    args: list[str] = obj.get(_REVIEW_ARGS_KEY, [])

    try:
        resolved = resolve_input(args or None)
    except InputError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=4) from None

    # US2 で接続予定: ReviewTarget 構築 → run_review() 呼び出し → レポート出力
    print(
        f"Review mode: {resolved.mode} (review execution not yet implemented)",
        file=sys.stderr,
    )


@app.command()
def config() -> None:
    """Manage configuration (not implemented in v0.1)."""
    print(
        "Error: 'config' subcommand is not implemented in v0.1. "
        "Edit .hachimoku/config.toml directly to configure settings.",
        file=sys.stderr,
    )
    raise typer.Exit(code=4)
