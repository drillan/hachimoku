"""applicability 評価器のテスト。"""

from __future__ import annotations

from hachimoku.agents.applicability import change_matches, select_agent_names
from hachimoku.agents.manifest import MANIFEST_VERSION, Manifest, ManifestEntry
from hachimoku.agents.models import ApplicabilityRule, Phase


class TestChangeMatches:
    def test_always_true_matches_regardless(self) -> None:
        rule = ApplicabilityRule(always=True)
        assert change_matches(rule, frozenset(), "") is True

    def test_file_pattern_matches_basename(self) -> None:
        rule = ApplicabilityRule(file_patterns=("*.py",))
        assert change_matches(rule, frozenset({"main.py"}), "") is True

    def test_file_pattern_no_match(self) -> None:
        rule = ApplicabilityRule(file_patterns=("*.rs",))
        assert change_matches(rule, frozenset({"main.py"}), "") is False

    def test_content_pattern_matches(self) -> None:
        rule = ApplicabilityRule(content_patterns=(r"TODO",))
        assert change_matches(rule, frozenset(), "x = 1  # TODO") is True

    def test_content_pattern_no_match(self) -> None:
        rule = ApplicabilityRule(content_patterns=(r"FIXME",))
        assert change_matches(rule, frozenset(), "x = 1  # TODO") is False

    def test_file_or_content_is_or(self) -> None:
        rule = ApplicabilityRule(
            file_patterns=("*.rs",), content_patterns=(r"password",)
        )
        assert change_matches(rule, frozenset({"main.py"}), "password = 1") is True

    def test_no_conditions_matches_nothing(self) -> None:
        rule = ApplicabilityRule()
        assert change_matches(rule, frozenset({"main.py"}), "anything") is False


class TestSelectAgentNames:
    def test_groups_by_phase_sorted(self) -> None:
        manifest = Manifest(
            version=MANIFEST_VERSION,
            entries=(
                ManifestEntry(
                    name="zzz-early",
                    applicability=ApplicabilityRule(always=True),
                    phase=Phase.EARLY,
                    output_schema="scored_issues",
                ),
                ManifestEntry(
                    name="aaa-early",
                    applicability=ApplicabilityRule(always=True),
                    phase=Phase.EARLY,
                    output_schema="scored_issues",
                ),
                ManifestEntry(
                    name="py-only",
                    applicability=ApplicabilityRule(file_patterns=("*.py",)),
                    phase=Phase.MAIN,
                    output_schema="scored_issues",
                ),
            ),
        )
        result = select_agent_names(manifest, frozenset({"main.py"}), "diff content")
        assert result == {
            Phase.EARLY: ["aaa-early", "zzz-early"],
            Phase.MAIN: ["py-only"],
            Phase.FINAL: [],
        }

    def test_excludes_non_matching(self) -> None:
        manifest = Manifest(
            version=MANIFEST_VERSION,
            entries=(
                ManifestEntry(
                    name="rust-only",
                    applicability=ApplicabilityRule(file_patterns=("*.rs",)),
                    phase=Phase.MAIN,
                    output_schema="scored_issues",
                ),
            ),
        )
        result = select_agent_names(manifest, frozenset({"main.py"}), "")
        assert result == {Phase.EARLY: [], Phase.MAIN: [], Phase.FINAL: []}

    def test_empty_manifest(self) -> None:
        manifest = Manifest(version=MANIFEST_VERSION, entries=())
        result = select_agent_names(manifest, frozenset({"main.py"}), "")
        assert result == {Phase.EARLY: [], Phase.MAIN: [], Phase.FINAL: []}
