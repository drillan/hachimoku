"""select コマンド — レビュー対象から起動エージェントを決定する。

LLM を用いず、Manifest の applicability ルールで決定的に起動対象を選び、
run_dir を作成してディスパッチプラン JSON を stdout に出力する。
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import typer
from pydantic import Field, ValidationError

from hachimoku.agents.applicability import select_agent_names
from hachimoku.agents.manifest import Manifest
from hachimoku.agents.models import Phase
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.exit_code import ExitCode
from hachimoku.review.changeset import ChangeSetError, compute_changeset
from hachimoku.review.target import ReviewTarget


class DispatchPlan(HachimokuBaseModel):
    """select コマンドの出力。オーケストレーターが消費する。

    Attributes:
        run_dir: サブエージェント findings の出力先ディレクトリ（絶対パス）。
        phases: フェーズ別の起動エージェント名リスト。
    """

    run_dir: str = Field(min_length=1)
    phases: dict[Phase, list[str]]


class SelectError(Exception):
    """select コマンドのエラー。"""


def load_manifest(manifest_path: Path) -> Manifest:
    """Manifest JSON を読み込む。

    Raises:
        SelectError: ファイルが存在しない・JSON 不正・スキーマ不適合の場合。
    """
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SelectError(
            f"Cannot read manifest: {manifest_path}: {exc}\n"
            "Run '8moku build' to generate the manifest."
        ) from exc
    try:
        return Manifest.model_validate_json(raw)
    except ValidationError as exc:
        raise SelectError(f"Invalid manifest at {manifest_path}: {exc}") from exc


def run_select(target: ReviewTarget, manifest_path: Path) -> DispatchPlan:
    """select の中核処理。ChangeSet 計算 → applicability 評価 → run_dir 作成。

    Raises:
        SelectError: manifest 読み込み失敗時。
        ChangeSetError: 変更内容計算失敗時。
    """
    manifest = load_manifest(manifest_path)
    changeset = compute_changeset(target)
    phases = select_agent_names(
        manifest, changeset.changed_basenames, changeset.content
    )
    run_dir = tempfile.mkdtemp(prefix="hachimoku-run-")
    return DispatchPlan(run_dir=run_dir, phases=phases)


def select_command(target: ReviewTarget, manifest_path: Path) -> None:
    """select サブコマンドのエントリ。DispatchPlan を JSON で stdout 出力する。

    終了コード: 0=成功, 3=実行エラー, 4=入力エラー。
    """
    try:
        plan = run_select(target, manifest_path)
    except SelectError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.INPUT_ERROR) from None
    except ChangeSetError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.EXECUTION_ERROR) from None
    print(plan.model_dump_json(indent=2))
