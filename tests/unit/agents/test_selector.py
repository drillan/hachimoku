"""_matches, select_agents のテスト。

T025: _matches — always=true, file_patterns マッチ/不一致, content_patterns マッチ/不一致,
      OR 条件, 両方空 + always=false
T026: select_agents — 複数エージェント選択, Phase 順ソート, 同 Phase 名前辞書順,
      空リスト入力, 全不適用時の空リスト

タスク参照: specs/003-agent-definition/tasks.md Phase 4
"""

from hachimoku.agents.models import (
    PHASE_ORDER,
    AgentDefinition,
    ApplicabilityRule,
    Phase,
)
from hachimoku.agents.selector import _matches, select_agents


# =============================================================================
# ヘルパー
# =============================================================================


def _valid_agent_data(**overrides: object) -> dict[str, object]:
    """AgentDefinition の最小限有効データを返す。"""
    base: dict[str, object] = {
        "name": "test-agent",
        "description": "A test agent",
        "model": "claude-sonnet-4-5-20250929",
        "output_schema": "scored_issues",
        "system_prompt": "You are a test agent.",
    }
    base.update(overrides)
    return base


def _make_agent(
    name: str = "test-agent",
    phase: str = "main",
    **applicability_kwargs: object,
) -> AgentDefinition:
    """テスト用 AgentDefinition を構築する。"""
    return AgentDefinition.model_validate(
        _valid_agent_data(
            name=name,
            phase=phase,
            applicability=applicability_kwargs if applicability_kwargs else None,
        )
    )


# =============================================================================
# T025: _matches — always=true
# =============================================================================


class TestMatchesAlways:
    """always=true の _matches 評価を検証。"""

    def test_always_true_returns_true(self) -> None:
        """always=true → 常に True。"""
        rule = ApplicabilityRule(always=True)
        assert _matches(rule, [], "") is True

    def test_always_true_ignores_file_paths(self) -> None:
        """always=true ではファイルパスに依存しない。"""
        rule = ApplicabilityRule(always=True)
        assert _matches(rule, ["src/main.py"], "") is True
        assert _matches(rule, [], "") is True

    def test_always_true_ignores_content(self) -> None:
        """always=true ではコンテンツに依存しない。"""
        rule = ApplicabilityRule(always=True)
        assert _matches(rule, [], "some content") is True
        assert _matches(rule, [], "") is True

    def test_always_true_overrides_non_matching_conditions(self) -> None:
        """always=true では file_patterns/content_patterns が不一致でも True。"""
        rule = ApplicabilityRule(
            always=True,
            file_patterns=("*.py",),
            content_patterns=(r"class\s+\w+",),
        )
        assert _matches(rule, ["main.js"], "no match here") is True


# =============================================================================
# T025: _matches — file_patterns マッチ
# =============================================================================


class TestMatchesFilePatterns:
    """file_patterns の _matches 評価を検証。"""

    def test_file_pattern_matches_basename(self) -> None:
        """ファイルパスの basename に対して fnmatch マッチする。"""
        rule = ApplicabilityRule(file_patterns=("*.py",))
        assert _matches(rule, ["src/main.py"], "") is True

    def test_file_pattern_matches_nested_path(self) -> None:
        """深いパスでも basename でマッチする。"""
        rule = ApplicabilityRule(file_patterns=("*.py",))
        assert _matches(rule, ["src/deep/nested/module.py"], "") is True

    def test_file_pattern_no_match(self) -> None:
        """パターンに一致しないファイルパスでは False。"""
        rule = ApplicabilityRule(file_patterns=("*.py",))
        assert _matches(rule, ["src/main.js"], "") is False

    def test_file_pattern_multiple_patterns(self) -> None:
        """複数パターンのいずれかにマッチすれば True。"""
        rule = ApplicabilityRule(file_patterns=("*.py", "*.ts"))
        assert _matches(rule, ["src/app.ts"], "") is True

    def test_file_pattern_multiple_files(self) -> None:
        """複数ファイルのいずれかがマッチすれば True。"""
        rule = ApplicabilityRule(file_patterns=("*.py",))
        assert _matches(rule, ["README.md", "src/main.py"], "") is True

    def test_file_pattern_question_mark(self) -> None:
        """? パターンが1文字にマッチする。"""
        rule = ApplicabilityRule(file_patterns=("?.py",))
        assert _matches(rule, ["a.py"], "") is True
        assert _matches(rule, ["ab.py"], "") is False

    def test_file_pattern_empty_file_paths(self) -> None:
        """file_paths が空リストの場合は False。"""
        rule = ApplicabilityRule(file_patterns=("*.py",))
        assert _matches(rule, [], "") is False

    def test_directory_pattern_does_not_match_basename(self) -> None:
        """ディレクトリ付きパターンは basename マッチのため一致しない。"""
        rule = ApplicabilityRule(file_patterns=("src/*.py",))
        assert _matches(rule, ["src/main.py"], "") is False


