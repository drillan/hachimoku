"""CostInfo, AgentSuccess, AgentError, AgentTimeout, AgentResult のテスト。

FR-DM-003: AgentResult 判別共用体。
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from hachimoku.models.agent_result import (
    AgentError,
    AgentResult,
    AgentSuccess,
    AgentTimeout,
    CostInfo,
)
from hachimoku.models.review import ReviewIssue
from hachimoku.models.severity import Severity


class TestCostInfoValid:
    """CostInfo の正常系を検証。"""

    def test_valid_cost_info(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        cost = CostInfo(input_tokens=100, output_tokens=50, total_cost=0.01)
        assert cost.input_tokens == 100
        assert cost.output_tokens == 50
        assert cost.total_cost == 0.01

    def test_zero_values_accepted(self) -> None:
        """全て0の値も受け入れる (ge=0)。"""
        cost = CostInfo(input_tokens=0, output_tokens=0, total_cost=0.0)
        assert cost.input_tokens == 0
        assert cost.output_tokens == 0
        assert cost.total_cost == 0.0


class TestCostInfoConstraints:
    """CostInfo の制約違反を検証。"""

    def test_negative_input_tokens_rejected(self) -> None:
        with pytest.raises(ValidationError, match="input_tokens"):
            CostInfo(input_tokens=-1, output_tokens=0, total_cost=0.0)

    def test_negative_output_tokens_rejected(self) -> None:
        with pytest.raises(ValidationError, match="output_tokens"):
            CostInfo(input_tokens=0, output_tokens=-1, total_cost=0.0)

    def test_negative_total_cost_rejected(self) -> None:
        with pytest.raises(ValidationError, match="total_cost"):
            CostInfo(input_tokens=0, output_tokens=0, total_cost=-0.01)

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            CostInfo(input_tokens=0, output_tokens=0, total_cost=0.0, currency="USD")  # type: ignore[call-arg]


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

    def test_cost_default_none(self) -> None:
        """cost 省略時に None となる。"""
        result = AgentSuccess(
            agent_name="test",
            issues=[],
            elapsed_time=1.0,
        )
        assert result.cost is None

    def test_cost_accepts_cost_info(self) -> None:
        """cost に CostInfo インスタンスを渡せる。"""
        cost = CostInfo(input_tokens=100, output_tokens=50, total_cost=0.01)
        result = AgentSuccess(
            agent_name="test",
            issues=[],
            elapsed_time=1.0,
            cost=cost,
        )
        assert result.cost == cost

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

    def test_missing_agent_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentSuccess(issues=[], elapsed_time=1.0)  # type: ignore[call-arg]

    def test_missing_issues_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentSuccess(agent_name="test", elapsed_time=1.0)  # type: ignore[call-arg]

    def test_missing_elapsed_time_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AgentSuccess(agent_name="test", issues=[])  # type: ignore[call-arg]

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


class TestAgentTimeoutValid:
    """AgentTimeout の正常系を検証。"""

    def test_valid_agent_timeout(self) -> None:
        """正常値でインスタンス生成が成功する。"""
        timeout = AgentTimeout(
            agent_name="code-reviewer",
            timeout_seconds=30.0,
        )
        assert timeout.agent_name == "code-reviewer"
        assert timeout.timeout_seconds == 30.0

    def test_status_is_timeout_literal(self) -> None:
        """status フィールドが "timeout" である。"""
        timeout = AgentTimeout(agent_name="test", timeout_seconds=10.0)
        assert timeout.status == "timeout"

    def test_status_default_value(self) -> None:
        """status を省略してもデフォルトで "timeout" が設定される。"""
        timeout = AgentTimeout(agent_name="test", timeout_seconds=10.0)
        assert timeout.status == "timeout"


class TestAgentTimeoutConstraints:
    """AgentTimeout の制約違反を検証。"""

    def test_empty_agent_name_rejected(self) -> None:
        with pytest.raises(ValidationError, match="agent_name"):
            AgentTimeout(agent_name="", timeout_seconds=10.0)

    def test_zero_timeout_seconds_rejected(self) -> None:
        """timeout_seconds=0 で ValidationError (gt=0)。"""
        with pytest.raises(ValidationError, match="timeout_seconds"):
            AgentTimeout(agent_name="test", timeout_seconds=0)

    def test_negative_timeout_seconds_rejected(self) -> None:
        with pytest.raises(ValidationError, match="timeout_seconds"):
            AgentTimeout(agent_name="test", timeout_seconds=-1.0)

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(ValidationError, match="extra_forbidden"):
            AgentTimeout(agent_name="test", timeout_seconds=10.0, reason="slow")  # type: ignore[call-arg]


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

    def test_deserialize_timeout(self) -> None:
        """status="timeout" で AgentTimeout が選択される。"""
        result = self.adapter.validate_python(
            {
                "status": "timeout",
                "agent_name": "test",
                "timeout_seconds": 30.0,
            }
        )
        assert isinstance(result, AgentTimeout)
        assert result.status == "timeout"

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
