"""出力スキーマと SCHEMA_REGISTRY のテスト。

FR-DM-005: BaseAgentOutput と6種スキーマの継承。
FR-DM-006: SCHEMA_REGISTRY。
FR-DM-007: 出力の型検証。
"""

import pytest
from pydantic import ValidationError

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.review import FileLocation, ReviewIssue
from hachimoku.models.schemas import (
    SCHEMA_REGISTRY,
    BaseAgentOutput,
    CategoryClassification,
    CoverageGap,
    DimensionScore,
    DuplicateSchemaError,
    ImprovementItem,
    ImprovementSuggestions,
    MultiDimensionalAnalysis,
    SchemaNotFoundError,
    ScoredIssues,
    SeverityClassified,
    TestGapAssessment,
    _SCHEMA_REGISTRY_INTERNAL,
    get_schema,
    register_schema,
)
from hachimoku.models.severity import Severity


def _make_review_issue(
    agent_name: str = "test-agent",
    severity: Severity = Severity.IMPORTANT,
    description: str = "Test issue",
) -> ReviewIssue:
    """テスト用 ReviewIssue を生成する。"""
    return ReviewIssue(
        agent_name=agent_name,
        severity=severity,
        description=description,
    )


# =============================================================================
# BaseAgentOutput
# =============================================================================


class TestBaseAgentOutputValid:
    """BaseAgentOutput の正常系を検証。"""

    def test_valid_with_issues(self) -> None:
        """issues リスト付きでインスタンス生成が成功する。"""
        issue = _make_review_issue()
        output = BaseAgentOutput(issues=[issue])
        assert output.issues == [issue]

    def test_empty_issues_accepted(self) -> None:
        """空の issues リストでインスタンス生成が成功する。"""
        output = BaseAgentOutput(issues=[])
        assert output.issues == []

    def test_isinstance_hachimoku_base_model(self) -> None:
        """HachimokuBaseModel のインスタンスである。"""
        output = BaseAgentOutput(issues=[])
        assert isinstance(output, HachimokuBaseModel)


class TestBaseAgentOutputConstraints:
    """BaseAgentOutput の制約を検証。"""

    def test_missing_issues_rejected(self) -> None:
        """issues フィールド省略時にバリデーションエラーが発生する。"""
        with pytest.raises(ValidationError, match="issues"):
            BaseAgentOutput()  # type: ignore[call-arg]

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra_field"):
            BaseAgentOutput(issues=[], extra_field="x")  # type: ignore[call-arg]

    def test_frozen_assignment_rejected(self) -> None:
        """frozen=True によりフィールド変更が拒否される。"""
        output = BaseAgentOutput(issues=[])
        with pytest.raises(ValidationError):
            output.issues = []  # type: ignore[misc]


# =============================================================================
# ScoredIssues
# =============================================================================


class TestScoredIssuesValid:
    """ScoredIssues の正常系を検証。"""

    def test_valid_scored_issues(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        issue = _make_review_issue()
        scored = ScoredIssues(issues=[issue], overall_score=7.5)
        assert scored.overall_score == 7.5
        assert scored.issues == [issue]

    def test_score_boundary_zero(self) -> None:
        """overall_score=0.0 が許容される。"""
        scored = ScoredIssues(issues=[], overall_score=0.0)
        assert scored.overall_score == 0.0

    def test_score_boundary_ten(self) -> None:
        """overall_score=10.0 が許容される。"""
        scored = ScoredIssues(issues=[], overall_score=10.0)
        assert scored.overall_score == 10.0

    def test_isinstance_base_agent_output(self) -> None:
        """BaseAgentOutput のインスタンスである。"""
        scored = ScoredIssues(issues=[], overall_score=5.0)
        assert isinstance(scored, BaseAgentOutput)


class TestScoredIssuesConstraints:
    """ScoredIssues の制約を検証。"""

    def test_score_below_zero_rejected(self) -> None:
        """overall_score < 0.0 がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="overall_score"):
            ScoredIssues(issues=[], overall_score=-0.1)

    def test_score_above_ten_rejected(self) -> None:
        """overall_score > 10.0 がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="overall_score"):
            ScoredIssues(issues=[], overall_score=10.1)

    def test_missing_overall_score_rejected(self) -> None:
        """overall_score 省略時にバリデーションエラーが発生する。"""
        with pytest.raises(ValidationError, match="overall_score"):
            ScoredIssues(issues=[])  # type: ignore[call-arg]

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra"):
            ScoredIssues(issues=[], overall_score=5.0, extra="x")  # type: ignore[call-arg]