# =============================================================================
# T025: _matches — content_patterns マッチ
# =============================================================================


class TestMatchesContentPatterns:
    r"""content_patterns の _matches 評価を検証。"""

    def test_content_pattern_matches(self) -> None:
        r"""正規表現パターンがコンテンツにマッチすれば True。"""
        rule = ApplicabilityRule(content_patterns=(r"class\s+\w+",))
        assert _matches(rule, [], "class MyClass:") is True

    def test_content_pattern_no_match(self) -> None:
        """パターンに一致しないコンテンツでは False。"""
        rule = ApplicabilityRule(content_patterns=(r"class\s+\w+",))
        assert _matches(rule, [], "def my_function():") is False

    def test_content_pattern_multiple_patterns(self) -> None:
        """複数パターンのいずれかにマッチすれば True。"""
        rule = ApplicabilityRule(content_patterns=(r"class\s+\w+", r"def\s+\w+"))
        assert _matches(rule, [], "def my_function():") is True

    def test_content_pattern_re_search_not_fullmatch(self) -> None:
        """re.search による部分マッチで評価する（fullmatch ではない）。"""
        rule = ApplicabilityRule(content_patterns=(r"error",))
        assert _matches(rule, [], "this has an error in it") is True

    def test_content_pattern_empty_content(self) -> None:
        """空コンテンツではマッチしない。"""
        rule = ApplicabilityRule(content_patterns=(r"class\s+\w+",))
        assert _matches(rule, [], "") is False


# =============================================================================
# T025: _matches — OR 条件
# =============================================================================


class TestMatchesOrCondition:
    """file_patterns と content_patterns の OR 評価を検証。"""

    def test_file_match_only(self) -> None:
        """file_patterns のみマッチで True（content_patterns 不一致でも）。"""
        rule = ApplicabilityRule(
            file_patterns=("*.py",),
            content_patterns=(r"class\s+\w+",),
        )
        assert _matches(rule, ["main.py"], "no class here") is True

    def test_content_match_only(self) -> None:
        """content_patterns のみマッチで True（file_patterns 不一致でも）。"""
        rule = ApplicabilityRule(
            file_patterns=("*.py",),
            content_patterns=(r"class\s+\w+",),
        )
        assert _matches(rule, ["main.js"], "class Foo:") is True

    def test_both_match(self) -> None:
        """両方マッチでも True。"""
        rule = ApplicabilityRule(
            file_patterns=("*.py",),
            content_patterns=(r"class\s+\w+",),
        )
        assert _matches(rule, ["main.py"], "class Foo:") is True

    def test_neither_match(self) -> None:
        """両方不一致で False。"""
        rule = ApplicabilityRule(
            file_patterns=("*.py",),
            content_patterns=(r"class\s+\w+",),
        )
        assert _matches(rule, ["main.js"], "no match here") is False


# =============================================================================
# T025: _matches — 両方空 + always=false
# =============================================================================


class TestMatchesNoCondition:
    """条件なし（両方空 + always=false）の _matches 評価を検証。"""

    def test_no_conditions_returns_false(self) -> None:
        """file_patterns/content_patterns 空 + always=false → False。"""
        rule = ApplicabilityRule()
        assert _matches(rule, ["main.py"], "some content") is False

    def test_no_conditions_empty_inputs(self) -> None:
        """入力も空の場合も False。"""
        rule = ApplicabilityRule()
        assert _matches(rule, [], "") is False


