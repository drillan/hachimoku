"""_model_resolver のテスト。

resolve_model の anthropic / claudecode プロバイダー解決を検証する。
"""

from claudecode_model import ClaudeCodeModel
from pydantic_ai.models import Model

from hachimoku.engine._model_resolver import resolve_model
from hachimoku.models.config import Provider


class TestResolveModelAnthropic:
    """provider == ANTHROPIC の場合のテスト。"""

    def test_returns_string_as_is(self) -> None:
        """anthropic プロバイダーではモデル文字列がそのまま返される。"""
        result = resolve_model("anthropic:claude-sonnet-4-5", Provider.ANTHROPIC)
        assert result == "anthropic:claude-sonnet-4-5"

    def test_returns_str_type(self) -> None:
        """戻り値が str 型であること。"""
        result = resolve_model("anthropic:claude-sonnet-4-5", Provider.ANTHROPIC)
        assert isinstance(result, str)

    def test_no_prefix_model_string(self) -> None:
        """プレフィックスなしの文字列もそのまま返される。"""
        result = resolve_model("claude-sonnet-4-5", Provider.ANTHROPIC)
        assert result == "claude-sonnet-4-5"


class TestResolveModelClaudeCode:
    """provider == CLAUDECODE の場合のテスト。"""

    def test_returns_claude_code_model_instance(self) -> None:
        """claudecode プロバイダーでは ClaudeCodeModel が返される。"""
        result = resolve_model("anthropic:claude-sonnet-4-5", Provider.CLAUDECODE)
        assert isinstance(result, ClaudeCodeModel)

    def test_returns_model_subclass(self) -> None:
        """ClaudeCodeModel は pydantic-ai Model のサブクラス。"""
        result = resolve_model("anthropic:claude-sonnet-4-5", Provider.CLAUDECODE)
        assert isinstance(result, Model)

    def test_strips_anthropic_prefix(self) -> None:
        """'anthropic:' プレフィックスが除去されて model_name に渡される。"""
        result = resolve_model("anthropic:claude-sonnet-4-5", Provider.CLAUDECODE)
        assert isinstance(result, ClaudeCodeModel)
        assert result.model_name == "claude-sonnet-4-5"

    def test_no_prefix_passed_through(self) -> None:
        """プレフィックスなしのモデル名はそのまま ClaudeCodeModel に渡される。"""
        result = resolve_model("claude-sonnet-4-5", Provider.CLAUDECODE)
        assert isinstance(result, ClaudeCodeModel)
        assert result.model_name == "claude-sonnet-4-5"

    def test_double_prefix_stripped_once(self) -> None:
        """'anthropic:' が1回だけ除去される。"""
        result = resolve_model("anthropic:anthropic:model", Provider.CLAUDECODE)
        assert isinstance(result, ClaudeCodeModel)
        assert result.model_name == "anthropic:model"