# =============================================================================
# SeverityClassified
# =============================================================================


class TestSeverityClassifiedValid:
    """SeverityClassified の正常系を検証。"""

    def test_valid_severity_classified(self) -> None:
        """4つの分類リストでインスタンス生成が成功する。"""
        critical = _make_review_issue(severity=Severity.CRITICAL, description="C1")
        important = _make_review_issue(severity=Severity.IMPORTANT, description="I1")
        classified = SeverityClassified(  # type: ignore[call-arg]
            critical_issues=[critical],
            important_issues=[important],
            suggestion_issues=[],
            nitpick_issues=[],
        )
        assert classified.critical_issues == [critical]
        assert classified.important_issues == [important]

    def test_issues_computed_from_classifications(self) -> None:
        """issues が4つの分類リストの結合から導出される。"""
        critical = _make_review_issue(severity=Severity.CRITICAL, description="C1")
        important = _make_review_issue(severity=Severity.IMPORTANT, description="I1")
        suggestion = _make_review_issue(severity=Severity.SUGGESTION, description="S1")
        nitpick = _make_review_issue(severity=Severity.NITPICK, description="N1")
        classified = SeverityClassified(  # type: ignore[call-arg]
            critical_issues=[critical],
            important_issues=[important],
            suggestion_issues=[suggestion],
            nitpick_issues=[nitpick],
        )
        assert classified.issues == [critical, important, suggestion, nitpick]

    def test_issues_preserves_order(self) -> None:
        """issues は critical, important, suggestion, nitpick の順で結合される。"""
        c1 = _make_review_issue(severity=Severity.CRITICAL, description="C1")
        c2 = _make_review_issue(severity=Severity.CRITICAL, description="C2")
        i1 = _make_review_issue(severity=Severity.IMPORTANT, description="I1")
        classified = SeverityClassified(  # type: ignore[call-arg]
            critical_issues=[c1, c2],
            important_issues=[i1],
            suggestion_issues=[],
            nitpick_issues=[],
        )
        assert classified.issues == [c1, c2, i1]

    def test_all_empty_classifications(self) -> None:
        """全分類リストが空の場合、issues も空リストとなる。"""
        classified = SeverityClassified(  # type: ignore[call-arg]
            critical_issues=[],
            important_issues=[],
            suggestion_issues=[],
            nitpick_issues=[],
        )
        assert classified.issues == []

    def test_isinstance_base_agent_output(self) -> None:
        """BaseAgentOutput のインスタンスである。"""
        classified = SeverityClassified(  # type: ignore[call-arg]
            critical_issues=[],
            important_issues=[],
            suggestion_issues=[],
            nitpick_issues=[],
        )
        assert isinstance(classified, BaseAgentOutput)

    def test_model_dump_includes_issues(self) -> None:
        """model_dump() に model_validator で自動導出された issues が含まれる。"""
        issue = _make_review_issue(severity=Severity.CRITICAL, description="C1")
        classified = SeverityClassified(  # type: ignore[call-arg]
            critical_issues=[issue],
            important_issues=[],
            suggestion_issues=[],
            nitpick_issues=[],
        )
        data = classified.model_dump()
        assert "issues" in data
        assert len(data["issues"]) == 1


