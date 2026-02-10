"""_model_resolver のテスト。

resolve_model のプレフィックスベースプロバイダー解決を検証する。
モデル文字列のプレフィックス（claudecode: / anthropic:）でプロバイダーを決定する。
"""

import os
from unittest.mock import patch

import pytest
from claudecode_model import ClaudeCodeModel
from pydantic_ai.models import Model

from hachimoku.engine._model_resolver import resolve_model


class TestResolveModelClaudeCodePrefix:
    """'claudecode:' プレフィックスのモデル解決テスト。"""

    def test_returns_claude_code_model_instance(self) -> None:
        """claudecode: プレフィックスで ClaudeCodeModel が返される。"""
        result = resolve_model("claudecode:claude-opus-4-6")
        assert isinstance(result, ClaudeCodeModel)

    def test_returns_model_subclass(self) -> None:
        """ClaudeCodeModel は pydantic-ai Model のサブクラス。"""
        result = resolve_model("claudecode:claude-opus-4-6")
        assert isinstance(result, Model)

    def test_strips_prefix(self) -> None:
        """'claudecode:' プレフィックスが除去されて model_name に渡される。"""
        result = resolve_model("claudecode:claude-opus-4-6")
        assert isinstance(result, ClaudeCodeModel)
        assert result.model_name == "claude-opus-4-6"

    def test_prefix_stripped_once(self) -> None:
        """'claudecode:' が1回だけ除去される。"""
        result = resolve_model("claudecode:claudecode:model")
        assert isinstance(result, ClaudeCodeModel)
        assert result.model_name == "claudecode:model"

    def test_empty_model_name_raises_error(self) -> None:
        """'claudecode:' のみ（モデル名なし）で ValueError が発生する。"""
        with pytest.raises(ValueError, match="cannot be empty"):
            resolve_model("claudecode:")


class TestResolveModelAnthropicPrefix:
    """'anthropic:' プレフィックスのモデル解決テスト。"""

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_returns_string_as_is(self) -> None:
        """anthropic: プレフィックスではモデル文字列がそのまま返される。"""
        result = resolve_model("anthropic:claude-opus-4-6")
        assert result == "anthropic:claude-opus-4-6"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_returns_str_type(self) -> None:
        """戻り値が str 型であること。"""
        result = resolve_model("anthropic:claude-opus-4-6")
        assert isinstance(result, str)

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_api_key_raises_error(self) -> None:
        """ANTHROPIC_API_KEY 未設定時に ValueError が発生する。"""
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            resolve_model("anthropic:claude-opus-4-6")

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_api_key_present_succeeds(self) -> None:
        """ANTHROPIC_API_KEY が設定されている場合は正常に処理される。"""
        result = resolve_model("anthropic:claude-opus-4-6")
        assert result == "anthropic:claude-opus-4-6"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""})
    def test_empty_api_key_raises_error(self) -> None:
        """ANTHROPIC_API_KEY が空文字列の場合も ValueError が発生する。"""
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            resolve_model("anthropic:claude-opus-4-6")

    def test_empty_model_name_raises_error(self) -> None:
        """'anthropic:' のみ（モデル名なし）で ValueError が発生する。"""
        with pytest.raises(ValueError, match="cannot be empty"):
            resolve_model("anthropic:")


class TestResolveModelUnknownPrefix:
    """未知のプレフィックスに対するガードのテスト。"""

    def test_unknown_prefix_raises_error(self) -> None:
        """未知のプレフィックスで ValueError が発生する。"""
        with pytest.raises(ValueError, match="Unknown model prefix"):
            resolve_model("openai:gpt-4")

    def test_no_prefix_raises_error(self) -> None:
        """プレフィックスなしのモデル名で ValueError が発生する。"""
        with pytest.raises(ValueError, match="Unknown model prefix"):
            resolve_model("claude-opus-4-6")
