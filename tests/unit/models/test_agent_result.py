"""AgentSuccess, AgentError, AgentResult のテスト。

FR-DM-003: AgentResult 判別共用体。
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from hachimoku.models.agent_result import (
    AgentError,
    AgentResult,
    AgentSuccess,
)
from hachimoku.models.review import ReviewIssue
from hachimoku.models.severity import Severity


class TestAgentSuccessValid:
    """AgentSuccess の正常系を検証。"""

    def test_valid_agent_success(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        result = AgentSuccess(
            agent_name="code-reviewer",
            issues=[],
            elapsed_time=1.5,
        )
        assert result.agent_name == "code-reviewer"
        assert result.issues == []
        assert result.elapsed_time == 1.5

    def test_status_is_success_literal(self) -> None:
        """status フィールドが "success" である。"""
        result = AgentSuccess(
            agent_name="test",
            issues=[],
            elapsed_time=1.0,
        )
        assert result.status == "success"

    def test_status_default_value(self) -> None:
        """status を省略してもデフォルトで "success" が設定される。"""
        result = AgentSuccess(
            agent_name="test",
            issues=[],
            elapsed_time=1.0,
        )
        assert result.status == "success"

    def test_empty_issues_list_accepted(self) -> None:
        """空リスト issues=[] も受け入れる。"""
        result = AgentSuccess(
            agent_name="test",
            issues=[],
            elapsed_time=1.0,
        )
        assert result.issues == []

    def test_overall_score_default_none(self) -> None:
        """overall_score 省略時に None となる。"""
        result = AgentSuccess(agent_name="test", issues=[], elapsed_time=1.0)
        assert result.overall_score is None

    def test_overall_score_accepts_float(self) -> None:
        """overall_score に float を渡せる。"""
        result = AgentSuccess(
            agent_name="test", issues=[], elapsed_time=1.0, overall_score=7.5
        )
        assert result.overall_score == 7.5

    def test_overall_score_boundary_zero(self) -> None:
        """overall_score=0.0 が許容される。"""
        result = AgentSuccess(
            agent_name="test", issues=[], elapsed_time=1.0, overall_score=0.0
        )
        assert result.overall_score == 0.0

    def test_overall_score_boundary_ten(self) -> None:
        """overall_score=10.0 が許容される。"""
        result = AgentSuccess(
            agent_name="test", issues=[], elapsed_time=1.0, overall_score=10.0
        )
        assert result.overall_score == 10.0

    def test_issues_with_review_issue(self) -> None:
        """issues に ReviewIssue リストを渡せる。"""
        issue = ReviewIssue(
            agent_name="code-reviewer",
            severity=Severity.CRITICAL,
            description="Bug found",
        )
        result = AgentSuccess(
            agent_name="code-reviewer",
            issues=[issue],
            elapsed_time=2.0,
        )
        assert len(result.issues) == 1
        assert result.issues[0].severity == Severity.CRITICAL


class TestAgentSuccessConstraints:
    """AgentSuccess の制約違反を検証。"""

    def test_empty_agent_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="agent_name"):
            AgentSuccess(agent_name="", issues=[], elapsed_time=1.0)

    def test_zero_elapsed_time_rejected(self) -> None:
        """elapsed_time=0 で ValidationError (gt=0)。"""
        with pytest.raises(ValidationError, match="elapsed_time"):
            AgentSuccess(agent_name="test", issues=[], elapsed_time=0)

    def test_negative_elapsed_time_rejected(self) -> None:
        with pytest.raises(ValidationError, match="elapsed_time"):
            AgentSuccess(agent_name="test", issues=[], elapsed_time=-1.0)

    def test_infinity_elapsed_time_rejected(self) -> None:
        """float('inf') は拒否する。"""
        with pytest.raises(ValidationError, match="elapsed_time"):
            AgentSuccess(agent_name="test", issues=[], elapsed_time=float("inf"))

    def test_missing_agent_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentSuccess(issues=[], elapsed_time=1.0)  # type: ignore[call-arg]

    def test_missing_issues_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentSuccess(agent_name="test", elapsed_time=1.0)  # type: ignore[call-arg]

    def test_overall_score_below_zero_rejected(self) -> None:
        """overall_score < 0.0 がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="overall_score"):
            AgentSuccess(
                agent_name="test", issues=[], elapsed_time=1.0, overall_score=-0.1
            )

    def test_overall_score_above_ten_rejected(self) -> None:
        """overall_score > 10.0 がバリデーションエラーとなる。"""
        with pytest.raises(ValidationError, match="overall_score"):
            AgentSuccess(
                agent_name="test", issues=[], elapsed_time=1.0, overall_score=10.1
            )

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            AgentSuccess(agent_name="test", issues=[], elapsed_time=1.0, extra="val")  # type: ignore[call-arg]


