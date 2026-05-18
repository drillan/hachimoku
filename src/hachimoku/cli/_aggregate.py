"""aggregate コマンド — サブエージェント findings を集約してレビューレポートを生成する。

LLM を用いない決定的処理。破損入力は AgentError として明示的に可視化する。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from pydantic import ValidationError

from hachimoku.cli._history_writer import (
    GitInfoError,
    HistoryWriteError,
    save_review_history,
)
from hachimoku.cli._markdown_formatter import format_markdown
from hachimoku.cli._select import DispatchPlan, SelectError, load_manifest
from hachimoku.config import find_project_root
from hachimoku.models.agent_result import AgentError, AgentResult, AgentSuccess
from hachimoku.models.exit_code import ExitCode
from hachimoku.models.report import ReviewReport, ReviewSummary
from hachimoku.models.schemas import SchemaNotFoundError, get_schema
from hachimoku.models.severity import SEVERITY_ORDER, Severity, determine_exit_code
from hachimoku.review.target import ReviewTarget


class AggregateError(Exception):
    """aggregate コマンドのエラー。run_dir / dispatch-plan 不在等。"""


def load_dispatch_plan(run_dir: Path) -> DispatchPlan:
    """run_dir から dispatch-plan.json を読み込み DispatchPlan に検証する。

    Args:
        run_dir: サブエージェント findings の格納ディレクトリ。

    Returns:
        検証済み DispatchPlan。

    Raises:
        AggregateError: ファイル不在・JSON 不正・スキーマ不適合の場合。
    """
    plan_path = run_dir / "dispatch-plan.json"
    try:
        raw = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AggregateError(f"Cannot read dispatch-plan: {plan_path}: {exc}") from exc
    try:
        return DispatchPlan.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        raise AggregateError(f"Invalid dispatch-plan at {plan_path}: {exc}") from exc


def _expected_agents(plan: DispatchPlan) -> list[str]:
    """DispatchPlan の全フェーズからエージェント名の一覧を返す。

    Args:
        plan: 検証済み DispatchPlan。

    Returns:
        全フェーズの起動予定エージェント名リスト（順序: early → main → final）。
    """
    names: list[str] = []
    for agents in plan.phases.values():
        names.extend(agents)
    return names


def _load_one(run_dir: Path, name: str, schema_name: str) -> AgentResult:
    """1エージェント分の findings JSON を読み込み AgentResult に変換する。

    Args:
        run_dir: サブエージェント findings の格納ディレクトリ。
        name: エージェント名。
        schema_name: SCHEMA_REGISTRY のキー（出力スキーマ名）。

    Returns:
        AgentSuccess（成功）または AgentError（ファイル不在・JSON 不正・スキーマ不適合）。
    """
    findings_path = run_dir / f"{name}.json"
    try:
        raw = findings_path.read_text(encoding="utf-8")
    except OSError:
        return AgentError(agent_name=name, error_message="no output")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return AgentError(
            agent_name=name,
            error_message=f"JSON decode error: {exc}",
        )

    try:
        schema_cls = get_schema(schema_name)
    except SchemaNotFoundError as exc:
        return AgentError(
            agent_name=name,
            error_message=f"schema not found: {exc}",
        )

    try:
        parsed = schema_cls.model_validate(data)
    except ValidationError as exc:
        return AgentError(
            agent_name=name,
            error_message=f"schema validation error: {exc}",
        )

    return AgentSuccess(
        agent_name=name,
        issues=parsed.issues,
        overall_score=parsed.overall_score,
    )


def build_report(results: list[AgentResult]) -> ReviewReport:
    """エージェント結果リストから ReviewReport を構築する。

    Args:
        results: エージェント結果のリスト（AgentSuccess / AgentError の混在可）。

    Returns:
        集約済み ReviewReport。
    """
    successes = [r for r in results if isinstance(r, AgentSuccess)]

    total_issues = sum(len(s.issues) for s in successes)

    max_severity: Severity | None = None
    if total_issues > 0:
        all_issues = [issue for s in successes for issue in s.issues]
        max_severity = max(
            all_issues, key=lambda i: SEVERITY_ORDER[i.severity.value]
        ).severity

    overall_score: float | None = None
    if successes:
        scores = [s.overall_score for s in successes if s.overall_score is not None]
        if scores:
            overall_score = sum(scores) / len(scores)

    summary = ReviewSummary(
        total_issues=total_issues,
        max_severity=max_severity,
        total_elapsed_time=None,
        overall_score=overall_score,
    )
    return ReviewReport(results=results, summary=summary, load_errors=())


def exit_code_for(summary: ReviewSummary) -> ExitCode:
    """サマリーの最大重大度から終了コードを決定する。

    重大度 → 終了コードのマッピングは ``severity.determine_exit_code`` を
    単一の正として委譲する（DRY）。

    Args:
        summary: レビューサマリー。

    Returns:
        ExitCode.CRITICAL（Critical）、ExitCode.IMPORTANT（Important）、
        ExitCode.SUCCESS（Suggestion/Nitpick/None）のいずれか。
    """
    return determine_exit_code(summary.max_severity)


def run_aggregate(run_dir: Path, manifest_path: Path) -> ReviewReport:
    """aggregate の中核処理。dispatch-plan と manifest を読み findings を集約する。

    Args:
        run_dir: サブエージェント findings の格納ディレクトリ。
        manifest_path: manifest JSON ファイルのパス。

    Returns:
        集約済み ReviewReport。

    Raises:
        AggregateError: run_dir 不在・dispatch-plan 読み込み失敗の場合。
        SelectError: manifest 読み込み失敗の場合。
    """
    if not run_dir.exists():
        raise AggregateError(
            f"run_dir does not exist: {run_dir}\n"
            "Run '8moku select' to create a run directory."
        )

    plan = load_dispatch_plan(run_dir)

    try:
        manifest = load_manifest(manifest_path)
    except SelectError as exc:
        raise AggregateError(str(exc)) from exc

    schema_map: dict[str, str] = {
        entry.name: entry.output_schema for entry in manifest.entries
    }

    agent_names = _expected_agents(plan)
    results: list[AgentResult] = []
    for name in agent_names:
        if name not in schema_map:
            results.append(
                AgentError(agent_name=name, error_message="agent not in manifest")
            )
        else:
            results.append(_load_one(run_dir, name, schema_map[name]))

    return build_report(results)


def aggregate_command(
    run_dir: Path,
    manifest_path: Path,
    target: ReviewTarget,
) -> None:
    """aggregate サブコマンドのエントリ。

    findings を集約し Markdown レポートを stdout に出力する。
    JSONL 履歴は .hachimoku/reviews/ に追記する。

    Args:
        run_dir: サブエージェント findings の格納ディレクトリ。
        manifest_path: manifest JSON ファイルのパス。
        target: レビュー対象（履歴記録用）。

    Raises:
        typer.Exit: 終了コードとともに終了する。
    """
    try:
        report = run_aggregate(run_dir, manifest_path)
    except AggregateError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=ExitCode.EXECUTION_ERROR) from None

    project_root = find_project_root(Path.cwd())
    if project_root is None:
        print(
            "Warning: .hachimoku/ not found; skipping review history.",
            file=sys.stderr,
        )
    else:
        reviews_dir = project_root / ".hachimoku" / "reviews"
        try:
            save_review_history(reviews_dir, target, report)
        except (HistoryWriteError, GitInfoError) as exc:
            print(f"Warning: Failed to save review history: {exc}", file=sys.stderr)

    print(format_markdown(report))
    raise typer.Exit(code=exit_code_for(report.summary))
