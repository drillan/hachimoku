"""設定リゾルバーのテスト。

T025: merge_config_layers — 空レイヤー, 単一レイヤー, 上書き, None スキップ, agents マージ
T026: filter_cli_overrides — None 除外, 非 None 保持, 空辞書
"""

from __future__ import annotations

import pytest

from hachimoku.config._resolver import (
    _AGENTS_KEY,
    filter_cli_overrides,
    merge_config_layers,
)


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