class TestAgentErrorValid:
    """AgentError の正常系を検証。"""

    def test_valid_agent_error(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        err = AgentError(
            agent_name="code-reviewer",
            error_message="Connection timeout",
        )
        assert err.agent_name == "code-reviewer"
        assert err.error_message == "Connection timeout"

    def test_status_is_error_literal(self) -> None:
        """status フィールドが "error" である。"""
        err = AgentError(agent_name="test", error_message="fail")
        assert err.status == "error"

    def test_status_default_value(self) -> None:
        """status を省略してもデフォルトで "error" が設定される。"""
        err = AgentError(agent_name="test", error_message="fail")
        assert err.status == "error"

    def test_optional_fields_default_none(self) -> None:
        """exit_code, error_type, stderr のデフォルト値が None である。"""
        err = AgentError(agent_name="test", error_message="fail")
        assert err.exit_code is None
        assert err.error_type is None
        assert err.stderr is None

    def test_with_exit_code(self) -> None:
        """exit_code を指定してインスタンス生成が成功する。"""
        err = AgentError(agent_name="test", error_message="fail", exit_code=1)
        assert err.exit_code == 1

    def test_with_error_type(self) -> None:
        """error_type を指定してインスタンス生成が成功する。"""
        err = AgentError(agent_name="test", error_message="fail", error_type="timeout")
        assert err.error_type == "timeout"

    def test_with_stderr(self) -> None:
        """stderr を指定してインスタンス生成が成功する。"""
        err = AgentError(agent_name="test", error_message="fail", stderr="error output")
        assert err.stderr == "error output"

    def test_with_all_optional_fields(self) -> None:
        """全オプションフィールドを指定してインスタンス生成が成功する。"""
        err = AgentError(
            agent_name="test",
            error_message="CLI failed",
            exit_code=1,
            error_type="timeout",
            stderr="timed out",
        )
        assert err.exit_code == 1
        assert err.error_type == "timeout"
        assert err.stderr == "timed out"


class TestAgentErrorConstraints:
    """AgentError の制約違反を検証。"""

    def test_empty_agent_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="agent_name"):
            AgentError(agent_name="", error_message="fail")

    def test_empty_error_message_rejected(self) -> None:
        with pytest.raises(ValidationError, match="error_message"):
            AgentError(agent_name="test", error_message="")

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            AgentError(agent_name="test", error_message="fail", code=500)  # type: ignore[call-arg]

    def test_empty_error_type_rejected(self) -> None:
        """空文字列の error_type は拒否される（min_length=1）。"""
        with pytest.raises(ValidationError, match="error_type"):
            AgentError(agent_name="test", error_message="fail", error_type="")

    def test_empty_stderr_accepted(self) -> None:
        """空文字列の stderr も受け入れる。"""
        err = AgentError(agent_name="test", error_message="fail", stderr="")
        assert err.stderr == ""


