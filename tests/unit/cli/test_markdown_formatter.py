"""Markdown フォーマッタのユニットテスト。

format_markdown(report) の各セクション出力を検証する。
"""

from __future__ import annotations


from hachimoku.agents.models import LoadError
from hachimoku.cli._markdown_formatter import format_markdown
from hachimoku.models.agent_result import (
    AgentError,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
    CostInfo,
)
from hachimoku.models.report import (
    AggregatedReport,
    Priority,
    RecommendedAction,
    ReviewReport,
    ReviewSummary,
)
from hachimoku.models.review import FileLocation, ReviewIssue
from hachimoku.models.severity import Severity


# ── ヘルパー ──────────────────────────────────────────────


def _make_issue(
    *,
    agent_name: str = "test-agent",
    severity: Severity = Severity.IMPORTANT,
    description: str = "Test issue description",
    file_path: str | None = None,
    line_number: int = 1,
    suggestion: str | None = None,
    category: str | None = None,
) -> ReviewIssue:
    location = (
        FileLocation(file_path=file_path, line_number=line_number)
        if file_path
        else None
    )
    return ReviewIssue(
        agent_name=agent_name,
        severity=severity,
        description=description,
        location=location,
        suggestion=suggestion,
        category=category,
    )


def _make_success(
    *,
    agent_name: str = "test-agent",
    issues: list[ReviewIssue] | None = None,
    elapsed_time: float = 1.0,
    cost: CostInfo | None = None,
) -> AgentSuccess:
    return AgentSuccess(
        agent_name=agent_name,
        issues=issues or [],
        elapsed_time=elapsed_time,
        cost=cost,
    )


def _make_report(
    *,
    results: list[AgentSuccess | AgentError | AgentTimeout | AgentTruncated]
    | None = None,
    total_issues: int = 0,
    max_severity: Severity | None = None,
    total_elapsed_time: float = 0.0,
    total_cost: CostInfo | None = None,
    load_errors: tuple[LoadError, ...] = (),
    aggregated: AggregatedReport | None = None,
    aggregation_error: str | None = None,
) -> ReviewReport:
    return ReviewReport(
        results=results or [],
        summary=ReviewSummary(
            total_issues=total_issues,
            max_severity=max_severity,
            total_elapsed_time=total_elapsed_time,
            total_cost=total_cost,
        ),
        load_errors=load_errors,
        aggregated=aggregated,
        aggregation_error=aggregation_error,
    )


# ── Summary セクション ───────────────────────────────────


class TestSummarySection:
    """Summary テーブルの出力検証。"""

    def test_contains_total_issues(self) -> None:
        report = _make_report(total_issues=0)
        result = format_markdown(report)
        assert "| Total Issues | 0 |" in result

    def test_contains_max_severity(self) -> None:
        issue = _make_issue(severity=Severity.CRITICAL)
        success = _make_success(issues=[issue])
        report = _make_report(
            results=[success], total_issues=1, max_severity=Severity.CRITICAL
        )
        result = format_markdown(report)
        assert "| Max Severity | Critical |" in result

    def test_max_severity_none_shows_dash(self) -> None:
        report = _make_report(total_issues=0, max_severity=None)
        result = format_markdown(report)
        assert "| Max Severity | - |" in result

    def test_contains_elapsed_time(self) -> None:
        report = _make_report(total_elapsed_time=12.345)
        result = format_markdown(report)
        assert "| Elapsed Time | 12.3s |" in result

    def test_contains_cost_when_present(self) -> None:
        cost = CostInfo(input_tokens=1000, output_tokens=500, total_cost=0.05)
        report = _make_report(total_cost=cost)
        result = format_markdown(report)
        assert "Total Cost" in result
        assert "$0.0500" in result
        assert "1000" in result
        assert "500" in result

    def test_omits_cost_when_none(self) -> None:
        report = _make_report(total_cost=None)
        result = format_markdown(report)
        assert "Total Cost" not in result


# ── Issues セクション ────────────────────────────────────


