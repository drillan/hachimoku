"""CliApp — Typer アプリケーション定義（薄い CLI）。

レビュー実行は Claude Code プラグイン（オーケストレーター skill + サブエージェント）
へ移行した。本 CLI は非課金のローカル操作（init / agents 等）のみを担う。
"""

from __future__ import annotations

import importlib.metadata
import sys
from pathlib import Path
from typing import Annotated

import typer

from hachimoku.agents import LoadResult, load_agents, load_builtin_agents
from hachimoku.cli._init_handler import InitError, run_init
from hachimoku.cli._input_resolver import (
    DiffInput,
    FileInput,
    InputError,
    PRInput,
    resolve_input,
)
from hachimoku.cli._aggregate import aggregate_command
from hachimoku.cli._build import build_command
from hachimoku.cli._select import select_command
from hachimoku.config import find_project_root
from hachimoku.models.exit_code import ExitCode
from hachimoku.review.target import (
    CommitTarget,
    DiffTarget,
    FileTarget,
    PRTarget,
    ReviewTarget,
)

app = typer.Typer(
    name="8moku",
    help="Multi-agent code review — thin CLI (review runs in the Claude Code plugin).",
    add_completion=False,
    invoke_without_command=True,
)


def _version_callback(value: bool) -> None:
    """--version 指定時にバージョン番号を出力して終了する。"""
    if value:
        print(importlib.metadata.version("hachimoku"))
        raise typer.Exit()


def main() -> None:
    """CLI エントリポイント。8moku / hachimoku 両方から呼ばれる。"""
    app()


@app.callback()
def main_callback(
    ctx: typer.Context,
    version: Annotated[
        bool | None,
        typer.Option(
            "--version",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """hachimoku — multi-agent code review for Claude Code."""
    if ctx.invoked_subcommand is not None:
        return
    print(
        "hachimoku review is migrating to the Claude Code plugin model.\n"
        "  Design: docs/superpowers/specs/2026-05-18-skill-migration-design.md\n"
        "  Available subcommands: init, agents\n"
        "  Run '8moku --help' for details.",
        file=sys.stderr,
    )
    raise typer.Exit(code=ExitCode.SUCCESS)


@app.command()
def init(
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing files with defaults.")
    ] = False,
    upgrade: Annotated[
        bool,
        typer.Option(
            "--upgrade",
            help="Update built-in agent definitions using hash comparison.",
        ),
    ] = False,
) -> None:
    """Initialize .hachimoku/ directory with default configuration and agent definitions."""
    try:
        result = run_init(Path.cwd(), force=force, upgrade=upgrade)
    except InitError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.INPUT_ERROR) from None

    if upgrade:
        for path in result.created:
            print(f"  Added: {path}", file=sys.stderr)
        for path in result.updated:
            print(f"  Updated: {path}", file=sys.stderr)
        for path in result.skipped_customized:
            print(f"  Skipped (customized): {path}", file=sys.stderr)
        for path in result.skipped_up_to_date:
            print(f"  Skipped (up to date): {path}", file=sys.stderr)
        total_changed = len(result.created) + len(result.updated)
        total_skipped = len(result.skipped_customized) + len(result.skipped_up_to_date)
        if total_changed:
            print(
                f"\nUpgraded: {len(result.created)} added, "
                f"{len(result.updated)} updated, {total_skipped} skipped.",
                file=sys.stderr,
            )
        else:
            print(
                "\nAll built-in agents are up to date. Nothing to upgrade.",
                file=sys.stderr,
            )
    else:
        for path in result.created:
            print(f"  Created: {path}", file=sys.stderr)
        for path in result.skipped:
            print(f"  Skipped (already exists): {path}", file=sys.stderr)
        if result.created:
            print(
                f"\nInitialized .hachimoku/ "
                f"({len(result.created)} created, {len(result.skipped)} skipped).",
                file=sys.stderr,
            )
        else:
            print(
                "\nAll files already exist."
                " Use --force to overwrite, or --upgrade to add new agents only.",
                file=sys.stderr,
            )


@app.command()
def agents(
    name: Annotated[
        str | None, typer.Argument(help="Agent name for detailed info.")
    ] = None,
) -> None:
    """List or inspect agent definitions."""
    try:
        project_root = find_project_root(Path.cwd())
        custom_dir = (project_root / ".hachimoku" / "agents") if project_root else None
        result = load_agents(custom_dir=custom_dir)
        builtin_result = load_builtin_agents()
    except Exception as e:
        print(
            f"Error: Failed to load agent definitions: {e}\n"
            "Run '8moku init' to initialize the project, or check directory permissions.",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.EXECUTION_ERROR) from None

    builtin_names = {a.name for a in builtin_result.agents}
    for error in (*builtin_result.errors, *result.errors):
        print(
            f"Warning: Failed to load agent '{error.source}': {error.message}",
            file=sys.stderr,
        )

    if name is None:
        _print_agents_list(result, builtin_names)
    else:
        _print_agent_detail(name, result, builtin_names)


@app.command()
def build(
    output: Annotated[
        Path,
        typer.Option("--output", help="Output directory for generated subagents."),
    ] = Path(".hachimoku/build"),
) -> None:
    """Build Claude Code subagents and manifest.json from TOML agent definitions."""
    build_command(output)


@app.command()
def select(
    manifest: Annotated[
        Path,
        typer.Option("--manifest", help="Path to the manifest JSON file."),
    ],
    args: Annotated[
        list[str] | None,
        typer.Argument(help="PR number or file paths (omit for diff mode)."),
    ] = None,
    commit: Annotated[
        str | None,
        typer.Option("--commit", help="Commit ref or range (SHA or SHA1..SHA2)."),
    ] = None,
    base_branch: Annotated[
        str, typer.Option("--base-branch", help="Base branch for diff mode.")
    ] = "main",
) -> None:
    """Select review agents for a target and emit a dispatch plan (JSON)."""
    target = _resolve_select_target(args, commit, base_branch)
    select_command(target, manifest)


@app.command()
def aggregate(
    run_dir: Annotated[
        Path, typer.Option("--run-dir", help="Run directory created by 'select'.")
    ],
    manifest: Annotated[
        Path, typer.Option("--manifest", help="Path to the manifest JSON file.")
    ],
    args: Annotated[
        list[str] | None,
        typer.Argument(help="PR number or file paths (omit for diff mode)."),
    ] = None,
    commit: Annotated[
        str | None,
        typer.Option("--commit", help="Commit ref or range (SHA or SHA1..SHA2)."),
    ] = None,
    base_branch: Annotated[
        str, typer.Option("--base-branch", help="Base branch for diff mode.")
    ] = "main",
) -> None:
    """Aggregate subagent findings into a review report."""
    target = _resolve_select_target(args, commit, base_branch)
    aggregate_command(run_dir, manifest, target)


def _resolve_select_target(
    args: list[str] | None, commit: str | None, base_branch: str
) -> ReviewTarget:
    """select の引数からレビュー対象を構築する。

    commit モードは位置引数と排他。それ以外は resolve_input でモード判定する。
    """
    if commit is not None:
        if args:
            print(
                "Error: --commit cannot be used with positional arguments.",
                file=sys.stderr,
            )
            raise typer.Exit(code=ExitCode.INPUT_ERROR)
        if ".." in commit:
            from_ref, _, to_ref = commit.partition("..")
            if not from_ref or not to_ref:
                print(
                    f"Error: Invalid commit range: '{commit}'. Use SHA1..SHA2.",
                    file=sys.stderr,
                )
                raise typer.Exit(code=ExitCode.INPUT_ERROR)
            return CommitTarget(from_ref=from_ref, to_ref=to_ref)
        return CommitTarget(from_ref=commit, to_ref="HEAD")

    try:
        resolved = resolve_input(args or None)
    except InputError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.INPUT_ERROR) from None

    if isinstance(resolved, DiffInput):
        return DiffTarget(base_branch=base_branch)
    if isinstance(resolved, PRInput):
        return PRTarget(pr_number=resolved.pr_number)
    if isinstance(resolved, FileInput):
        return FileTarget(paths=resolved.paths)
    msg = f"Unexpected resolved input: {resolved!r}"
    raise AssertionError(msg)