class TestSeverityClassifiedConstraints:
    """SeverityClassified の制約を検証。"""

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra"):
            SeverityClassified(
                critical_issues=[],
                important_issues=[],
                suggestion_issues=[],
                nitpick_issues=[],
                extra="x",  # type: ignore[call-arg]
            )

    def test_frozen_assignment_rejected(self) -> None:
        """frozen=True によりフィールド変更が拒否される。"""
        classified = SeverityClassified(  # type: ignore[call-arg]
            critical_issues=[],
            important_issues=[],
            suggestion_issues=[],
            nitpick_issues=[],
        )
        with pytest.raises(ValidationError):
            classified.critical_issues = []  # type: ignore[misc]

    def test_issues_always_rebuilt_from_classifications(self) -> None:
        """issues を明示的に渡しても分類リストから再計算される。"""
        issue = _make_review_issue(severity=Severity.CRITICAL, description="C1")
        extra_issue = _make_review_issue(severity=Severity.NITPICK, description="N1")
        classified = SeverityClassified(
            critical_issues=[issue],
            important_issues=[],
            suggestion_issues=[],
            nitpick_issues=[],
            issues=[extra_issue],  # type: ignore[call-arg]
        )
        assert classified.issues == [issue]

    def test_missing_classification_list_rejected(self) -> None:
        """分類リスト省略時にバリデーションエラーが発生する。"""
        with pytest.raises(ValidationError, match="critical_issues"):
            SeverityClassified(
                important_issues=[],
                suggestion_issues=[],
                nitpick_issues=[],
            )  # type: ignore[call-arg]


# =============================================================================
# CoverageGap
# =============================================================================


class TestCoverageGapValid:
    """CoverageGap の正常系を検証。"""

    def test_valid_coverage_gap(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        gap = CoverageGap(
            file_path="src/main.py",
            description="No tests for error handling",
            priority=Severity.IMPORTANT,
        )
        assert gap.file_path == "src/main.py"
        assert gap.priority == Severity.IMPORTANT

    def test_isinstance_hachimoku_base_model(self) -> None:
        """HachimokuBaseModel のインスタンスである。"""
        gap = CoverageGap(
            file_path="src/main.py",
            description="desc",
            priority=Severity.NITPICK,
        )
        assert isinstance(gap, HachimokuBaseModel)


class TestCoverageGapConstraints:
    """CoverageGap の制約を検証。"""

    def test_empty_file_path_rejected(self) -> None:
        """空文字列の file_path がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="file_path"):
            CoverageGap(
                file_path="",
                description="desc",
                priority=Severity.IMPORTANT,
            )

    def test_empty_description_rejected(self) -> None:
        """空文字列の description がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="description"):
            CoverageGap(
                file_path="src/main.py",
                description="",
                priority=Severity.IMPORTANT,
            )

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra"):
            CoverageGap(
                file_path="src/main.py",
                description="desc",
                priority=Severity.IMPORTANT,
                extra="x",  # type: ignore[call-arg]
            )


# =============================================================================
# TestGapAssessment
# =============================================================================


