"""設定リゾルバーのテスト。

T025: merge_config_layers — 空レイヤー, 単一レイヤー, 上書き, None スキップ, agents マージ
T026: filter_cli_overrides — None 除外, 非 None 保持, 空辞書
T027: resolve_config — 5層統合, デフォルト値, 優先順位, エラー伝播
T033: resolve_config — エージェント個別設定の統合テスト (US3)
T040: merge_config_layers — selector セクションのフィールド単位マージ
T041: resolve_config — セレクター設定の統合テスト (US5, FR-CF-010)
"""

from __future__ import annotations

import contextlib
import os
import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from hachimoku.config._resolver import (
    _AGENTS_KEY,
    _SELECTOR_KEY,
    filter_cli_overrides,
    merge_config_layers,
    resolve_config,
)
from hachimoku.models.config import HachimokuConfig, SelectorConfig


# ---------------------------------------------------------------------------
# T025: merge_config_layers
# ---------------------------------------------------------------------------


class TestMergeConfigLayersEmptyOnly:
    """引数なし・None のみ → 空辞書。"""

    def test_returns_empty_dict(self) -> None:
        """引数なしで呼び出すと空辞書を返す。"""
        assert merge_config_layers() == {}

    def test_none_layers_only(self) -> None:
        """None のみのレイヤーでは空辞書を返す。"""
        assert merge_config_layers(None, None) == {}


class TestMergeConfigLayersSingleLayer:
    """単一レイヤー → そのまま返却。"""

    def test_returns_layer_as_is(self) -> None:
        """単一辞書はそのまま返す。"""
        layer: dict[str, object] = {"model": "opus", "timeout": 600}
        assert merge_config_layers(layer) == {"model": "opus", "timeout": 600}

    def test_single_none_and_one_dict(self) -> None:
        """None と辞書の組み合わせでは辞書のみが返る。"""
        layer: dict[str, object] = {"model": "opus"}
        assert merge_config_layers(None, layer) == {"model": "opus"}


class TestMergeConfigLayersOverride:
    """複数レイヤーでの上書き。"""

    def test_upper_overrides_lower(self) -> None:
        """後のレイヤーが先のレイヤーを上書きする。"""
        layer1: dict[str, object] = {"model": "sonnet", "timeout": 300}
        layer2: dict[str, object] = {"model": "opus"}
        result = merge_config_layers(layer1, layer2)
        assert result == {"model": "opus", "timeout": 300}

    def test_three_layers_priority(self) -> None:
        """3レイヤーで最後が最高優先度。"""
        layer1: dict[str, object] = {"model": "sonnet", "timeout": 300}
        layer2: dict[str, object] = {"model": "haiku", "parallel": True}
        layer3: dict[str, object] = {"model": "opus"}
        result = merge_config_layers(layer1, layer2, layer3)
        assert result == {"model": "opus", "timeout": 300, "parallel": True}


class TestMergeConfigLayersNoneSkipped:
    """中間の None レイヤーがスキップされる。"""

    def test_none_layers_skipped(self) -> None:
        """None レイヤーは無視され前後のレイヤーがマージされる。"""
        layer1: dict[str, object] = {"model": "sonnet"}
        layer3: dict[str, object] = {"timeout": 60}
        result = merge_config_layers(layer1, None, layer3)
        assert result == {"model": "sonnet", "timeout": 60}


