"""ReviewTarget 判別共用体のテスト。

FR-RE-001: レビュー対象の入力情報モデル。
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from hachimoku.engine._target import (
    DiffTarget,
    FileTarget,
    PRTarget,
    ReviewMode,
    ReviewTarget,
)
from hachimoku.models._base import HachimokuBaseModel


# =============================================================================
# ReviewMode
# =============================================================================


class TestReviewModeEnumValues:
    """ReviewMode 列挙値の定義を検証。"""

    def test_has_three_members(self) -> None:
        """3つの列挙値が定義されている。"""
        assert len(ReviewMode) == 3

    def test_diff_value(self) -> None:
        assert ReviewMode.DIFF == "diff"

    def test_pr_value(self) -> None:
        assert ReviewMode.PR == "pr"

    def test_file_value(self) -> None:
        assert ReviewMode.FILE == "file"


# =============================================================================
# DiffTarget
# =============================================================================


class TestDiffTargetValid:
    """DiffTarget の正常系を検証。"""

    def test_valid_diff_target(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        target = DiffTarget(base_branch="main")
        assert target.mode == "diff"
        assert target.base_branch == "main"
        assert target.issue_number is None

    def test_with_issue_number(self) -> None:
        """issue_number 指定でインスタンス生成が成功する。"""
        target = DiffTarget(base_branch="develop", issue_number=123)
        assert target.issue_number == 123

    def test_inherits_hachimoku_base_model(self) -> None:
        """HachimokuBaseModel のインスタンスである。"""
        target = DiffTarget(base_branch="main")
        assert isinstance(target, HachimokuBaseModel)

    def test_frozen(self) -> None:
        """frozen=True でフィールド変更不可。"""
        target = DiffTarget(base_branch="main")
        with pytest.raises(ValidationError):
            target.base_branch = "develop"  # type: ignore[misc]


class TestDiffTargetConstraints:
    """DiffTarget の制約違反を検証。"""

    def test_empty_base_branch_rejected(self) -> None:
        """base_branch 空文字列で ValidationError。"""
        with pytest.raises(ValidationError, match="base_branch"):
            DiffTarget(base_branch="")

    def test_zero_issue_number_rejected(self) -> None:
        """issue_number=0 で ValidationError (gt=0)。"""
        with pytest.raises(ValidationError, match="issue_number"):
            DiffTarget(base_branch="main", issue_number=0)

    def test_negative_issue_number_rejected(self) -> None:
        """issue_number が負で ValidationError。"""
        with pytest.raises(ValidationError, match="issue_number"):
            DiffTarget(base_branch="main", issue_number=-1)

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドで extra_forbidden。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            DiffTarget(base_branch="main", unknown="x")  # type: ignore[call-arg]


# =============================================================================
# PRTarget
# =============================================================================


class TestPRTargetValid:
    """PRTarget の正常系を検証。"""

    def test_valid_pr_target(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        target = PRTarget(pr_number=42)
        assert target.mode == "pr"
        assert target.pr_number == 42
        assert target.issue_number is None

    def test_with_issue_number(self) -> None:
        """issue_number 指定でインスタンス生成が成功する。"""
        target = PRTarget(pr_number=10, issue_number=99)
        assert target.issue_number == 99


class TestPRTargetConstraints:
    """PRTarget の制約違反を検証。"""

    def test_zero_pr_number_rejected(self) -> None:
        """pr_number=0 で ValidationError (gt=0)。"""
        with pytest.raises(ValidationError, match="pr_number"):
            PRTarget(pr_number=0)

    def test_negative_pr_number_rejected(self) -> None:
        """pr_number が負で ValidationError。"""
        with pytest.raises(ValidationError, match="pr_number"):
            PRTarget(pr_number=-1)

    def test_zero_issue_number_rejected(self) -> None:
        """issue_number=0 で ValidationError (gt=0)。"""
        with pytest.raises(ValidationError, match="issue_number"):
            PRTarget(pr_number=1, issue_number=0)

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドで extra_forbidden。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            PRTarget(pr_number=1, unknown="x")  # type: ignore[call-arg]


# =============================================================================
# FileTarget
# =============================================================================


class TestFileTargetValid:
    """FileTarget の正常系を検証。"""

    def test_valid_file_target(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        target = FileTarget(paths=("src/main.py",))
        assert target.mode == "file"
        assert target.paths == ("src/main.py",)
        assert target.issue_number is None

    def test_multiple_paths(self) -> None:
        """複数パス指定でインスタンス生成が成功する。"""
        target = FileTarget(paths=("src/main.py", "tests/test_main.py"))
        assert len(target.paths) == 2

    def test_with_issue_number(self) -> None:
        """issue_number 指定でインスタンス生成が成功する。"""
        target = FileTarget(paths=("a.py",), issue_number=5)
        assert target.issue_number == 5


class TestFileTargetConstraints:
    """FileTarget の制約違反を検証。"""

    def test_empty_paths_rejected(self) -> None:
        """paths 空タプルで ValidationError (min_length=1)。"""
        with pytest.raises(ValidationError, match="paths"):
            FileTarget(paths=())

    def test_zero_issue_number_rejected(self) -> None:
        """issue_number=0 で ValidationError (gt=0)。"""
        with pytest.raises(ValidationError, match="issue_number"):
            FileTarget(paths=("a.py",), issue_number=0)

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドで extra_forbidden。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            FileTarget(paths=("a.py",), unknown="x")  # type: ignore[call-arg]


# =============================================================================
# ReviewTarget（判別共用体）
# =============================================================================


class TestReviewTargetDiscriminatedUnion:
    """ReviewTarget 判別共用体のデシリアライズを検証。"""

    def setup_method(self) -> None:
        """TypeAdapter を初期化する。"""
        self.adapter: TypeAdapter[DiffTarget | PRTarget | FileTarget] = TypeAdapter(
            ReviewTarget
        )

    def test_deserialize_diff(self) -> None:
        """mode="diff" で DiffTarget が選択される。"""
        result = self.adapter.validate_python({"mode": "diff", "base_branch": "main"})
        assert isinstance(result, DiffTarget)

    def test_deserialize_pr(self) -> None:
        """mode="pr" で PRTarget が選択される。"""
        result = self.adapter.validate_python({"mode": "pr", "pr_number": 42})
        assert isinstance(result, PRTarget)

    def test_deserialize_file(self) -> None:
        """mode="file" で FileTarget が選択される。"""
        result = self.adapter.validate_python(
            {"mode": "file", "paths": ["src/main.py"]}
        )
        assert isinstance(result, FileTarget)

    def test_invalid_mode_rejected(self) -> None:
        """不正な mode 値で ValidationError。"""
        with pytest.raises(ValidationError):
            self.adapter.validate_python({"mode": "unknown", "base_branch": "main"})
