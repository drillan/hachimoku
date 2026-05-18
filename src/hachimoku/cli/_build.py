"""build コマンド — TOML エージェント定義からサブエージェント .md と manifest.json を生成する。

LLM 不要の決定的処理。全エージェント定義を読み込み、
Claude Code サブエージェント形式に変換してファイルシステムへ書き出す。
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from hachimoku.agents import load_agents
from hachimoku.agents.manifest import MANIFEST_VERSION, Manifest
from hachimoku.agents.subagent import render_subagent_md, to_manifest_entry
from hachimoku.config import find_project_root
from hachimoku.models.exit_code import ExitCode


class BuildError(Exception):
    """出力ディレクトリへの書き込み失敗等の build コマンド固有エラー。"""


def run_build(
    output_dir: Path, custom_agents_dir: Path | None, hook_script: str
) -> int:
    """ビルド処理を実行し、生成した .md ファイル数を返す。

    全エージェント定義を読み込み、各エージェントの Claude Code サブエージェント .md を
    ``output_dir/agents/`` に書き出す。また全エージェントの ManifestEntry から
    Manifest を構築し ``output_dir/manifest.json`` に書き出す。

    Args:
        output_dir: 生成ファイルの出力先ルートディレクトリ。
        custom_agents_dir: カスタムエージェント定義のディレクトリパス。
            None の場合はビルトインのみ読み込む。
        hook_script: PreToolUse Bash フック用スクリプトの絶対パス。
            各エージェント ``.md`` の hooks ブロックに埋め込まれる。

    Returns:
        書き出した .md ファイル数。

    Raises:
        BuildError: ディレクトリ作成またはファイル書き込みに失敗した場合。
    """
    result = load_agents(custom_dir=custom_agents_dir)

    for error in result.errors:
        print(
            f"Warning: Failed to load agent '{error.source}': {error.message}",
            file=sys.stderr,
        )

    try:
        agents_dir = output_dir / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BuildError(
            f"Failed to create output directory '{agents_dir}': {exc}"
        ) from exc

    for agent in result.agents:
        md_path = agents_dir / f"{agent.name}.md"
        try:
            md_path.write_text(
                render_subagent_md(agent, hook_script=hook_script), encoding="utf-8"
            )
        except OSError as exc:
            raise BuildError(f"Failed to write '{md_path}': {exc}") from exc

    manifest = Manifest(
        version=MANIFEST_VERSION,
        entries=tuple(to_manifest_entry(agent) for agent in result.agents),
    )
    manifest_path = output_dir / "manifest.json"
    try:
        manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    except OSError as exc:
        raise BuildError(f"Failed to write '{manifest_path}': {exc}") from exc

    return len(result.agents)


def build_command(output_dir: Path, hook_script: str) -> None:
    """build サブコマンドのメインロジック。

    プロジェクトルートを検出してカスタムエージェントディレクトリを決定し、
    ``run_build`` を呼び出す。エラー時は stderr に出力して終了コード 3 で終了する。

    Args:
        output_dir: 生成ファイルの出力先ルートディレクトリ。
        hook_script: PreToolUse Bash フック用スクリプトの絶対パス。
    """
    project_root = find_project_root(Path.cwd())
    custom_agents_dir = (
        (project_root / ".hachimoku" / "agents") if project_root else None
    )

    try:
        count = run_build(output_dir, custom_agents_dir, hook_script)
    except BuildError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.EXECUTION_ERROR) from None

    print(
        f"Built {count} subagents and manifest.json under {output_dir}",
        file=sys.stderr,
    )