class TestAgentResultDiscriminatedUnion:
    """AgentResult 判別共用体のデシリアライズを検証。

    TypeAdapter を使用して JSON-like dict から型を自動選択する。
    """

    def setup_method(self) -> None:
        """TypeAdapter を初期化する。"""
        self.adapter: TypeAdapter[AgentResult] = TypeAdapter(AgentResult)

    def test_deserialize_success(self) -> None:
        """status="success" で AgentSuccess が選択される。"""
        result = self.adapter.validate_python(
            {
                "status": "success",
                "agent_name": "test",
                "issues": [],
                "elapsed_time": 1.0,
            }
        )
        assert isinstance(result, AgentSuccess)
        assert result.status == "success"

    def test_deserialize_error(self) -> None:
        """status="error" で AgentError が選択される。"""
        result = self.adapter.validate_python(
            {
                "status": "error",
                "agent_name": "test",
                "error_message": "fail",
            }
        )
        assert isinstance(result, AgentError)
        assert result.status == "error"

    def test_invalid_status_rejected(self) -> None:
        """不正な status 値で ValidationError。"""
        with pytest.raises(ValidationError):
            self.adapter.validate_python(
                {
                    "status": "unknown",
                    "agent_name": "test",
                }
            )

    def test_missing_status_rejected(self) -> None:
        """status フィールドなしで ValidationError。"""
        with pytest.raises(ValidationError):
            self.adapter.validate_python(
                {
                    "agent_name": "test",
                    "issues": [],
                    "elapsed_time": 1.0,
                }
            )

    def test_success_status_with_error_fields_rejected(self) -> None:
        """status="success" に error_message のみ渡すと ValidationError。"""
        with pytest.raises(ValidationError):
            self.adapter.validate_python(
                {
                    "status": "success",
                    "agent_name": "test",
                    "error_message": "fail",
                }
            )

    def test_error_status_with_success_fields_rejected(self) -> None:
        """status="error" に issues/elapsed_time を渡すと ValidationError。"""
        with pytest.raises(ValidationError):
            self.adapter.validate_python(
                {
                    "status": "error",
                    "agent_name": "test",
                    "issues": [],
                    "elapsed_time": 1.0,
                }
            )

    def test_round_trip_success(self) -> None:
        """AgentSuccess の model_dump → validate_python ラウンドトリップ。"""
        original = AgentSuccess(
            agent_name="test",
            issues=[],
            elapsed_time=1.5,
        )
        data = original.model_dump()
        restored = self.adapter.validate_python(data)
        assert isinstance(restored, AgentSuccess)
        assert restored.agent_name == original.agent_name
        assert restored.elapsed_time == original.elapsed_time

    def test_round_trip_success_with_score(self) -> None:
        """overall_score 付き AgentSuccess のラウンドトリップ。"""
        original = AgentSuccess(
            agent_name="test",
            issues=[],
            elapsed_time=1.5,
            overall_score=8.5,
        )
        data = original.model_dump()
        restored = self.adapter.validate_python(data)
        assert isinstance(restored, AgentSuccess)
        assert restored.overall_score == 8.5

    def test_round_trip_error(self) -> None:
        """AgentError の model_dump → validate_python ラウンドトリップ。"""
        original = AgentError(agent_name="test", error_message="fail")
        data = original.model_dump()
        restored = self.adapter.validate_python(data)
        assert isinstance(restored, AgentError)
        assert restored.error_message == original.error_message

    def test_deserialize_error_with_optional_fields(self) -> None:
        """status="error" にオプションフィールドを含むデータがデシリアライズできる。"""
        result = self.adapter.validate_python(
            {
                "status": "error",
                "agent_name": "test",
                "error_message": "CLI failed",
                "exit_code": 1,
                "error_type": "timeout",
                "stderr": "timed out",
            }
        )
        assert isinstance(result, AgentError)
        assert result.exit_code == 1
        assert result.error_type == "timeout"
        assert result.stderr == "timed out"

    def test_deserialize_error_without_optional_fields(self) -> None:
        """オプションフィールドなしの旧フォーマットがデシリアライズできる（後方互換）。"""
        result = self.adapter.validate_python(
            {
                "status": "error",
                "agent_name": "test",
                "error_message": "fail",
            }
        )
        assert isinstance(result, AgentError)
        assert result.exit_code is None
        assert result.error_type is None
        assert result.stderr is None

    def test_round_trip_error_with_optional_fields(self) -> None:
        """オプションフィールド付き AgentError のラウンドトリップ。"""
        original = AgentError(
            agent_name="test",
            error_message="CLI failed",
            exit_code=1,
            error_type="timeout",
            stderr="timed out",
        )
        data = original.model_dump()
        restored = self.adapter.validate_python(data)
        assert isinstance(restored, AgentError)
        assert restored.exit_code == original.exit_code
        assert restored.error_type == original.error_type
        assert restored.stderr == original.stderr


class TestReshapedAgentResult:
    def test_agent_success_without_cost_field(self) -> None:
        success = AgentSuccess(agent_name="code-reviewer", issues=[])
        assert success.status == "success"
        assert success.elapsed_time is None
        assert not hasattr(success, "cost")

    def test_agent_success_elapsed_time_optional(self) -> None:
        success = AgentSuccess(agent_name="code-reviewer", issues=[], elapsed_time=12.5)
        assert success.elapsed_time == 12.5

    def test_agent_success_elapsed_time_rejects_non_positive(self) -> None:
        with pytest.raises(ValidationError):
            AgentSuccess(agent_name="a", issues=[], elapsed_time=0.0)

    def test_cost_info_is_removed(self) -> None:
        import hachimoku.models.agent_result as mod

        assert not hasattr(mod, "CostInfo")
        assert not hasattr(mod, "AgentTruncated")
        assert not hasattr(mod, "AgentTimeout")

    def test_agent_result_union_has_two_variants(self) -> None:
        from pydantic import TypeAdapter

        adapter: TypeAdapter[AgentResult] = TypeAdapter(AgentResult)
        ok = adapter.validate_python(
            {"status": "success", "agent_name": "a", "issues": []}
        )
        assert isinstance(ok, AgentSuccess)
        err = adapter.validate_python(
            {"status": "error", "agent_name": "a", "error_message": "boom"}
        )
        assert isinstance(err, AgentError)

    def test_agent_result_rejects_removed_status(self) -> None:
        from pydantic import TypeAdapter

        adapter: TypeAdapter[AgentResult] = TypeAdapter(AgentResult)
        with pytest.raises(ValidationError):
            adapter.validate_python(
                {"status": "timeout", "agent_name": "a", "timeout_seconds": 1.0}
            )
