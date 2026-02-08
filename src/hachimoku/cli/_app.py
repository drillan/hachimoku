"""CliApp — Typer アプリケーション定義。

FR-CLI-001: デュアルコマンド名。
FR-CLI-002: 位置引数からの入力モード判定。
FR-CLI-003: 終了コード。
FR-CLI-004: stdout/stderr ストリーム分離。
FR-CLI-006: CLI オプション対応表。
FR-CLI-013: --help 対応。
FR-CLI-014: エラーメッセージに解決方法を含む。
"""

from __future__ import annotations

import asyncio
import sys
from typing import Annotated

import click
import typer
from typer.core import TyperGroup

from hachimoku.cli._input_resolver import (
    DiffInput,
    InputError,
    PRInput,
    ResolvedInput,
    resolve_input,
)
from hachimoku.config import resolve_config
from hachimoku.engine import run_review
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models.config import HachimokuConfig, OutputFormat
from hachimoku.models.exit_code import ExitCode
from hachimoku.models.report import ReviewReport

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
    # 設定上書きオプション（FR-CLI-006）
    model: Annotated[str | None, typer.Option(help="LLM model name.")] = None,
    timeout: Annotated[
        int | None, typer.Option(help="Timeout in seconds (positive integer).", min=1)
    ] = None,
    max_turns: Annotated[
        int | None,
        typer.Option("--max-turns", help="Max agent turns (positive integer).", min=1),
    ] = None,
    parallel: Annotated[
        bool | None,
        typer.Option(
            "--parallel/--no-parallel", help="Enable/disable parallel execution."
        ),
    ] = None,
    base_branch: Annotated[
        str | None, typer.Option("--base-branch", help="Base branch for diff mode.")
    ] = None,
    format: Annotated[
        OutputFormat | None,
        typer.Option("--format", help="Output format: markdown or json."),
    ] = None,
    save_reviews: Annotated[
        bool | None,
        typer.Option("--save-reviews/--no-save-reviews", help="Save review results."),
    ] = None,
    show_cost: Annotated[
        bool | None,
        typer.Option("--show-cost/--no-show-cost", help="Show cost information."),
    ] = None,
    max_files: Annotated[
        int | None,
        typer.Option(
            "--max-files", help="Max files per review (positive integer).", min=1
        ),
    ] = None,
    # per-invocation オプション
    issue: Annotated[
        int | None,
        typer.Option("--issue", help="GitHub Issue number for context.", min=1),
    ] = None,
    no_confirm: Annotated[
        bool, typer.Option("--no-confirm", help="Skip confirmation prompts.")
    ] = False,
) -> None:
    """Execute a code review (default command).

    Without arguments: diff mode (review current branch changes).
    With an integer: PR mode (review specified PR).
    With file paths: file mode (review specified files).
    """
    if ctx.invoked_subcommand is not None:
        return

    # 1. 入力モード判定
    obj = ctx.ensure_object(dict)
    raw_args: list[str] = obj.get(_REVIEW_ARGS_KEY, [])

    try:
        resolved = resolve_input(raw_args or None)
    except InputError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.INPUT_ERROR) from None

    # 2. config_overrides 辞書構築
    config_overrides = _build_config_overrides(
        model=model,
        timeout=timeout,
        max_turns=max_turns,
        parallel=parallel,
        base_branch=base_branch,
        format=format,
        save_reviews=save_reviews,
        show_cost=show_cost,
        max_files=max_files,
    )

    # 3. config 解決（DiffTarget の base_branch 取得用）
    config = resolve_config(cli_overrides=config_overrides)

    # 4. ReviewTarget 構築
    target = _build_target(resolved, config, issue)

    # 5. run_review() 呼び出し
    try:
        result = asyncio.run(
            run_review(target=target, config_overrides=config_overrides)
        )
    except Exception as e:
        print(f"Error: Review execution failed: {e}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.EXECUTION_ERROR) from None

    # 6. stdout にレポート出力
    report_text = _format_report(result.report, config.output_format)
    print(report_text)

    # 7. 終了コード
    raise typer.Exit(code=result.exit_code)


@app.command()
def config() -> None:
    """Manage configuration (not implemented in v0.1)."""
    print(
        "Error: 'config' subcommand is not implemented in v0.1. "
        "Edit .hachimoku/config.toml directly to configure settings.",
        file=sys.stderr,
    )
    raise typer.Exit(code=ExitCode.INPUT_ERROR)


def _build_config_overrides(
    *,
    model: str | None,
    timeout: int | None,
    max_turns: int | None,
    parallel: bool | None,
    base_branch: str | None,
    format: OutputFormat | None,
    save_reviews: bool | None,
    show_cost: bool | None,
    max_files: int | None,
) -> dict[str, object]:
    """CLI オプションから config_overrides 辞書を構築する。

    None 値は「未指定」として除外する。
    CLI パラメータ名と config キー名の対応:
        format → output_format
        max_files → max_files_per_review
    """
    raw: dict[str, object] = {
        "model": model,
        "timeout": timeout,
        "max_turns": max_turns,
        "parallel": parallel,
        "base_branch": base_branch,
        "output_format": format,
        "save_reviews": save_reviews,
        "show_cost": show_cost,
        "max_files_per_review": max_files,
    }
    return {k: v for k, v in raw.items() if v is not None}


def _build_target(
    resolved: ResolvedInput,
    config: HachimokuConfig,
    issue: int | None,
) -> DiffTarget | PRTarget | FileTarget:
    """ResolvedInput と config から ReviewTarget を構築する。"""
    if isinstance(resolved, DiffInput):
        return DiffTarget(base_branch=config.base_branch, issue_number=issue)
    if isinstance(resolved, PRInput):
        return PRTarget(pr_number=resolved.pr_number, issue_number=issue)
    # FileInput
    return FileTarget(paths=resolved.paths, issue_number=issue)


def _format_report(report: ReviewReport, output_format: OutputFormat) -> str:
    """レポートを文字列に変換する（暫定実装）。

    007-output-format で正式なフォーマッターに置き換え予定。
    """
    if output_format == OutputFormat.JSON:
        return report.model_dump_json(indent=2)
    # MARKDOWN（暫定: JSON ダンプで代替）
    return report.model_dump_json(indent=2)
