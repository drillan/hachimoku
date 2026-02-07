"""ReviewSummary と ReviewReport のテスト。

FR-DM-004: ReviewReport による結果集約。
FR-RE-014: ReviewReport.load_errors フィールド。
"""

import pytest
from pydantic import ValidationError

from hachimoku.agents.models import LoadError
from hachimoku.models.agent_result import (
    AgentError,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
    CostInfo,
)
from hachimoku.models.report import ReviewReport, ReviewSummary
from hachimoku.models.severity import Severity


class TestReviewSummaryValid:
    """ReviewSummary の正常系を検証。"""

    def test_valid_review_summary(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        summary = ReviewSummary(
            total_issues=5,
            max_severity=Severity.CRITICAL,
            total_elapsed_time=10.5,
        )
        assert summary.total_issues == 5
        assert summary.max_severity == Severity.CRITICAL
        assert summary.total_elapsed_time == 10.5

    def test_max_severity_none_accepted(self) -> None:
        """max_severity=None (問題なし) でインスタンス生成が成功する。"""
        summary = ReviewSummary(
            total_issues=0,
            max_severity=None,
            total_elapsed_time=1.0,
        )
        assert summary.max_severity is None

    def test_total_cost_default_none(self) -> None:
        """total_cost 省略時に None となる。"""
        summary = ReviewSummary(
            total_issues=0,
            max_severity=None,
            total_elapsed_time=0.0,
        )
        assert summary.total_cost is None

    def test_total_cost_accepts_cost_info(self) -> None:
        """total_cost に CostInfo インスタンスを渡せる。"""
        cost = CostInfo(input_tokens=200, output_tokens=100, total_cost=0.05)
        summary = ReviewSummary(
            total_issues=3,
            max_severity=Severity.IMPORTANT,
            total_elapsed_time=5.0,
            total_cost=cost,
        )
        assert summary.total_cost == cost

    def test_zero_values_accepted(self) -> None:
        """total_issues=0, total_elapsed_time=0.0 も受け入れる。"""
        summary = ReviewSummary(
            total_issues=0,
            max_severity=None,
            total_elapsed_time=0.0,
        )
        assert summary.total_issues == 0
        assert summary.total_elapsed_time == 0.0


class TestReviewSummaryConstraints:
    """ReviewSummary の制約違反を検証。"""

    def test_negative_total_issues_rejected(self) -> None:
        with pytest.raises(ValidationError, match="total_issues"):
            ReviewSummary(
                total_issues=-1,
                max_severity=None,
                total_elapsed_time=0.0,
            )

    def test_negative_total_elapsed_time_rejected(self) -> None:
        with pytest.raises(ValidationError, match="total_elapsed_time"):
            ReviewSummary(
                total_issues=0,
                max_severity=None,
                total_elapsed_time=-1.0,
            )

    def test_infinity_total_elapsed_time_rejected(self) -> None:
        """float('inf') は拒否する。"""
        with pytest.raises(ValidationError, match="total_elapsed_time"):
            ReviewSummary(
                total_issues=0,
                max_severity=None,
                total_elapsed_time=float("inf"),
            )

    def test_missing_total_issues_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewSummary(max_severity=None, total_elapsed_time=0.0)  # type: ignore[call-arg]

    def test_missing_max_severity_rejected(self) -> None:
        """max_severity 省略で ValidationError (明示的に None を渡す必要がある)。"""
        with pytest.raises(ValidationError):
            ReviewSummary(total_issues=0, total_elapsed_time=0.0)  # type: ignore[call-arg]

    def test_missing_total_elapsed_time_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewSummary(total_issues=0, max_severity=None)  # type: ignore[call-arg]

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            ReviewSummary(
                total_issues=0,
                max_severity=None,
                total_elapsed_time=0.0,
                avg_time=1.0,  # type: ignore[call-arg]
            )


class TestReviewSummaryConsistency:
    """ReviewSummary の total_issues と max_severity の整合性を検証。"""

    def test_issues_with_severity_accepted(self) -> None:
        """total_issues > 0 かつ max_severity 指定で成功。"""
        summary = ReviewSummary(
            total_issues=5,
            max_severity=Severity.CRITICAL,
            total_elapsed_time=10.0,
        )
        assert summary.total_issues == 5
        assert summary.max_severity == Severity.CRITICAL

    def test_no_issues_with_no_severity_accepted(self) -> None:
        """total_issues=0 かつ max_severity=None で成功。"""
        summary = ReviewSummary(
            total_issues=0,
            max_severity=None,
            total_elapsed_time=0.0,
        )
        assert summary.total_issues == 0
        assert summary.max_severity is None

    def test_issues_without_severity_rejected(self) -> None:
        """total_issues > 0 なのに max_severity=None は矛盾。"""
        with pytest.raises(ValidationError, match="max_severity"):
            ReviewSummary(
                total_issues=5,
                max_severity=None,
                total_elapsed_time=10.0,
            )

    def test_no_issues_with_severity_rejected(self) -> None:
        """total_issues=0 なのに max_severity 指定は矛盾。"""
        with pytest.raises(ValidationError, match="max_severity"):
            ReviewSummary(
                total_issues=0,
                max_severity=Severity.CRITICAL,
                total_elapsed_time=0.0,
            )


class TestReviewReportValid:
    """ReviewReport の正常系を検証。"""

    def _make_summary(self, **kwargs: object) -> ReviewSummary:
        """テスト用 ReviewSummary を生成するヘルパー。"""
        defaults: dict[str, object] = {
            "total_issues": 0,
            "max_severity": None,
            "total_elapsed_time": 0.0,
        }
        defaults.update(kwargs)
        return ReviewSummary(**defaults)  # type: ignore[arg-type]

    def test_valid_review_report(self) -> None:
        """AgentSuccess を含むレポートでインスタンス生成が成功する。"""
        success = AgentSuccess(
            agent_name="code-reviewer",
            issues=[],
            elapsed_time=2.0,
        )
        report = ReviewReport(
            results=[success],
            summary=self._make_summary(total_elapsed_time=2.0),
        )
        assert len(report.results) == 1

    def test_empty_results_accepted(self) -> None:
        """results=[] (空リスト) でインスタンス生成が成功する (SC-006)。"""
        report = ReviewReport(
            results=[],
            summary=self._make_summary(),
        )
        assert report.results == []

    def test_mixed_results_accepted(self) -> None:
        """AgentSuccess と AgentError の混在リストで成功する。"""
        success = AgentSuccess(
            agent_name="reviewer-a",
            issues=[],
            elapsed_time=1.0,
        )
        error = AgentError(
            agent_name="reviewer-b",
            error_message="Connection failed",
        )
        report = ReviewReport(
            results=[success, error],
            summary=self._make_summary(total_elapsed_time=1.0),
        )
        assert len(report.results) == 2

    def test_results_preserved(self) -> None:
        """results 内の各要素が正しい型で保持される。"""
        success = AgentSuccess(
            agent_name="test",
            issues=[],
            elapsed_time=1.0,
        )
        error = AgentError(
            agent_name="test",
            error_message="fail",
        )
        report = ReviewReport(
            results=[success, error],
            summary=self._make_summary(),
        )
        assert isinstance(report.results[0], AgentSuccess)
        assert isinstance(report.results[1], AgentError)

    def test_all_four_variants_accepted(self) -> None:
        """AgentSuccess, AgentTruncated, AgentError, AgentTimeout の4種混在で成功する。"""
        success = AgentSuccess(
            agent_name="reviewer-a",
            issues=[],
            elapsed_time=1.0,
        )
        truncated = AgentTruncated(
            agent_name="reviewer-b",
            issues=[],
            elapsed_time=3.0,
            turns_consumed=10,
        )
        error = AgentError(
            agent_name="reviewer-c",
            error_message="Connection failed",
        )
        timeout = AgentTimeout(
            agent_name="reviewer-d",
            timeout_seconds=30.0,
        )
        report = ReviewReport(
            results=[success, truncated, error, timeout],
            summary=self._make_summary(total_elapsed_time=4.0),
        )
        assert len(report.results) == 4
        assert isinstance(report.results[0], AgentSuccess)
        assert isinstance(report.results[1], AgentTruncated)
        assert isinstance(report.results[2], AgentError)
        assert isinstance(report.results[3], AgentTimeout)


class TestReviewReportConstraints:
    """ReviewReport の制約違反を検証。"""

    def test_missing_results_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewReport(  # type: ignore[call-arg]
                summary=ReviewSummary(
                    total_issues=0,
                    max_severity=None,
                    total_elapsed_time=0.0,
                ),
            )

    def test_missing_summary_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewReport(results=[])  # type: ignore[call-arg]

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            ReviewReport(
                results=[],
                summary=ReviewSummary(
                    total_issues=0,
                    max_severity=None,
                    total_elapsed_time=0.0,
                ),
                metadata={},  # type: ignore[call-arg]
            )


# =============================================================================
# ReviewReport.load_errors (FR-RE-014)
# =============================================================================


class TestReviewReportLoadErrors:
    """ReviewReport の load_errors フィールドを検証。"""

    def _make_summary(self) -> ReviewSummary:
        """テスト用 ReviewSummary を生成するヘルパー。"""
        return ReviewSummary(
            total_issues=0,
            max_severity=None,
            total_elapsed_time=0.0,
        )

    def test_load_errors_default_empty_tuple(self) -> None:
        """load_errors 省略時に空タプルとなる。"""
        report = ReviewReport(
            results=[],
            summary=self._make_summary(),
        )
        assert report.load_errors == ()

    def test_load_errors_accepts_load_error_tuple(self) -> None:
        """load_errors に LoadError タプルを渡せる。"""
        error = LoadError(source="broken.toml", message="parse error")
        report = ReviewReport(
            results=[],
            summary=self._make_summary(),
            load_errors=(error,),
        )
        assert len(report.load_errors) == 1
        assert report.load_errors[0].source == "broken.toml"
        assert report.load_errors[0].message == "parse error"

    def test_multiple_load_errors(self) -> None:
        """複数の LoadError を保持できる。"""
        errors = (
            LoadError(source="a.toml", message="error a"),
            LoadError(source="b.toml", message="error b"),
        )
        report = ReviewReport(
            results=[],
            summary=self._make_summary(),
            load_errors=errors,
        )
        assert len(report.load_errors) == 2
        assert report.load_errors[0].source == "a.toml"
        assert report.load_errors[1].source == "b.toml"