class TestMergeConfigLayersAgentsMerge:
    """agents セクションのフィールド単位マージ (004-config R-006)。"""

    def test_agents_field_level_merge(self) -> None:
        """同一エージェントの異なるフィールドがマージされる。"""
        layer1: dict[str, object] = {
            _AGENTS_KEY: {"code-reviewer": {"timeout": 600}},
        }
        layer2: dict[str, object] = {
            _AGENTS_KEY: {"code-reviewer": {"model": "haiku"}},
        }
        result = merge_config_layers(layer1, layer2)
        assert result == {
            _AGENTS_KEY: {"code-reviewer": {"timeout": 600, "model": "haiku"}},
        }

    def test_agents_field_override(self) -> None:
        """同一エージェントの同一フィールドは上位レイヤーで上書き。"""
        layer1: dict[str, object] = {
            _AGENTS_KEY: {"code-reviewer": {"model": "sonnet", "timeout": 600}},
        }
        layer2: dict[str, object] = {
            _AGENTS_KEY: {"code-reviewer": {"model": "haiku"}},
        }
        result = merge_config_layers(layer1, layer2)
        assert result == {
            _AGENTS_KEY: {"code-reviewer": {"model": "haiku", "timeout": 600}},
        }

    def test_agents_different_agents_merged(self) -> None:
        """異なるエージェント名は両方とも結果に含まれる。"""
        layer1: dict[str, object] = {
            _AGENTS_KEY: {"code-reviewer": {"model": "sonnet"}},
        }
        layer2: dict[str, object] = {
            _AGENTS_KEY: {"security-checker": {"enabled": False}},
        }
        result = merge_config_layers(layer1, layer2)
        assert result == {
            _AGENTS_KEY: {
                "code-reviewer": {"model": "sonnet"},
                "security-checker": {"enabled": False},
            },
        }

    def test_agents_only_in_lower_layer(self) -> None:
        """下位レイヤーのみに agents がある場合はそのまま保持。"""
        layer1: dict[str, object] = {
            _AGENTS_KEY: {"code-reviewer": {"model": "sonnet"}},
        }
        layer2: dict[str, object] = {"timeout": 600}
        result = merge_config_layers(layer1, layer2)
        assert result == {
            _AGENTS_KEY: {"code-reviewer": {"model": "sonnet"}},
            "timeout": 600,
        }

    def test_agents_only_in_upper_layer(self) -> None:
        """上位レイヤーのみに agents がある場合はそのまま採用。"""
        layer1: dict[str, object] = {"timeout": 600}
        layer2: dict[str, object] = {
            _AGENTS_KEY: {"code-reviewer": {"model": "opus"}},
        }
        result = merge_config_layers(layer1, layer2)
        assert result == {
            "timeout": 600,
            _AGENTS_KEY: {"code-reviewer": {"model": "opus"}},
        }

    def test_three_layers_agents_progressive_merge(self) -> None:
        """3レイヤーで agents が段階的にマージされる。"""
        layer1: dict[str, object] = {
            _AGENTS_KEY: {"code-reviewer": {"timeout": 600}},
        }
        layer2: dict[str, object] = {
            _AGENTS_KEY: {"code-reviewer": {"model": "haiku"}},
        }
        layer3: dict[str, object] = {
            _AGENTS_KEY: {"code-reviewer": {"enabled": False}},
        }
        result = merge_config_layers(layer1, layer2, layer3)
        assert result == {
            _AGENTS_KEY: {
                "code-reviewer": {
                    "timeout": 600,
                    "model": "haiku",
                    "enabled": False,
                },
            },
        }


class TestMergeConfigLayersAgentsTypeError:
    """agents セクションの非 dict 値に対する TypeError。"""

    def test_agents_value_not_dict_raises_type_error(self) -> None:
        """agents キーの値が dict でない場合は TypeError。"""
        layer: dict[str, object] = {_AGENTS_KEY: "invalid"}
        with pytest.raises(TypeError, match="'agents' must be a dict"):
            merge_config_layers(layer)

    def test_agent_config_not_dict_raises_type_error(self) -> None:
        """個別エージェント設定が dict でない場合は TypeError。"""
        layer: dict[str, object] = {
            _AGENTS_KEY: {"code-reviewer": "invalid"},
        }
        with pytest.raises(TypeError, match="Agent config for 'code-reviewer'"):
            merge_config_layers(layer)


class TestMergeConfigLayersDoesNotMutateInput:
    """入力辞書が変更されないことを保証する。"""

    def test_input_dicts_not_mutated(self) -> None:
        """マージ後も入力辞書は元の値のまま。"""
        layer1: dict[str, object] = {
            "model": "sonnet",
            _AGENTS_KEY: {"code-reviewer": {"timeout": 600}},
        }
        layer2: dict[str, object] = {
            "model": "opus",
            _AGENTS_KEY: {"code-reviewer": {"model": "haiku"}},
        }
        # 元の値を保存
        layer1_copy: dict[str, object] = {
            "model": "sonnet",
            _AGENTS_KEY: {"code-reviewer": {"timeout": 600}},
        }
        layer2_copy: dict[str, object] = {
            "model": "opus",
            _AGENTS_KEY: {"code-reviewer": {"model": "haiku"}},
        }
        merge_config_layers(layer1, layer2)
        assert layer1 == layer1_copy
        assert layer2 == layer2_copy


# ---------------------------------------------------------------------------
# T026: filter_cli_overrides
# ---------------------------------------------------------------------------