_LIST_NAME_WIDTH = 28
_LIST_MODEL_WIDTH = 32
_LIST_PHASE_WIDTH = 8
_SYSTEM_PROMPT_SUMMARY_LINES = 3


def _print_agents_list(result: LoadResult, builtin_names: set[str]) -> None:
    """エージェント一覧をテーブル形式で stdout に表示する。"""
    header = (
        f"{'NAME':<{_LIST_NAME_WIDTH}}"
        f"{'MODEL':<{_LIST_MODEL_WIDTH}}"
        f"{'PHASE':<{_LIST_PHASE_WIDTH}}"
        f"{'SCHEMA'}"
    )
    print(header)
    print("-" * len(header))
    for agent in sorted(result.agents, key=lambda a: a.name):
        custom_marker = "  [custom]" if agent.name not in builtin_names else ""
        print(
            f"{agent.name:<{_LIST_NAME_WIDTH}}"
            f"{agent.model:<{_LIST_MODEL_WIDTH}}"
            f"{agent.phase.value:<{_LIST_PHASE_WIDTH}}"
            f"{agent.output_schema}{custom_marker}"
        )


def _print_agent_detail(name: str, result: LoadResult, builtin_names: set[str]) -> None:
    """エージェント詳細を stdout に表示する。見つからない場合は終了コード 4。"""
    agent = next((a for a in result.agents if a.name == name), None)
    if agent is None:
        available = ", ".join(sorted(a.name for a in result.agents))
        print(
            f"Error: Agent '{name}' not found.\nAvailable agents: {available}",
            file=sys.stderr,
        )
        raise typer.Exit(code=ExitCode.INPUT_ERROR)

    custom_marker = " [custom]" if name not in builtin_names else ""
    print(f"Name:             {agent.name}{custom_marker}")
    print(f"Description:      {agent.description}")
    print(f"Model:            {agent.model}")
    print(f"Phase:            {agent.phase.value}")
    print(f"Output Schema:    {agent.output_schema}")

    app_rule = agent.applicability
    if app_rule.always:
        print("Applicability:    always")
    else:
        if app_rule.file_patterns:
            print(f"File Patterns:    {', '.join(app_rule.file_patterns)}")
        if app_rule.content_patterns:
            print(f"Content Patterns: {', '.join(app_rule.content_patterns)}")

    if agent.allowed_tools:
        print(f"Allowed Tools:    {', '.join(agent.allowed_tools)}")
    else:
        print("Allowed Tools:    (none)")

    prompt_lines = agent.system_prompt.strip().splitlines()
    summary = "\n".join(prompt_lines[:_SYSTEM_PROMPT_SUMMARY_LINES])
    if len(prompt_lines) > _SYSTEM_PROMPT_SUMMARY_LINES:
        summary += "\n..."
    print(f"System Prompt:\n{summary}")
