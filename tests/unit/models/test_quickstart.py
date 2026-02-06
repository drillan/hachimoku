"""quickstart.md の使用例コードが公開 API 経由で動作することを検証するスモークテスト。

specs/002-domain-models/quickstart.md (L79-138) の使用例を再現し、
hachimoku.models の re-export が正しく機能することを保証する。
"""

from hachimoku.models import (
    AgentError,
    AgentResult,
    AgentSuccess,
    FileLocation,
    ReviewIssue,
    ReviewReport,
    ReviewSummary,
    ScoredIssues,
    Severity,
    determine_exit_code,
    get_schema,
)


class TestQuickstartReviewIssueCreation:
    """quickstart.md: ReviewIssue の作成。"""

    def test_review_issue_with_location_and_suggestion(self) -> None:
        issue = ReviewIssue(
            agent_name="code-reviewer",
            severity=Severity.CRITICAL,
            description="SQL injection vulnerability detected",
            location=FileLocation(file_path="src/db.py", line_number=42),
            suggestion="Use parameterized queries",
        )

        assert issue.agent_name == "code-reviewer"
        assert issue.severity == Severity.CRITICAL
        assert issue.description == "SQL injection vulnerability detected"
        assert issue.location is not None
        assert issue.location.file_path == "src/db.py"
        assert issue.location.line_number == 42
        assert issue.suggestion == "Use parameterized queries"


class TestQuickstartSeverityCaseInsensitive:
    """quickstart.md: 大文字小文字非依存の Severity 入力。"""

    def test_lowercase_severity_accepted(self) -> None:
        issue = ReviewIssue(
            agent_name="code-reviewer",
            severity="critical",  # type: ignore[arg-type]
            description="Another issue",
        )

        assert issue.severity == Severity.CRITICAL


class TestQuickstartAgentResult:
    """quickstart.md: AgentResult（判別共用体）。"""

    def test_agent_success_creation(self) -> None:
        issue = ReviewIssue(
            agent_name="code-reviewer",
            severity=Severity.CRITICAL,
            description="SQL injection vulnerability detected",
            location=FileLocation(file_path="src/db.py", line_number=42),
            suggestion="Use parameterized queries",
        )
        success: AgentResult = AgentSuccess(
            agent_name="code-reviewer",
            issues=[issue],
            elapsed_time=1.5,
        )

        assert success.status == "success"  # type: ignore[union-attr]

    def test_agent_error_creation(self) -> None:
        error: AgentResult = AgentError(
            agent_name="silent-failure-hunter",
            error_message="API rate limit exceeded",
        )

        assert error.status == "error"  # type: ignore[union-attr]


class TestQuickstartReviewReport:
    """quickstart.md: ReviewReport + ReviewSummary。"""

    def test_review_report_creation(self) -> None:
        issue = ReviewIssue(
            agent_name="code-reviewer",
            severity=Severity.CRITICAL,
            description="SQL injection vulnerability detected",
        )
        success: AgentResult = AgentSuccess(
            agent_name="code-reviewer",
            issues=[issue],
            elapsed_time=1.5,
        )
        error: AgentResult = AgentError(
            agent_name="silent-failure-hunter",
            error_message="API rate limit exceeded",
        )
        report = ReviewReport(
            results=[success, error],
            summary=ReviewSummary(
                total_issues=1,
                max_severity=Severity.CRITICAL,
                total_elapsed_time=1.5,
            ),
        )

        assert len(report.results) == 2
        assert report.summary.total_issues == 1
        assert report.summary.max_severity == Severity.CRITICAL


class TestQuickstartExitCode:
    """quickstart.md: 終了コード決定。"""

    def test_critical_severity_returns_exit_code_1(self) -> None:
        exit_code = determine_exit_code(Severity.CRITICAL)

        assert exit_code == 1


class TestQuickstartSchemaRegistry:
    """quickstart.md: SCHEMA_REGISTRY の使用。"""

    def test_get_schema_scored_issues(self) -> None:
        schema = get_schema("scored_issues")

        assert schema is ScoredIssues