class TestFilterCliOverridesExcludesNone:
    """None 値が除外される。"""

    def test_none_values_excluded(self) -> None:
        """None 値のキーはフィルタされる。"""
        data: dict[str, object] = {"model": "opus", "timeout": None}
        result = filter_cli_overrides(data)
        assert result == {"model": "opus"}


class TestFilterCliOverridesRetainsValues:
    """非 None 値は保持される。"""

    def test_non_none_values_retained(self) -> None:
        """すべて非 None の値はそのまま保持。"""
        data: dict[str, object] = {"model": "opus", "timeout": 600, "parallel": True}
        assert filter_cli_overrides(data) == data

    def test_false_and_zero_retained(self) -> None:
        """False や 0 などの falsy 値は None ではないので保持。"""
        data: dict[str, object] = {"parallel": False, "timeout": 0}
        assert filter_cli_overrides(data) == {"parallel": False, "timeout": 0}


class TestFilterCliOverridesEmpty:
    """空辞書 → 空辞書。"""

    def test_empty_dict_returns_empty(self) -> None:
        """空辞書を渡すと空辞書を返す。"""
        assert filter_cli_overrides({}) == {}


class TestFilterCliOverridesAllNone:
    """全て None → 空辞書。"""

    def test_all_none_returns_empty(self) -> None:
        """全値が None なら空辞書を返す。"""
        data: dict[str, object] = {"model": None, "timeout": None}
        assert filter_cli_overrides(data) == {}


# ---------------------------------------------------------------------------
# T027: resolve_config
# ---------------------------------------------------------------------------

_PROJECT_DIR_NAME = ".hachimoku"

_SKIP_PERMISSION = pytest.mark.skipif(
    os.name == "nt" or os.getuid() == 0,
    reason="POSIX permissions required and not running as root",
)