class TestIssuesSection:
    """Issues セクションの出力検証。"""

    def test_issues_grouped_by_severity(self) -> None:
        critical = _make_issue(severity=Severity.CRITICAL, description="Critical bug")
        important = _make_issue(
            severity=Severity.IMPORTANT, description="Important issue"
        )
        success = _make_success(issues=[critical, important])
        report = _make_report(
            results=[success], total_issues=2, max_severity=Severity.CRITICAL
        )
        result = format_markdown(report)
        assert "### Critical (1)" in result
        assert "### Important (1)" in result

    def test_issues_severity_order_descending(self) -> None:
        """Critical → Important → Suggestion → Nitpick の降順で出力される。"""
        nitpick = _make_issue(severity=Severity.NITPICK, description="Nitpick note")
        critical = _make_issue(severity=Severity.CRITICAL, description="Critical bug")
        success = _make_success(issues=[nitpick, critical])
        report = _make_report(
            results=[success], total_issues=2, max_severity=Severity.CRITICAL
        )
        result = format_markdown(report)
        critical_pos = result.index("### Critical")
        nitpick_pos = result.index("### Nitpick")
        assert critical_pos < nitpick_pos

    def test_issue_contains_description(self) -> None:
        issue = _make_issue(description="Use parameterized queries")
        success = _make_success(issues=[issue])
        report = _make_report(
            results=[success], total_issues=1, max_severity=Severity.IMPORTANT
        )
        result = format_markdown(report)
        assert "Use parameterized queries" in result

    def test_issue_contains_agent_name(self) -> None:
        issue = _make_issue(agent_name="security-reviewer")
        success = _make_success(issues=[issue])
        report = _make_report(
            results=[success], total_issues=1, max_severity=Severity.IMPORTANT
        )
        result = format_markdown(report)
        assert "security-reviewer" in result

    def test_issue_contains_location_when_present(self) -> None:
        issue = _make_issue(file_path="src/db.py", line_number=42)
        success = _make_success(issues=[issue])
        report = _make_report(
            results=[success], total_issues=1, max_severity=Severity.IMPORTANT
        )
        result = format_markdown(report)
        assert "`src/db.py:42`" in result

    def test_issue_omits_location_when_none(self) -> None:
        issue = _make_issue(file_path=None)
        success = _make_success(issues=[issue])
        report = _make_report(
            results=[success], total_issues=1, max_severity=Severity.IMPORTANT
        )
        result = format_markdown(report)
        assert "**Location**" not in result

    def test_issue_contains_suggestion_when_present(self) -> None:
        issue = _make_issue(suggestion="Use dataclass instead")
        success = _make_success(issues=[issue])
        report = _make_report(
            results=[success], total_issues=1, max_severity=Severity.IMPORTANT
        )
        result = format_markdown(report)
        assert "Use dataclass instead" in result

    def test_issue_omits_suggestion_when_none(self) -> None:
        issue = _make_issue(suggestion=None)
        success = _make_success(issues=[issue])
        report = _make_report(
            results=[success], total_issues=1, max_severity=Severity.IMPORTANT
        )
        result = format_markdown(report)
        assert "**Suggestion**" not in result

    def test_issue_contains_category_when_present(self) -> None:
        issue = _make_issue(category="security")
        success = _make_success(issues=[issue])
        report = _make_report(
            results=[success], total_issues=1, max_severity=Severity.IMPORTANT
        )
        result = format_markdown(report)
        assert "security" in result

    def test_no_issues_section_when_empty(self) -> None:
        report = _make_report(total_issues=0)
        result = format_markdown(report)
        assert "## Issues" not in result

    def test_issues_from_truncated_agent(self) -> None:
        """AgentTruncated の issues も Issues セクションに含まれる。"""
        issue = _make_issue(description="Found by truncated agent")
        truncated = AgentTruncated(
            agent_name="truncated-agent",
            issues=[issue],
            elapsed_time=5.0,
            turns_consumed=10,
        )
        report = _make_report(
            results=[truncated], total_issues=1, max_severity=Severity.IMPORTANT
        )
        result = format_markdown(report)
        assert "Found by truncated agent" in result


# ── Agent Results セクション ─────────────────────────────


class TestAgentResultsSection:
    """Agent Results テーブルの出力検証。"""

    def test_agent_success_shown(self) -> None:
        success = _make_success(agent_name="code-reviewer", elapsed_time=5.2)
        report = _make_report(results=[success])
        result = format_markdown(report)
        assert "code-reviewer" in result
        assert "success" in result
        assert "5.2s" in result

    def test_agent_error_shown(self) -> None:
        error = AgentError(
            agent_name="broken-agent", error_message="Connection timeout"
        )
        report = _make_report(results=[error])
        result = format_markdown(report)
        assert "broken-agent" in result
        assert "error" in result

    def test_agent_timeout_shown(self) -> None:
        timeout = AgentTimeout(agent_name="slow-agent", timeout_seconds=30.0)
        report = _make_report(results=[timeout])
        result = format_markdown(report)
        assert "slow-agent" in result
        assert "timeout" in result
        assert "30" in result

    def test_agent_truncated_shown(self) -> None:
        truncated = AgentTruncated(
            agent_name="long-agent",
            issues=[],
            elapsed_time=10.0,
            turns_consumed=5,
        )
        report = _make_report(results=[truncated])
        result = format_markdown(report)
        assert "long-agent" in result
        assert "truncated" in result


# ── Aggregated Analysis セクション ───────────────────────