class TestTestGapAssessmentValid:
    """TestGapAssessment の正常系を検証。"""

    def test_valid_test_gap_assessment(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        gap = CoverageGap(
            file_path="src/main.py",
            description="No tests",
            priority=Severity.IMPORTANT,
        )
        assessment = TestGapAssessment(
            issues=[],
            coverage_gaps=[gap],
            risk_level=Severity.IMPORTANT,
        )
        assert assessment.coverage_gaps == [gap]
        assert assessment.risk_level == Severity.IMPORTANT

    def test_empty_coverage_gaps_accepted(self) -> None:
        """空の coverage_gaps リストが許容される。"""
        assessment = TestGapAssessment(
            issues=[],
            coverage_gaps=[],
            risk_level=Severity.NITPICK,
        )
        assert assessment.coverage_gaps == []

    def test_isinstance_base_agent_output(self) -> None:
        """BaseAgentOutput のインスタンスである。"""
        assessment = TestGapAssessment(
            issues=[],
            coverage_gaps=[],
            risk_level=Severity.NITPICK,
        )
        assert isinstance(assessment, BaseAgentOutput)


class TestTestGapAssessmentConstraints:
    """TestGapAssessment の制約を検証。"""

    def test_missing_risk_level_rejected(self) -> None:
        """risk_level 省略時にバリデーションエラーが発生する。"""
        with pytest.raises(ValidationError, match="risk_level"):
            TestGapAssessment(issues=[], coverage_gaps=[])  # type: ignore[call-arg]

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra"):
            TestGapAssessment(
                issues=[],
                coverage_gaps=[],
                risk_level=Severity.NITPICK,
                extra="x",  # type: ignore[call-arg]
            )


# =============================================================================
# DimensionScore
# =============================================================================


class TestDimensionScoreValid:
    """DimensionScore の正常系を検証。"""

    def test_valid_dimension_score(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        dim = DimensionScore(
            name="encapsulation",
            score=8.5,
            description="Good encapsulation",
        )
        assert dim.name == "encapsulation"
        assert dim.score == 8.5

    def test_score_boundary_zero_and_ten(self) -> None:
        """score=0.0 と score=10.0 の境界値が許容される。"""
        dim_zero = DimensionScore(name="a", score=0.0, description="d")
        dim_ten = DimensionScore(name="a", score=10.0, description="d")
        assert dim_zero.score == 0.0
        assert dim_ten.score == 10.0

    def test_isinstance_hachimoku_base_model(self) -> None:
        """HachimokuBaseModel のインスタンスである。"""
        dim = DimensionScore(name="a", score=5.0, description="d")
        assert isinstance(dim, HachimokuBaseModel)


class TestDimensionScoreConstraints:
    """DimensionScore の制約を検証。"""

    def test_score_below_zero_rejected(self) -> None:
        """score < 0.0 がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="score"):
            DimensionScore(name="a", score=-0.1, description="d")

    def test_score_above_ten_rejected(self) -> None:
        """score > 10.0 がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="score"):
            DimensionScore(name="a", score=10.1, description="d")

    def test_empty_name_rejected(self) -> None:
        """空文字列の name がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="name"):
            DimensionScore(name="", score=5.0, description="d")

    def test_empty_description_rejected(self) -> None:
        """空文字列の description がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="description"):
            DimensionScore(name="a", score=5.0, description="")

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra"):
            DimensionScore(name="a", score=5.0, description="d", extra="x")  # type: ignore[call-arg]


# =============================================================================
# MultiDimensionalAnalysis
# =============================================================================