def _write_toml(path: Path, content: str) -> Path:
    """TOML ファイルを書き込みパスを返す。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _create_config_toml(base: Path, content: str) -> Path:
    """.hachimoku/config.toml を作成しパスを返す。"""
    (base / _PROJECT_DIR_NAME).mkdir(parents=True, exist_ok=True)
    return _write_toml(base / _PROJECT_DIR_NAME / "config.toml", content)


def _create_pyproject_toml(base: Path, content: str) -> Path:
    """pyproject.toml を作成しパスを返す。"""
    return _write_toml(base / "pyproject.toml", content)


def _nonexistent_user_config(
    tmp_path: Path,
) -> contextlib.AbstractContextManager[object]:
    """get_user_config_path を存在しないパスに差し替える patch を返す。"""
    return patch(
        "hachimoku.config._resolver.get_user_config_path",
        return_value=tmp_path / "nonexistent" / "config.toml",
    )


class TestResolveConfigNoFiles:
    """設定ファイルなし → デフォルト値の HachimokuConfig。"""

    def test_returns_default_config(self, tmp_path: Path) -> None:
        """設定ファイルが存在しない場合、デフォルト値のみで構築。"""
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert config == HachimokuConfig()


class TestResolveConfigOnlyProjectConfig:
    """.hachimoku/config.toml のみ → 反映。"""

    def test_config_toml_values_applied(self, tmp_path: Path) -> None:
        """.hachimoku/config.toml の値が設定に反映される。"""
        _create_config_toml(tmp_path, 'model = "opus"\ntimeout = 600\n')
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert config.model == "opus"
        assert config.timeout == 600
        # 他はデフォルト
        assert config.max_turns == 30


class TestResolveConfigOnlyPyprojectConfig:
    """pyproject.toml [tool.hachimoku] のみ → 反映。"""

    def test_pyproject_toml_values_applied(self, tmp_path: Path) -> None:
        """pyproject.toml の [tool.hachimoku] 値が設定に反映される。"""
        _create_pyproject_toml(
            tmp_path,
            '[tool.hachimoku]\nmodel = "haiku"\ntimeout = 120\n',
        )
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert config.model == "haiku"
        assert config.timeout == 120
        assert config.max_turns == 30  # デフォルト


class TestResolveConfigOnlyUserGlobalConfig:
    """ユーザーグローバル設定のみ → 反映。"""

    def test_user_global_values_applied(self, tmp_path: Path) -> None:
        """~/.config/hachimoku/config.toml の値が設定に反映される。"""
        user_config_dir = tmp_path / "user_home" / ".config" / "hachimoku"
        _write_toml(
            user_config_dir / "config.toml",
            'model = "user-model"\nmax_turns = 42\n',
        )
        with patch(
            "hachimoku.config._resolver.get_user_config_path",
            return_value=user_config_dir / "config.toml",
        ):
            config = resolve_config(start_dir=tmp_path)
        assert config.model == "user-model"
        assert config.max_turns == 42
        assert config.timeout == 600  # デフォルト


class TestResolveConfigProjectDirWithoutConfigToml:
    """.hachimoku/ ディレクトリあり・config.toml 不在 → デフォルト値。"""

    def test_missing_config_toml_skipped(self, tmp_path: Path) -> None:
        """.hachimoku/ はあるが config.toml がない場合、該当レイヤーをスキップ。"""
        (tmp_path / _PROJECT_DIR_NAME).mkdir()
        # config.toml は作成しない
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert config == HachimokuConfig()


class TestResolveConfigFiveLayerPriority:
    """5層の優先順位テスト (FR-CF-001)。"""

    def test_cli_overrides_highest_priority(self, tmp_path: Path) -> None:
        """cli > config.toml > pyproject.toml > user global > default。"""
        # user global
        user_config_dir = tmp_path / "user_home" / ".config" / "hachimoku"
        _write_toml(
            user_config_dir / "config.toml",
            'model = "user-model"\ntimeout = 100\nmax_turns = 5\n',
        )
        # pyproject.toml
        _create_pyproject_toml(
            tmp_path,
            '[tool.hachimoku]\nmodel = "pyproject-model"\ntimeout = 200\n',
        )
        # .hachimoku/config.toml
        _create_config_toml(tmp_path, 'model = "project-model"\ntimeout = 300\n')

        with patch(
            "hachimoku.config._resolver.get_user_config_path",
            return_value=user_config_dir / "config.toml",
        ):
            config = resolve_config(
                start_dir=tmp_path,
                cli_overrides={"model": "cli-model"},
            )
        # CLI が最高優先
        assert config.model == "cli-model"
        # config.toml が pyproject.toml より優先
        assert config.timeout == 300
        # user global の max_turns はそのまま適用
        assert config.max_turns == 5


class TestResolveConfigCliOverridesNoneIgnored:
    """cli_overrides の None 値は無視される。"""

    def test_none_values_in_cli_overrides_ignored(self, tmp_path: Path) -> None:
        """None 値は filter_cli_overrides で除外される。"""
        _create_config_toml(tmp_path, 'model = "opus"\n')
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(
                start_dir=tmp_path,
                cli_overrides={"model": None, "timeout": 600},
            )
        # model は None → CLI 層では上書きされず config.toml の "opus" が残る
        assert config.model == "opus"
        # timeout は CLI 層で 600 に上書き
        assert config.timeout == 600


class TestResolveConfigInvalidValues:
    """不正な設定値 → ValidationError。"""

    def test_invalid_timeout_raises_validation_error(self, tmp_path: Path) -> None:
        """timeout に不正値 → ValidationError (match でフィールド名検証)。"""
        _create_config_toml(tmp_path, "timeout = -1\n")
        with _nonexistent_user_config(tmp_path):
            with pytest.raises(ValidationError, match="timeout"):
                resolve_config(start_dir=tmp_path)


class TestResolveConfigStartDirNone:
    """start_dir=None → カレントディレクトリ (Path.cwd()) から探索。"""

    def test_uses_cwd_when_start_dir_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """start_dir=None の場合 Path.cwd() を使用。"""
        _create_config_toml(tmp_path, 'base_branch = "develop"\n')
        monkeypatch.chdir(tmp_path)
        with _nonexistent_user_config(tmp_path):
            config = resolve_config()  # start_dir=None
        assert config.base_branch == "develop"


class TestResolveConfigTomlSyntaxError:
    """TOML 構文エラー → TOMLDecodeError が伝播。"""

    def test_config_toml_syntax_error_propagates(self, tmp_path: Path) -> None:
        """config.toml の構文エラーは TOMLDecodeError として伝播。"""
        _create_config_toml(tmp_path, "invalid = = = toml")
        with _nonexistent_user_config(tmp_path):
            with pytest.raises(tomllib.TOMLDecodeError):
                resolve_config(start_dir=tmp_path)

    def test_pyproject_toml_syntax_error_propagates(self, tmp_path: Path) -> None:
        """pyproject.toml の構文エラーは TOMLDecodeError として伝播。"""
        _create_pyproject_toml(tmp_path, "[invalid\n")
        with _nonexistent_user_config(tmp_path):
            with pytest.raises(tomllib.TOMLDecodeError):
                resolve_config(start_dir=tmp_path)

    def test_user_global_syntax_error_propagates(self, tmp_path: Path) -> None:
        """ユーザーグローバル設定の構文エラーは TOMLDecodeError として伝播。"""
        user_config_dir = tmp_path / "user_home" / ".config" / "hachimoku"
        _write_toml(user_config_dir / "config.toml", "bad = = = toml")
        with patch(
            "hachimoku.config._resolver.get_user_config_path",
            return_value=user_config_dir / "config.toml",
        ):
            with pytest.raises(tomllib.TOMLDecodeError):
                resolve_config(start_dir=tmp_path)


class TestResolveConfigPermissionError:
    """読み取り権限なし → PermissionError が伝播。"""

    @_SKIP_PERMISSION
    def test_config_toml_permission_error_propagates(self, tmp_path: Path) -> None:
        """config.toml の読み取り権限なし → PermissionError。"""
        config_path = _create_config_toml(tmp_path, 'model = "opus"\n')
        config_path.chmod(0o000)
        try:
            with _nonexistent_user_config(tmp_path):
                with pytest.raises(PermissionError):
                    resolve_config(start_dir=tmp_path)
        finally:
            config_path.chmod(0o644)

    @_SKIP_PERMISSION
    def test_pyproject_toml_permission_error_propagates(self, tmp_path: Path) -> None:
        """pyproject.toml の読み取り権限なし → PermissionError。"""
        pyproject_path = _create_pyproject_toml(
            tmp_path, '[tool.hachimoku]\nmodel = "opus"\n'
        )
        pyproject_path.chmod(0o000)
        try:
            with _nonexistent_user_config(tmp_path):
                with pytest.raises(PermissionError):
                    resolve_config(start_dir=tmp_path)
        finally:
            pyproject_path.chmod(0o644)

    @_SKIP_PERMISSION
    def test_user_global_permission_error_propagates(self, tmp_path: Path) -> None:
        """ユーザーグローバル設定の読み取り権限なし → PermissionError。"""
        user_config_dir = tmp_path / "user_home" / ".config" / "hachimoku"
        user_config_path = _write_toml(
            user_config_dir / "config.toml", 'model = "opus"\n'
        )
        user_config_path.chmod(0o000)
        try:
            with patch(
                "hachimoku.config._resolver.get_user_config_path",
                return_value=user_config_path,
            ):
                with pytest.raises(PermissionError):
                    resolve_config(start_dir=tmp_path)
        finally:
            user_config_path.chmod(0o644)


# ---------------------------------------------------------------------------
# T033: resolve_config — エージェント個別設定の統合テスト (US3)
# ---------------------------------------------------------------------------


class TestResolveConfigAgentEnabledFalse:
    """config.toml で [agents.code-reviewer] enabled=false → 反映。"""

    def test_agent_disabled_through_config(self, tmp_path: Path) -> None:
        """config.toml でエージェントを無効化すると agents に反映される。"""
        _create_config_toml(
            tmp_path,
            "[agents.code-reviewer]\nenabled = false\n",
        )
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert "code-reviewer" in config.agents
        assert config.agents["code-reviewer"].enabled is False

    def test_agent_enabled_default_remains_true(self, tmp_path: Path) -> None:
        """enabled を明示指定しない場合はデフォルト True のまま。"""
        _create_config_toml(
            tmp_path,
            '[agents.code-reviewer]\nmodel = "haiku"\n',
        )
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert config.agents["code-reviewer"].enabled is True


class TestResolveConfigAgentModelOverride:
    """config.toml で [agents.code-reviewer] model="haiku" → 反映。"""

    def test_agent_model_override(self, tmp_path: Path) -> None:
        """エージェント固有のモデルが設定される。"""
        _create_config_toml(
            tmp_path,
            '[agents.code-reviewer]\nmodel = "haiku"\n',
        )
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert config.agents["code-reviewer"].model == "haiku"

    def test_agent_timeout_and_max_turns_override(self, tmp_path: Path) -> None:
        """timeout と max_turns もエージェント固有に上書きできる。"""
        _create_config_toml(
            tmp_path,
            "[agents.code-reviewer]\ntimeout = 600\nmax_turns = 20\n",
        )
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert config.agents["code-reviewer"].timeout == 600
        assert config.agents["code-reviewer"].max_turns == 20


class TestResolveConfigNonexistentAgentPreserved:
    """存在しないエージェント名のセクション → 保持（エラーとしない）。"""

    def test_unknown_agent_name_preserved(self, tmp_path: Path) -> None:
        """定義に存在しないエージェント名でも設定モデルに保持される。"""
        _create_config_toml(
            tmp_path,
            "[agents.nonexistent-agent]\nenabled = false\n",
        )
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert "nonexistent-agent" in config.agents
        assert config.agents["nonexistent-agent"].enabled is False

    def test_multiple_unknown_agents_preserved(self, tmp_path: Path) -> None:
        """複数の未知エージェント名も全て保持される。"""
        _create_config_toml(
            tmp_path,
            ('[agents.agent-a]\nenabled = false\n\n[agents.agent-b]\nmodel = "opus"\n'),
        )
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert "agent-a" in config.agents
        assert "agent-b" in config.agents
        assert config.agents["agent-a"].enabled is False
        assert config.agents["agent-b"].model == "opus"


class TestResolveConfigAgentFieldLevelMergeMultiSource:
    """複数ソース（config.toml + user global）のエージェント設定がフィールド単位マージ。

    R-006: エージェント個別設定は、エージェント名→フィールド単位でマージされる。
    user global (低優先度) → config.toml (高優先度) の順で適用。
    """

    def test_different_fields_merged(self, tmp_path: Path) -> None:
        """異なるフィールドが両ソースからマージされる。

        user global: code-reviewer の timeout=600
        config.toml: code-reviewer の model="haiku"
        → 結果: timeout=600, model="haiku" の両方が反映
        """
        user_config_dir = tmp_path / "user_home" / ".config" / "hachimoku"
        _write_toml(
            user_config_dir / "config.toml",
            "[agents.code-reviewer]\ntimeout = 600\n",
        )
        _create_config_toml(
            tmp_path,
            '[agents.code-reviewer]\nmodel = "haiku"\n',
        )
        with patch(
            "hachimoku.config._resolver.get_user_config_path",
            return_value=user_config_dir / "config.toml",
        ):
            config = resolve_config(start_dir=tmp_path)
        agent = config.agents["code-reviewer"]
        assert agent.timeout == 600
        assert agent.model == "haiku"

    def test_same_field_upper_wins(self, tmp_path: Path) -> None:
        """同一フィールドは上位ソース（config.toml）が優先される。

        user global: code-reviewer の model="sonnet", timeout=600
        config.toml: code-reviewer の model="haiku"
        → 結果: config.toml が優先 → model="haiku", user global の timeout=600 は保持
        """
        user_config_dir = tmp_path / "user_home" / ".config" / "hachimoku"
        _write_toml(
            user_config_dir / "config.toml",
            '[agents.code-reviewer]\nmodel = "sonnet"\ntimeout = 600\n',
        )
        _create_config_toml(
            tmp_path,
            '[agents.code-reviewer]\nmodel = "haiku"\n',
        )
        with patch(
            "hachimoku.config._resolver.get_user_config_path",
            return_value=user_config_dir / "config.toml",
        ):
            config = resolve_config(start_dir=tmp_path)
        agent = config.agents["code-reviewer"]
        # config.toml が優先 → model="haiku"
        assert agent.model == "haiku"
        # user global にしかない timeout は保持
        assert agent.timeout == 600


class TestResolveConfigAgentViaPyproject:
    """pyproject.toml [tool.hachimoku.agents.*] 経由のエージェント個別設定。"""

    def test_pyproject_agent_config_applied(self, tmp_path: Path) -> None:
        """pyproject.toml のエージェント設定が反映される。"""
        _create_pyproject_toml(
            tmp_path,
            '[tool.hachimoku.agents.code-reviewer]\nmodel = "haiku"\n',
        )
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert config.agents["code-reviewer"].model == "haiku"

    def test_pyproject_agent_enabled_false(self, tmp_path: Path) -> None:
        """pyproject.toml でエージェントを無効化できる。"""
        _create_pyproject_toml(
            tmp_path,
            "[tool.hachimoku.agents.code-reviewer]\nenabled = false\n",
        )
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert config.agents["code-reviewer"].enabled is False


class TestResolveConfigAgentThreeSourceMerge:
    """3 ソース（user global + pyproject.toml + config.toml）のエージェントマージ優先順位。"""

    def test_three_source_agent_priority(self, tmp_path: Path) -> None:
        """config.toml > pyproject.toml > user global の優先順位でマージされる。

        user global: code-reviewer の max_turns=5
        pyproject.toml: code-reviewer の timeout=120, model="sonnet"
        config.toml: code-reviewer の model="haiku"
        → 結果: model="haiku" (config.toml), timeout=120 (pyproject), max_turns=5 (user)
        """
        user_config_dir = tmp_path / "user_home" / ".config" / "hachimoku"
        _write_toml(
            user_config_dir / "config.toml",
            "[agents.code-reviewer]\nmax_turns = 5\n",
        )
        _create_pyproject_toml(
            tmp_path,
            '[tool.hachimoku.agents.code-reviewer]\ntimeout = 120\nmodel = "sonnet"\n',
        )
        _create_config_toml(
            tmp_path,
            '[agents.code-reviewer]\nmodel = "haiku"\n',
        )
        with patch(
            "hachimoku.config._resolver.get_user_config_path",
            return_value=user_config_dir / "config.toml",
        ):
            config = resolve_config(start_dir=tmp_path)
        agent = config.agents["code-reviewer"]
        # config.toml が最高優先 → model="haiku"
        assert agent.model == "haiku"
        # pyproject.toml の timeout は保持
        assert agent.timeout == 120
        # user global の max_turns は保持
        assert agent.max_turns == 5


# ---------------------------------------------------------------------------
# T040: merge_config_layers — selector セクションのフィールド単位マージ
# ---------------------------------------------------------------------------


class TestMergeConfigLayersSelectorMerge:
    """selector セクションのフィールド単位マージ (FR-CF-007, FR-CF-010)。"""

    def test_selector_field_level_merge(self) -> None:
        """同一 selector の異なるフィールドがマージされる。"""
        layer1: dict[str, object] = {
            _SELECTOR_KEY: {"timeout": 60},
        }
        layer2: dict[str, object] = {
            _SELECTOR_KEY: {"model": "haiku"},
        }
        result = merge_config_layers(layer1, layer2)
        assert result == {
            _SELECTOR_KEY: {"timeout": 60, "model": "haiku"},
        }

    def test_selector_field_override(self) -> None:
        """同一 selector の同一フィールドは上位レイヤーで上書き。"""
        layer1: dict[str, object] = {
            _SELECTOR_KEY: {"model": "sonnet", "timeout": 60},
        }
        layer2: dict[str, object] = {
            _SELECTOR_KEY: {"model": "haiku"},
        }
        result = merge_config_layers(layer1, layer2)
        assert result == {
            _SELECTOR_KEY: {"model": "haiku", "timeout": 60},
        }

    def test_selector_only_in_lower_layer(self) -> None:
        """下位レイヤーのみに selector がある場合はそのまま保持。"""
        layer1: dict[str, object] = {
            _SELECTOR_KEY: {"model": "sonnet"},
        }
        layer2: dict[str, object] = {"timeout": 600}
        result = merge_config_layers(layer1, layer2)
        assert result == {
            _SELECTOR_KEY: {"model": "sonnet"},
            "timeout": 600,
        }

    def test_selector_only_in_upper_layer(self) -> None:
        """上位レイヤーのみに selector がある場合はそのまま採用。"""
        layer1: dict[str, object] = {"timeout": 600}
        layer2: dict[str, object] = {
            _SELECTOR_KEY: {"model": "opus"},
        }
        result = merge_config_layers(layer1, layer2)
        assert result == {
            "timeout": 600,
            _SELECTOR_KEY: {"model": "opus"},
        }

    def test_three_layers_selector_progressive_merge(self) -> None:
        """3レイヤーで selector が段階的にマージされる。"""
        layer1: dict[str, object] = {
            _SELECTOR_KEY: {"timeout": 60},
        }
        layer2: dict[str, object] = {
            _SELECTOR_KEY: {"model": "haiku"},
        }
        layer3: dict[str, object] = {
            _SELECTOR_KEY: {"max_turns": 5},
        }
        result = merge_config_layers(layer1, layer2, layer3)
        assert result == {
            _SELECTOR_KEY: {
                "timeout": 60,
                "model": "haiku",
                "max_turns": 5,
            },
        }


class TestMergeConfigLayersSelectorTypeError:
    """selector セクションの非 dict 値に対する TypeError。"""

    def test_selector_value_not_dict_raises_type_error(self) -> None:
        """selector キーの値が dict でない場合は TypeError。"""
        layer: dict[str, object] = {_SELECTOR_KEY: "invalid"}
        with pytest.raises(TypeError, match="'selector' must be a dict"):
            merge_config_layers(layer)


class TestMergeConfigLayersSelectorDoesNotMutateInput:
    """selector を含む入力辞書が変更されないことを保証する。"""

    def test_input_dicts_not_mutated(self) -> None:
        """マージ後も入力辞書は元の値のまま。"""
        layer1: dict[str, object] = {
            _SELECTOR_KEY: {"timeout": 60},
        }
        layer2: dict[str, object] = {
            _SELECTOR_KEY: {"model": "haiku"},
        }
        layer1_copy: dict[str, object] = {
            _SELECTOR_KEY: {"timeout": 60},
        }
        layer2_copy: dict[str, object] = {
            _SELECTOR_KEY: {"model": "haiku"},
        }
        merge_config_layers(layer1, layer2)
        assert layer1 == layer1_copy
        assert layer2 == layer2_copy


# ---------------------------------------------------------------------------
# T041: resolve_config — セレクター設定の統合テスト (US5, FR-CF-010)
# ---------------------------------------------------------------------------


class TestResolveConfigSelectorDefault:
    """[selector] セクション未指定 → デフォルト値。"""

    def test_selector_defaults_when_absent(self, tmp_path: Path) -> None:
        """[selector] セクションなしでもデフォルトの SelectorConfig が設定される。"""
        _create_config_toml(tmp_path, 'model = "opus"\n')
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert config.selector == SelectorConfig()


class TestResolveConfigSelectorModelOverride:
    """[selector] model = "haiku" → モデル上書き。"""

    def test_selector_model_override(self, tmp_path: Path) -> None:
        """[selector] セクションの model がセレクター設定に反映される。"""
        _create_config_toml(
            tmp_path,
            '[selector]\nmodel = "haiku"\n',
        )
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert config.selector.model == "haiku"
        # 他はデフォルト
        assert config.selector.timeout is None


class TestResolveConfigSelectorViaPyproject:
    """pyproject.toml [tool.hachimoku.selector] 経由のセレクター設定。"""

    def test_pyproject_selector_config_applied(self, tmp_path: Path) -> None:
        """pyproject.toml のセレクター設定が反映される。"""
        _create_pyproject_toml(
            tmp_path,
            '[tool.hachimoku.selector]\nmodel = "haiku"\n',
        )
        with _nonexistent_user_config(tmp_path):
            config = resolve_config(start_dir=tmp_path)
        assert config.selector.model == "haiku"


class TestResolveConfigSelectorFieldLevelMergeMultiSource:
    """複数ソースの selector 設定がフィールド単位マージ。"""

    def test_different_fields_merged(self, tmp_path: Path) -> None:
        """異なるフィールドが両ソースからマージされる。

        user global: selector の timeout=60
        config.toml: selector の model="haiku"
        → 結果: timeout=60, model="haiku" の両方が反映
        """
        user_config_dir = tmp_path / "user_home" / ".config" / "hachimoku"
        _write_toml(
            user_config_dir / "config.toml",
            "[selector]\ntimeout = 60\n",
        )
        _create_config_toml(
            tmp_path,
            '[selector]\nmodel = "haiku"\n',
        )
        with patch(
            "hachimoku.config._resolver.get_user_config_path",
            return_value=user_config_dir / "config.toml",
        ):
            config = resolve_config(start_dir=tmp_path)
        assert config.selector.model == "haiku"
        assert config.selector.timeout == 60

    def test_same_field_upper_wins(self, tmp_path: Path) -> None:
        """同一フィールドは上位ソース（config.toml）が優先される。"""
        user_config_dir = tmp_path / "user_home" / ".config" / "hachimoku"
        _write_toml(
            user_config_dir / "config.toml",
            '[selector]\nmodel = "sonnet"\ntimeout = 60\n',
        )
        _create_config_toml(
            tmp_path,
            '[selector]\nmodel = "haiku"\n',
        )
        with patch(
            "hachimoku.config._resolver.get_user_config_path",
            return_value=user_config_dir / "config.toml",
        ):
            config = resolve_config(start_dir=tmp_path)
        assert config.selector.model == "haiku"
        assert config.selector.timeout == 60