class TestAggregatedSection:
    """Aggregated Analysis セクションの出力検証。"""

    def test_strengths_shown(self) -> None:
        agg = AggregatedReport(
            issues=[],
            strengths=["Clean code", "Good tests"],
            recommended_actions=[],
            agent_failures=[],
        )
        report = _make_report(aggregated=agg)
        result = format_markdown(report)
        assert "Clean code" in result
        assert "Good tests" in result

    def test_recommended_actions_shown_with_priority(self) -> None:
        agg = AggregatedReport(
            issues=[],
            strengths=[],
            recommended_actions=[
                RecommendedAction(
                    description="Fix SQL injection", priority=Priority.HIGH
                ),
                RecommendedAction(description="Add logging", priority=Priority.MEDIUM),
            ],
            agent_failures=[],
        )
        report = _make_report(aggregated=agg)
        result = format_markdown(report)
        assert "high" in result
        assert "Fix SQL injection" in result
        assert "medium" in result
        assert "Add logging" in result

    def test_agent_failures_shown(self) -> None:
        agg = AggregatedReport(
            issues=[],
            strengths=[],
            recommended_actions=[],
            agent_failures=["timeout-agent", "broken-agent"],
        )
        report = _make_report(aggregated=agg)
        result = format_markdown(report)
        assert "timeout-agent" in result
        assert "broken-agent" in result

    def test_aggregated_issues_shown(self) -> None:
        issue = _make_issue(description="Deduplicated issue")
        agg = AggregatedReport(
            issues=[issue],
            strengths=[],
            recommended_actions=[],
            agent_failures=[],
        )
        report = _make_report(aggregated=agg)
        result = format_markdown(report)
        assert "Deduplicated issue" in result

    def test_no_aggregated_section_when_none(self) -> None:
        report = _make_report(aggregated=None)
        result = format_markdown(report)
        assert "## Aggregated Analysis" not in result


# ── Load Errors セクション ───────────────────────────────


class TestLoadErrorsSection:
    """Load Errors セクションの出力検証。"""

    def test_load_errors_shown(self) -> None:
        errors = (LoadError(source="bad-agent.toml", message="Invalid TOML syntax"),)
        report = _make_report(load_errors=errors)
        result = format_markdown(report)
        assert "bad-agent.toml" in result
        assert "Invalid TOML syntax" in result

    def test_no_load_errors_section_when_empty(self) -> None:
        report = _make_report(load_errors=())
        result = format_markdown(report)
        assert "## Load Errors" not in result


# ── Aggregation Error セクション ─────────────────────────


class TestAggregationErrorSection:
    """Aggregation Error セクションの出力検証。"""

    def test_aggregation_error_shown(self) -> None:
        report = _make_report(aggregation_error="Aggregator timeout after 60 seconds")
        result = format_markdown(report)
        assert "Aggregator timeout after 60 seconds" in result

    def test_no_aggregation_error_section_when_none(self) -> None:
        report = _make_report(aggregation_error=None)
        result = format_markdown(report)
        assert "## Aggregation Error" not in result


# ── 統合テスト ───────────────────────────────────────────


class TestIntegration:
    """統合的な出力検証。"""

    def test_empty_report_minimal_output(self) -> None:
        """空レポートでも Report ヘッダーと Summary は出力される。"""
        report = _make_report()
        result = format_markdown(report)
        assert result.startswith("# Review Report")
        assert "## Summary" in result
        # オプションセクションは出力されない
        assert "## Issues" not in result
        assert "## Aggregated Analysis" not in result
        assert "## Load Errors" not in result
        assert "## Aggregation Error" not in result

    def test_full_report_all_sections_present(self) -> None:
        """全データが揃った場合に全セクションが出力される。"""
        issue = _make_issue(
            agent_name="sec-agent",
            severity=Severity.CRITICAL,
            description="SQL injection",
            file_path="src/db.py",
            line_number=42,
            suggestion="Use parameterized queries",
            category="security",
        )
        success = _make_success(
            agent_name="sec-agent",
            issues=[issue],
            elapsed_time=5.2,
            cost=CostInfo(input_tokens=1000, output_tokens=500, total_cost=0.05),
        )
        error = AgentError(agent_name="broken-agent", error_message="Connection failed")
        agg = AggregatedReport(
            issues=[issue],
            strengths=["Good structure"],
            recommended_actions=[
                RecommendedAction(description="Fix injection", priority=Priority.HIGH),
            ],
            agent_failures=["broken-agent"],
        )
        report = _make_report(
            results=[success, error],
            total_issues=1,
            max_severity=Severity.CRITICAL,
            total_elapsed_time=5.2,
            total_cost=CostInfo(input_tokens=1000, output_tokens=500, total_cost=0.05),
            load_errors=(LoadError(source="bad.toml", message="Parse error"),),
            aggregated=agg,
            aggregation_error="Partial failure",
        )
        result = format_markdown(report)

        assert "# Review Report" in result
        assert "## Summary" in result
        assert "## Issues" in result
        assert "## Aggregated Analysis" in result
        assert "## Agent Results" in result
        assert "## Load Errors" in result
        assert "## Aggregation Error" in result