class TestMultiDimensionalAnalysisValid:
    """MultiDimensionalAnalysis の正常系を検証。"""

    def test_valid_multi_dimensional_analysis(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        dim = DimensionScore(name="quality", score=8.0, description="Good")
        analysis = MultiDimensionalAnalysis(issues=[], dimensions=[dim])
        assert analysis.dimensions == [dim]

    def test_empty_dimensions_accepted(self) -> None:
        """空の dimensions リストが許容される。"""
        analysis = MultiDimensionalAnalysis(issues=[], dimensions=[])
        assert analysis.dimensions == []

    def test_isinstance_base_agent_output(self) -> None:
        """BaseAgentOutput のインスタンスである。"""
        analysis = MultiDimensionalAnalysis(issues=[], dimensions=[])
        assert isinstance(analysis, BaseAgentOutput)


class TestMultiDimensionalAnalysisConstraints:
    """MultiDimensionalAnalysis の制約を検証。"""

    def test_missing_dimensions_rejected(self) -> None:
        """dimensions 省略時にバリデーションエラーが発生する。"""
        with pytest.raises(ValidationError, match="dimensions"):
            MultiDimensionalAnalysis(issues=[])  # type: ignore[call-arg]

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra"):
            MultiDimensionalAnalysis(
                issues=[],
                dimensions=[],
                extra="x",  # type: ignore[call-arg]
            )


# =============================================================================
# CategoryClassification
# =============================================================================


class TestCategoryClassificationValid:
    """CategoryClassification の正常系を検証。"""

    def test_valid_category_classification(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        issue = _make_review_issue()
        cat = CategoryClassification(
            issues=[issue],
            categories={"style": [issue]},
        )
        assert cat.categories == {"style": [issue]}

    def test_empty_categories_accepted(self) -> None:
        """空の categories 辞書が許容される。"""
        cat = CategoryClassification(issues=[], categories={})
        assert cat.categories == {}

    def test_isinstance_base_agent_output(self) -> None:
        """BaseAgentOutput のインスタンスである。"""
        cat = CategoryClassification(issues=[], categories={})
        assert isinstance(cat, BaseAgentOutput)


class TestCategoryClassificationConstraints:
    """CategoryClassification の制約を検証。"""

    def test_missing_categories_rejected(self) -> None:
        """categories 省略時にバリデーションエラーが発生する。"""
        with pytest.raises(ValidationError, match="categories"):
            CategoryClassification(issues=[])  # type: ignore[call-arg]

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra"):
            CategoryClassification(
                issues=[],
                categories={},
                extra="x",  # type: ignore[call-arg]
            )


# =============================================================================
# ImprovementItem
# =============================================================================


class TestImprovementItemValid:
    """ImprovementItem の正常系を検証。"""

    def test_valid_improvement_item(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        item = ImprovementItem(
            title="Extract method",
            description="Extract duplicated logic into a helper function",
            priority=Severity.SUGGESTION,
        )
        assert item.title == "Extract method"
        assert item.priority == Severity.SUGGESTION

    def test_location_optional_default_none(self) -> None:
        """location 省略時に None となる。"""
        item = ImprovementItem(title="t", description="d", priority=Severity.NITPICK)
        assert item.location is None

    def test_location_with_file_location(self) -> None:
        """FileLocation 付きでインスタンス生成が成功する。"""
        loc = FileLocation(file_path="src/main.py", line_number=10)
        item = ImprovementItem(
            title="t",
            description="d",
            priority=Severity.SUGGESTION,
            location=loc,
        )
        assert item.location == loc

    def test_isinstance_hachimoku_base_model(self) -> None:
        """HachimokuBaseModel のインスタンスである。"""
        item = ImprovementItem(title="t", description="d", priority=Severity.NITPICK)
        assert isinstance(item, HachimokuBaseModel)


class TestImprovementItemConstraints:
    """ImprovementItem の制約を検証。"""

    def test_empty_title_rejected(self) -> None:
        """空文字列の title がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="title"):
            ImprovementItem(title="", description="d", priority=Severity.NITPICK)

    def test_empty_description_rejected(self) -> None:
        """空文字列の description がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="description"):
            ImprovementItem(title="t", description="", priority=Severity.NITPICK)

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra"):
            ImprovementItem(
                title="t",
                description="d",
                priority=Severity.NITPICK,
                extra="x",  # type: ignore[call-arg]
            )


# =============================================================================
# ImprovementSuggestions
# =============================================================================


class TestImprovementSuggestionsValid:
    """ImprovementSuggestions の正常系を検証。"""

    def test_valid_improvement_suggestions(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        item = ImprovementItem(title="t", description="d", priority=Severity.SUGGESTION)
        suggestions = ImprovementSuggestions(issues=[], suggestions=[item])
        assert suggestions.suggestions == [item]

    def test_empty_suggestions_accepted(self) -> None:
        """空の suggestions リストが許容される。"""
        suggestions = ImprovementSuggestions(issues=[], suggestions=[])
        assert suggestions.suggestions == []

    def test_isinstance_base_agent_output(self) -> None:
        """BaseAgentOutput のインスタンスである。"""
        suggestions = ImprovementSuggestions(issues=[], suggestions=[])
        assert isinstance(suggestions, BaseAgentOutput)


class TestImprovementSuggestionsConstraints:
    """ImprovementSuggestions の制約を検証。"""

    def test_missing_suggestions_rejected(self) -> None:
        """suggestions 省略時にバリデーションエラーが発生する。"""
        with pytest.raises(ValidationError, match="suggestions"):
            ImprovementSuggestions(issues=[])  # type: ignore[call-arg]

    def test_extra_field_rejected(self) -> None:
        """定義外フィールドがバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="extra"):
            ImprovementSuggestions(
                issues=[],
                suggestions=[],
                extra="x",  # type: ignore[call-arg]
            )


# =============================================================================
# SCHEMA_REGISTRY
# =============================================================================


class TestSchemaRegistryLookup:
    """SCHEMA_REGISTRY の検索を検証。"""

    def test_all_six_schemas_registered(self) -> None:
        """6種のスキーマが全て登録されている。"""
        expected_names = {
            "scored_issues",
            "severity_classified",
            "test_gap_assessment",
            "multi_dimensional_analysis",
            "category_classification",
            "improvement_suggestions",
        }
        assert set(SCHEMA_REGISTRY.keys()) == expected_names

    @pytest.mark.parametrize(
        ("name", "expected_class"),
        [
            ("scored_issues", ScoredIssues),
            ("severity_classified", SeverityClassified),
            ("test_gap_assessment", TestGapAssessment),
            ("multi_dimensional_analysis", MultiDimensionalAnalysis),
            ("category_classification", CategoryClassification),
            ("improvement_suggestions", ImprovementSuggestions),
        ],
    )
    def test_get_schema_returns_correct_class(
        self,
        name: str,
        expected_class: type[BaseAgentOutput],
    ) -> None:
        """get_schema が正しいスキーマクラスを返す。"""
        assert get_schema(name) is expected_class

    def test_get_schema_unknown_raises_schema_not_found_error(self) -> None:
        """未登録のスキーマ名で SchemaNotFoundError が発生する。"""
        with pytest.raises(SchemaNotFoundError):
            get_schema("nonexistent_schema")

    def test_schema_not_found_error_message_contains_name(self) -> None:
        """SchemaNotFoundError のメッセージにスキーマ名が含まれる。"""
        with pytest.raises(SchemaNotFoundError, match="nonexistent_schema"):
            get_schema("nonexistent_schema")

    def test_schema_not_found_error_message_lists_available(self) -> None:
        """SchemaNotFoundError のメッセージに利用可能スキーマ一覧が含まれる。"""
        with pytest.raises(SchemaNotFoundError, match="Available schemas:"):
            get_schema("nonexistent_schema")


class TestSchemaRegistryRegister:
    """SCHEMA_REGISTRY の登録を検証。"""

    def test_register_new_schema(self) -> None:
        """新規スキーマの登録が成功する。"""

        class _TestSchema(BaseAgentOutput):
            pass

        name = "_test_register_new_schema"
        try:
            register_schema(name, _TestSchema)
            assert get_schema(name) is _TestSchema
        finally:
            _SCHEMA_REGISTRY_INTERNAL.pop(name, None)

    def test_register_duplicate_raises_duplicate_schema_error(self) -> None:
        """同名スキーマの重複登録で DuplicateSchemaError が発生する。"""
        with pytest.raises(DuplicateSchemaError):
            register_schema("scored_issues", ScoredIssues)

    def test_duplicate_schema_error_message_contains_name(self) -> None:
        """DuplicateSchemaError のメッセージにスキーマ名が含まれる。"""
        with pytest.raises(DuplicateSchemaError, match="scored_issues"):
            register_schema("scored_issues", ScoredIssues)

    def test_register_non_subclass_raises_type_error(self) -> None:
        """BaseAgentOutput のサブクラスでない型の登録で TypeError が発生する。"""
        with pytest.raises(TypeError, match="subclass of BaseAgentOutput"):
            register_schema("bad_schema", str)  # type: ignore[arg-type]


class TestSchemaRegistryImmutability:
    """SCHEMA_REGISTRY の読み取り専用性を検証。"""

    def test_registry_direct_mutation_rejected(self) -> None:
        """SCHEMA_REGISTRY への直接変更が TypeError となる。"""
        with pytest.raises(TypeError):
            SCHEMA_REGISTRY["bad"] = ScoredIssues  # type: ignore[index]


class TestSchemaRegistryExceptions:
    """SCHEMA_REGISTRY の例外クラスを検証。"""

    def test_schema_not_found_error_is_exception(self) -> None:
        """SchemaNotFoundError は Exception のサブクラスである。"""
        assert issubclass(SchemaNotFoundError, Exception)

    def test_duplicate_schema_error_is_exception(self) -> None:
        """DuplicateSchemaError は Exception のサブクラスである。"""
        assert issubclass(DuplicateSchemaError, Exception)
