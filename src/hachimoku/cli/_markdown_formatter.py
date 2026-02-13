"""ReviewReport の Markdown フォーマッタ。

Issue #200: デフォルト出力形式を markdown にするための実装。
007-output-format 仕様策定時に適切な配置へリファクタリング予定。
"""

from __future__ import annotations

from itertools import groupby

from hachimoku.agents.models import LoadError
from hachimoku.models.agent_result import (
    AgentError,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
    CostInfo,
)
from hachimoku.models.report import (
    AggregatedReport,
    ReviewReport,
    ReviewSummary,
)
from hachimoku.models.review import ReviewIssue
from hachimoku.models.severity import SEVERITY_ORDER


def format_markdown(report: ReviewReport) -> str:
    """ReviewReport を Markdown 文字列に変換する。

    Args:
        report: 変換対象のレビューレポート。

    Returns:
        Markdown 形式の文字列。
    """
    sections: list[str] = [
        "# Review Report",
        _format_summary(report.summary),
    ]

    issues = _collect_issues(report)
    issues_section = _format_issues(issues)
    if issues_section:
        sections.append(issues_section)

    if report.aggregated is not None:
        sections.append(_format_aggregated(report.aggregated))

    sections.append(_format_agent_results(report))

    load_errors_section = _format_load_errors(report.load_errors)
    if load_errors_section:
        sections.append(load_errors_section)

    if report.aggregation_error is not None:
        sections.append(_format_aggregation_error(report.aggregation_error))

    return "\n\n".join(sections) + "\n"


# ── Summary ──────────────────────────────────────────────


def _format_summary(summary: ReviewSummary) -> str:
    severity_display = summary.max_severity.value if summary.max_severity else "-"
    elapsed_display = f"{summary.total_elapsed_time:.1f}s"

    rows = [
        f"| Total Issues | {summary.total_issues} |",
        f"| Max Severity | {severity_display} |",
        f"| Elapsed Time | {elapsed_display} |",
    ]

    if summary.total_cost is not None:
        rows.append(_format_cost_row(summary.total_cost))

    table = "\n".join(rows)
    return f"## Summary\n\n| Metric | Value |\n|--------|-------|\n{table}"


def _format_cost_row(cost: CostInfo) -> str:
    cost_display = f"${cost.total_cost}" if cost.total_cost is not None else "-"
    return (
        f"| Total Cost | {cost_display} "
        f"(input: {cost.input_tokens}, output: {cost.output_tokens}) |"
    )


# ── Issues ───────────────────────────────────────────────


def _collect_issues(report: ReviewReport) -> list[ReviewIssue]:
    """AgentSuccess と AgentTruncated から issues を収集する。"""
    issues: list[ReviewIssue] = []
    for agent_result in report.results:
        if isinstance(agent_result, (AgentSuccess, AgentTruncated)):
            issues.extend(agent_result.issues)
    return issues


def _format_issues(issues: list[ReviewIssue]) -> str:
    """Issues を severity 降順でグループ化して Markdown に変換する。

    Returns:
        Markdown 文字列。issues が空の場合は空文字列。
    """
    if not issues:
        return ""

    sorted_issues = sorted(
        issues,
        key=lambda i: SEVERITY_ORDER[i.severity.value],
        reverse=True,
    )

    parts: list[str] = ["## Issues"]

    for severity, group in groupby(sorted_issues, key=lambda i: i.severity):
        group_list = list(group)
        parts.append(f"\n### {severity.value} ({len(group_list)})")
        for idx, issue in enumerate(group_list, 1):
            parts.append(_format_single_issue(idx, issue))

    return "\n".join(parts)


def _format_single_issue(index: int, issue: ReviewIssue) -> str:
    lines: list[str] = [
        f"\n#### {index}. {issue.description}\n",
        f"- **Agent**: {issue.agent_name}",
    ]
    if issue.location is not None:
        lines.append(
            f"- **Location**: `{issue.location.file_path}:{issue.location.line_number}`"
        )
    if issue.category is not None:
        lines.append(f"- **Category**: {issue.category}")
    if issue.suggestion is not None:
        lines.append(f"- **Suggestion**: {issue.suggestion}")
    return "\n".join(lines)


# ── Agent Results ────────────────────────────────────────


def _format_agent_results(report: ReviewReport) -> str:
    rows: list[str] = []
    for agent_result in report.results:
        rows.append(_format_agent_result_row(agent_result))

    table_rows = "\n".join(rows)
    return (
        "## Agent Results\n\n"
        "| Agent | Status | Issues | Time |\n"
        "|-------|--------|--------|------|\n"
        f"{table_rows}"
    )


def _format_agent_result_row(
    agent_result: AgentSuccess | AgentError | AgentTimeout | AgentTruncated,
) -> str:
    match agent_result:
        case AgentSuccess():
            issue_count = str(len(agent_result.issues))
            time_display = f"{agent_result.elapsed_time:.1f}s"
            return f"| {agent_result.agent_name} | success | {issue_count} | {time_display} |"
        case AgentTruncated():
            issue_count = str(len(agent_result.issues))
            time_display = f"{agent_result.elapsed_time:.1f}s"
            return f"| {agent_result.agent_name} | truncated | {issue_count} | {time_display} |"
        case AgentError():
            return f"| {agent_result.agent_name} | error | - | - |"
        case AgentTimeout():
            return f"| {agent_result.agent_name} | timeout ({agent_result.timeout_seconds:.0f}s) | - | - |"


# ── Aggregated Analysis ─────────────────────────────────


def _format_aggregated(aggregated: AggregatedReport) -> str:
    parts: list[str] = ["## Aggregated Analysis"]

    if aggregated.issues:
        issue_lines = "\n".join(
            f"- [{i.severity.value}] {i.description}" for i in aggregated.issues
        )
        parts.append(f"\n### Issues\n\n{issue_lines}")

    if aggregated.strengths:
        strength_lines = "\n".join(f"- {s}" for s in aggregated.strengths)
        parts.append(f"\n### Strengths\n\n{strength_lines}")

    if aggregated.recommended_actions:
        action_lines = "\n".join(
            f"{idx}. **[{a.priority.value}]** {a.description}"
            for idx, a in enumerate(aggregated.recommended_actions, 1)
        )
        parts.append(f"\n### Recommended Actions\n\n{action_lines}")

    if aggregated.agent_failures:
        failure_lines = "\n".join(f"- {f}" for f in aggregated.agent_failures)
        parts.append(f"\n### Agent Failures\n\n{failure_lines}")

    return "\n".join(parts)


# ── Load Errors ──────────────────────────────────────────


def _format_load_errors(load_errors: tuple[LoadError, ...]) -> str:
    """Returns:
    Markdown 文字列。load_errors が空の場合は空文字列。
    """
    if not load_errors:
        return ""

    lines = "\n".join(f"- **{e.source}**: {e.message}" for e in load_errors)
    return f"## Load Errors\n\n{lines}"


# ── Aggregation Error ────────────────────────────────────


def _format_aggregation_error(error: str) -> str:
    return f"## Aggregation Error\n\n{error}"
