"""FileLocation と ReviewIssue のテスト。

FR-DM-002: ReviewIssue の統一表現。
FR-DM-010: Severity の大文字小文字非依存入力。
"""

import pytest
from pydantic import ValidationError

from hachimoku.models.review import FileLocation, ReviewIssue
from hachimoku.models.severity import Severity


class TestFileLocationValid:
    """FileLocation の正常系を検証。"""

    def test_valid_file_location(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        loc = FileLocation(file_path="src/main.py", line_number=1)
        assert loc.file_path == "src/main.py"
        assert loc.line_number == 1

    def test_large_line_number(self) -> None:
        """大きな行番号も受け入れる。"""
        loc = FileLocation(file_path="file.py", line_number=999999)
        assert loc.line_number == 999999


class TestFileLocationConstraints:
    """FileLocation の制約違反を検証。"""

    def test_empty_file_path_rejected(self) -> None:
        """file_path 空文字列で ValidationError。"""
        with pytest.raises(ValidationError, match="file_path"):
            FileLocation(file_path="", line_number=1)

    def test_line_number_zero_rejected(self) -> None:
        """line_number=0 で ValidationError (ge=1)。"""
        with pytest.raises(ValidationError, match="line_number"):
            FileLocation(file_path="file.py", line_number=0)

    def test_negative_line_number_rejected(self) -> None:
        """負の行番号で ValidationError。"""
        with pytest.raises(ValidationError, match="line_number"):
            FileLocation(file_path="file.py", line_number=-1)

    def test_extra_field_rejected(self) -> None:
        """未定義フィールドで ValidationError (extra="forbid")。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            FileLocation(file_path="file.py", line_number=1, column=5)  # type: ignore[call-arg]


class TestReviewIssueValid:
    """ReviewIssue の正常系を検証。"""

    def test_required_fields_only(self) -> None:
        """必須フィールドのみでインスタンス生成が成功する。"""
        issue = ReviewIssue(
            agent_name="code-reviewer",
            severity=Severity.CRITICAL,
            description="Bug detected",
        )
        assert issue.agent_name == "code-reviewer"
        assert issue.severity == Severity.CRITICAL
        assert issue.description == "Bug detected"

    def test_all_fields(self) -> None:
        """全フィールド指定でインスタンス生成が成功する。"""
        loc = FileLocation(file_path="src/main.py", line_number=10)
        issue = ReviewIssue(
            agent_name="code-reviewer",
            severity=Severity.IMPORTANT,
            description="Unused variable",
            location=loc,
            suggestion="Remove the variable",
            category="code-quality",
        )
        assert issue.location == loc
        assert issue.suggestion == "Remove the variable"
        assert issue.category == "code-quality"

    def test_optional_fields_default_none(self) -> None:
        """オプショナルフィールドのデフォルトが None。"""
        issue = ReviewIssue(
            agent_name="test",
            severity=Severity.NITPICK,
            description="Minor issue",
        )
        assert issue.location is None
        assert issue.suggestion is None
        assert issue.category is None


class TestReviewIssueSeverityCaseInsensitive:
    """ReviewIssue での Severity 大文字小文字非依存入力を検証。

    FR-DM-010: field_validator(mode="before") による正規化。
    """

    def test_lowercase_severity_accepted(self) -> None:
        """全小文字で Severity.CRITICAL に正規化される。"""
        issue = ReviewIssue(
            agent_name="test",
            severity="critical",  # type: ignore[arg-type]
            description="test",
        )
        assert issue.severity == Severity.CRITICAL

    def test_uppercase_severity_accepted(self) -> None:
        """全大文字で Severity.CRITICAL に正規化される。"""
        issue = ReviewIssue(
            agent_name="test",
            severity="CRITICAL",  # type: ignore[arg-type]
            description="test",
        )
        assert issue.severity == Severity.CRITICAL

    def test_mixed_case_severity_accepted(self) -> None:
        """混合ケースで Severity.CRITICAL に正規化される。"""
        issue = ReviewIssue(
            agent_name="test",
            severity="cRiTiCaL",  # type: ignore[arg-type]
            description="test",
        )
        assert issue.severity == Severity.CRITICAL

    @pytest.mark.parametrize(
        ("input_str", "expected"),
        [
            ("critical", Severity.CRITICAL),
            ("important", Severity.IMPORTANT),
            ("suggestion", Severity.SUGGESTION),
            ("nitpick", Severity.NITPICK),
        ],
    )
    def test_all_severity_values_case_insensitive(
        self, input_str: str, expected: Severity
    ) -> None:
        """全4値について小文字入力を検証。"""
        issue = ReviewIssue(
            agent_name="test",
            severity=input_str,  # type: ignore[arg-type]
            description="test",
        )
        assert issue.severity == expected

    def test_invalid_severity_string_rejected(self) -> None:
        """不正な文字列で ValidationError。"""
        with pytest.raises(ValidationError):
            ReviewIssue(
                agent_name="test",
                severity="invalid",  # type: ignore[arg-type]
                description="test",
            )

    def test_severity_enum_value_accepted(self) -> None:
        """Severity enum インスタンスも受け入れる。"""
        issue = ReviewIssue(
            agent_name="test",
            severity=Severity.SUGGESTION,
            description="test",
        )
        assert issue.severity == Severity.SUGGESTION


class TestReviewIssueConstraints:
    """ReviewIssue の制約違反を検証。"""

    def test_empty_agent_name_rejected(self) -> None:
        """agent_name 空文字列で ValidationError。"""
        with pytest.raises(ValidationError, match="agent_name"):
            ReviewIssue(
                agent_name="",
                severity=Severity.CRITICAL,
                description="test",
            )

    def test_empty_description_rejected(self) -> None:
        """description 空文字列で ValidationError。"""
        with pytest.raises(ValidationError, match="description"):
            ReviewIssue(
                agent_name="test",
                severity=Severity.CRITICAL,
                description="",
            )

    def test_missing_agent_name_rejected(self) -> None:
        """agent_name 省略で ValidationError。"""
        with pytest.raises(ValidationError):
            ReviewIssue(severity=Severity.CRITICAL, description="test")  # type: ignore[call-arg]

    def test_missing_severity_rejected(self) -> None:
        """severity 省略で ValidationError。"""
        with pytest.raises(ValidationError):
            ReviewIssue(agent_name="test", description="test")  # type: ignore[call-arg]

    def test_missing_description_rejected(self) -> None:
        """description 省略で ValidationError。"""
        with pytest.raises(ValidationError):
            ReviewIssue(agent_name="test", severity=Severity.CRITICAL)  # type: ignore[call-arg]

    def test_extra_field_rejected(self) -> None:
        """未定義フィールドで ValidationError (extra="forbid")。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            ReviewIssue(
                agent_name="test",
                severity=Severity.CRITICAL,
                description="test",
                priority="high",  # type: ignore[call-arg]
            )
