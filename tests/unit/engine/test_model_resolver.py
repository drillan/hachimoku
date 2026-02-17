"""_model_resolver のテスト。

resolve_model のプレフィックスベースプロバイダー解決を検証する。
モデル文字列のプレフィックス（claudecode: / anthropic:）でプロバイダーを決定する。
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from claudecode_model import ClaudeCodeModel
from pydantic_ai.models import Model

from hachimoku.engine._model_resolver import (
    _ALLOWED_BUILTIN_TOOLS,
    resolve_model,
)


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


class TestResolveModelAllowedTools:
    """ClaudeCodeModel の allowed_tools 設定テスト。

    読み取り専用ツール（Read, Grep, Glob）のみ許可し、
    それ以外の CLI ビルトインツールは自動的にブロックされる。
    """

    @patch("hachimoku.engine._model_resolver.ClaudeCodeModel")
    def test_claudecode_passes_allowed_tools(self, mock_ccm_cls: MagicMock) -> None:
        """claudecode: プレフィックスで allowed_tools が渡される。"""
        resolve_model("claudecode:claude-opus-4-6")
        mock_ccm_cls.assert_called_once_with(
            model_name="claude-opus-4-6",
            allowed_tools=list(_ALLOWED_BUILTIN_TOOLS),
        )

    @pytest.mark.parametrize("tool", ["Read", "Grep", "Glob"])
    def test_allowed_tools_contains_readonly_tool(self, tool: str) -> None:
        """読み取り専用ツールが許可リストに含まれる。"""
        assert tool in _ALLOWED_BUILTIN_TOOLS

    @pytest.mark.parametrize("tool", ["Bash", "Write", "Task"])
    def test_allowed_tools_excludes_dangerous_tool(self, tool: str) -> None:
        """危険なツールは許可リストに含まれない。"""
        assert tool not in _ALLOWED_BUILTIN_TOOLS

    def test_allowed_tools_is_nonempty(self) -> None:
        """許可リストが空でないこと。"""
        assert _ALLOWED_BUILTIN_TOOLS

    def test_allowed_tools_has_exactly_three_tools(self) -> None:
        """許可リストは正確に3つの読み取り専用ツールのみ。"""
        assert len(_ALLOWED_BUILTIN_TOOLS) == 3


class TestResolveModelAllowedBuiltinToolsOverride:
    """allowed_builtin_tools パラメータによるオーバーライドのテスト。

    Issue #198: セレクター向けに CLI ビルトインツールを空にできる仕組み。
    """

    @patch("hachimoku.engine._model_resolver.ClaudeCodeModel")
    def test_none_uses_default_tools(self, mock_ccm_cls: MagicMock) -> None:
        """allowed_builtin_tools=None でデフォルトの _ALLOWED_BUILTIN_TOOLS が使用される。"""
        resolve_model("claudecode:claude-opus-4-6", allowed_builtin_tools=None)
        mock_ccm_cls.assert_called_once_with(
            model_name="claude-opus-4-6",
            allowed_tools=list(_ALLOWED_BUILTIN_TOOLS),
        )

    @patch("hachimoku.engine._model_resolver.ClaudeCodeModel")
    def test_empty_tuple_passes_empty_list(self, mock_ccm_cls: MagicMock) -> None:
        """allowed_builtin_tools=() で空リストが ClaudeCodeModel に渡される。"""
        resolve_model("claudecode:claude-opus-4-6", allowed_builtin_tools=())
        mock_ccm_cls.assert_called_once_with(
            model_name="claude-opus-4-6",
            allowed_tools=[],
        )

    @patch("hachimoku.engine._model_resolver.ClaudeCodeModel")
    def test_custom_tools_passed(self, mock_ccm_cls: MagicMock) -> None:
        """allowed_builtin_tools=("Read",) で指定ツールのみ渡される。"""
        resolve_model("claudecode:claude-opus-4-6", allowed_builtin_tools=("Read",))
        mock_ccm_cls.assert_called_once_with(
            model_name="claude-opus-4-6",
            allowed_tools=["Read"],
        )

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_anthropic_prefix_ignores_parameter(self) -> None:
        """anthropic: プレフィックスでは allowed_builtin_tools が無視される。"""
        result = resolve_model("anthropic:claude-opus-4-6", allowed_builtin_tools=())
        assert result == "anthropic:claude-opus-4-6"

    @patch("hachimoku.engine._model_resolver.ClaudeCodeModel")
    def test_omitted_parameter_uses_default(self, mock_ccm_cls: MagicMock) -> None:
        """パラメータ省略時はデフォルトの _ALLOWED_BUILTIN_TOOLS が使用される。"""
        resolve_model("claudecode:claude-opus-4-6")
        mock_ccm_cls.assert_called_once_with(
            model_name="claude-opus-4-6",
            allowed_tools=list(_ALLOWED_BUILTIN_TOOLS),
        )


# =============================================================================
# resolve_model — extra_builtin_tools パラメータ（Issue #222）
# =============================================================================


class TestResolveModelExtraBuiltinTools:
    """extra_builtin_tools パラメータのテスト。

    Issue #222: web_fetch カテゴリから解決された claudecode ビルトインツール名を
    ClaudeCodeModel の allowed_tools に追加する。
    """

    @patch("hachimoku.engine._model_resolver.ClaudeCodeModel")
    def test_empty_extra_tools_no_change(self, mock_ccm_cls: MagicMock) -> None:
        """extra_builtin_tools=() でデフォルトの allowed_tools のみ渡される。"""
        resolve_model("claudecode:claude-opus-4-6", extra_builtin_tools=())
        mock_ccm_cls.assert_called_once_with(
            model_name="claude-opus-4-6",
            allowed_tools=list(_ALLOWED_BUILTIN_TOOLS),
        )

    @patch("hachimoku.engine._model_resolver.ClaudeCodeModel")
    def test_extra_tools_appended_to_default(self, mock_ccm_cls: MagicMock) -> None:
        """extra_builtin_tools がデフォルトの allowed_tools に追加される。"""
        resolve_model("claudecode:claude-opus-4-6", extra_builtin_tools=("WebFetch",))
        expected = list(_ALLOWED_BUILTIN_TOOLS) + ["WebFetch"]
        mock_ccm_cls.assert_called_once_with(
            model_name="claude-opus-4-6",
            allowed_tools=expected,
        )

    @patch("hachimoku.engine._model_resolver.ClaudeCodeModel")
    def test_extra_tools_appended_to_custom_allowed(
        self, mock_ccm_cls: MagicMock
    ) -> None:
        """allowed_builtin_tools と extra_builtin_tools が両方指定された場合、結合される。"""
        resolve_model(
            "claudecode:claude-opus-4-6",
            allowed_builtin_tools=("Read",),
            extra_builtin_tools=("WebFetch",),
        )
        mock_ccm_cls.assert_called_once_with(
            model_name="claude-opus-4-6",
            allowed_tools=["Read", "WebFetch"],
        )

    @patch("hachimoku.engine._model_resolver.ClaudeCodeModel")
    def test_extra_tools_appended_to_empty_allowed(
        self, mock_ccm_cls: MagicMock
    ) -> None:
        """allowed_builtin_tools=() + extra_builtin_tools で extra のみ渡される。"""
        resolve_model(
            "claudecode:claude-opus-4-6",
            allowed_builtin_tools=(),
            extra_builtin_tools=("WebFetch",),
        )
        mock_ccm_cls.assert_called_once_with(
            model_name="claude-opus-4-6",
            allowed_tools=["WebFetch"],
        )

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"})
    def test_anthropic_prefix_ignores_extra_tools(self) -> None:
        """anthropic: プレフィックスでは extra_builtin_tools が無視される。"""
        result = resolve_model(
            "anthropic:claude-opus-4-6", extra_builtin_tools=("WebFetch",)
        )
        assert result == "anthropic:claude-opus-4-6"