# =============================================================================
# T026: select_agents — 選択
# =============================================================================


class TestSelectAgents:
    """select_agents のエージェント選択を検証。"""

    def test_selects_matching_agents(self) -> None:
        """マッチするエージェントのみ選択する。"""
        always_agent = _make_agent(name="always-on", always=True)
        py_agent = _make_agent(name="py-only", file_patterns=("*.py",))
        agents = [always_agent, py_agent]

        result = select_agents(agents, ["main.py"], "")
        assert {a.name for a in result} == {"always-on", "py-only"}

    def test_excludes_non_matching_agents(self) -> None:
        """マッチしないエージェントは除外する。"""
        py_agent = _make_agent(name="py-only", file_patterns=("*.py",))
        result = select_agents([py_agent], ["main.js"], "")
        assert result == []

    def test_empty_agents_list(self) -> None:
        """空のエージェントリスト → 空リスト。"""
        result = select_agents([], ["main.py"], "some content")
        assert result == []

    def test_all_agents_not_applicable(self) -> None:
        """全エージェント不適用 → 空リスト。"""
        agent1 = _make_agent(name="agent-a", file_patterns=("*.py",))
        agent2 = _make_agent(name="agent-b", file_patterns=("*.rs",))
        result = select_agents([agent1, agent2], ["main.js"], "")
        assert result == []

    def test_content_based_selection(self) -> None:
        """content_patterns に基づく選択が機能する。"""
        agent = _make_agent(
            name="error-hunter",
            content_patterns=(r"try:\s*",),
        )
        result = select_agents([agent], [], "try:\n    pass")
        assert len(result) == 1
        assert result[0].name == "error-hunter"


# =============================================================================
# T026: select_agents — ソート
# =============================================================================


class TestSelectAgentsSorting:
    """select_agents の Phase 順 + 名前辞書順ソートを検証。"""

    def test_phase_order_sorting(self) -> None:
        """Phase 順（early → main → final）でソートされる。"""
        final_agent = _make_agent(name="z-final", phase="final", always=True)
        early_agent = _make_agent(name="a-early", phase="early", always=True)
        main_agent = _make_agent(name="m-main", phase="main", always=True)

        result = select_agents([final_agent, early_agent, main_agent], [], "")
        phases = [a.phase for a in result]
        assert phases == [Phase.EARLY, Phase.MAIN, Phase.FINAL]

    def test_same_phase_sorted_by_name(self) -> None:
        """同 Phase 内は名前の辞書順でソートされる。"""
        agent_c = _make_agent(name="charlie", phase="main", always=True)
        agent_a = _make_agent(name="alpha", phase="main", always=True)
        agent_b = _make_agent(name="bravo", phase="main", always=True)

        result = select_agents([agent_c, agent_a, agent_b], [], "")
        names = [a.name for a in result]
        assert names == ["alpha", "bravo", "charlie"]

    def test_mixed_phase_and_name_sorting(self) -> None:
        """Phase 順が優先され、同 Phase 内で名前順。"""
        agents = [
            _make_agent(name="z-main", phase="main", always=True),
            _make_agent(name="a-final", phase="final", always=True),
            _make_agent(name="b-early", phase="early", always=True),
            _make_agent(name="a-main", phase="main", always=True),
            _make_agent(name="a-early", phase="early", always=True),
        ]

        result = select_agents(agents, [], "")
        names = [a.name for a in result]
        assert names == [
            "a-early",
            "b-early",
            "a-main",
            "z-main",
            "a-final",
        ]

    def test_phase_order_uses_phase_order_constant(self) -> None:
        """PHASE_ORDER 定数の値に基づいたソートが行われることを確認。"""
        assert PHASE_ORDER[Phase.EARLY] < PHASE_ORDER[Phase.MAIN]
        assert PHASE_ORDER[Phase.MAIN] < PHASE_ORDER[Phase.FINAL]
