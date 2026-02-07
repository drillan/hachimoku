"""ReviewInstructionBuilder のテスト。

FR-RE-001: 入力モードに応じたプロンプトコンテキストの生成。
FR-RE-011: --issue オプションの Issue 番号注入。
"""

from hachimoku.agents.models import AgentDefinition, ApplicabilityRule, Phase
from hachimoku.engine._instruction import (
    build_review_instruction,
    build_selector_instruction,
)
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget


def _make_agent(
    name: str = "test-agent",
    description: str = "Test description",
    phase: Phase = Phase.MAIN,
) -> AgentDefinition:
    """テスト用 AgentDefinition を生成するヘルパー。

    resolved_schema は model_validator(mode="before") で output_schema から自動解決される。
    """
    return AgentDefinition(  # type: ignore[call-arg]
        name=name,
        description=description,
        model="test-model",
        output_schema="scored_issues",
        system_prompt="Test prompt",
        applicability=ApplicabilityRule(always=True),
        phase=phase,
    )


# =============================================================================
# build_review_instruction
# =============================================================================


class TestBuildReviewInstructionDiff:
    """build_review_instruction の diff モードを検証。"""

    def test_includes_base_branch(self) -> None:
        """base_branch 名を含む。"""
        target = DiffTarget(base_branch="develop")
        instruction = build_review_instruction(target)
        assert "develop" in instruction

    def test_includes_merge_base_guidance(self) -> None:
        """マージベースの差分取得ガイダンスを含む。"""
        target = DiffTarget(base_branch="main")
        instruction = build_review_instruction(target)
        assert "merge-base" in instruction.lower() or "diff" in instruction.lower()


class TestBuildReviewInstructionPR:
    """build_review_instruction の PR モードを検証。"""

    def test_includes_pr_number(self) -> None:
        """PR 番号を含む。"""
        target = PRTarget(pr_number=42)
        instruction = build_review_instruction(target)
        assert "42" in instruction


class TestBuildReviewInstructionFile:
    """build_review_instruction の file モードを検証。"""

    def test_includes_file_paths(self) -> None:
        """ファイルパスを含む。"""
        target = FileTarget(paths=("src/main.py", "tests/test.py"))
        instruction = build_review_instruction(target)
        assert "src/main.py" in instruction
        assert "tests/test.py" in instruction


class TestBuildReviewInstructionIssue:
    """build_review_instruction の issue_number 付加を検証。"""

    def test_includes_issue_number_when_present(self) -> None:
        """issue_number 指定時に Issue 番号を含む。"""
        target = DiffTarget(base_branch="main", issue_number=123)
        instruction = build_review_instruction(target)
        assert "123" in instruction

    def test_excludes_issue_when_none(self) -> None:
        """issue_number=None 時に Issue 参照を含まない。"""
        target = DiffTarget(base_branch="main")
        instruction = build_review_instruction(target)
        # issue 関連のキーワードが含まれないことを確認
        assert "#None" not in instruction


# =============================================================================
# build_selector_instruction
# =============================================================================


class TestBuildSelectorInstruction:
    """build_selector_instruction 関数のテスト。"""

    def test_includes_review_instruction_content(self) -> None:
        """レビュー指示情報を含む。"""
        target = DiffTarget(base_branch="main")
        instruction = build_selector_instruction(target, [])
        assert "main" in instruction

    def test_includes_agent_name_and_description(self) -> None:
        """エージェント名と説明を含む。"""
        target = DiffTarget(base_branch="main")
        agent = _make_agent(name="code-reviewer", description="Code quality check")
        instruction = build_selector_instruction(target, [agent])
        assert "code-reviewer" in instruction
        assert "Code quality check" in instruction

    def test_includes_multiple_agents(self) -> None:
        """複数エージェントの情報を含む。"""
        target = PRTarget(pr_number=10)
        agents = [
            _make_agent(name="reviewer-a", description="Desc A"),
            _make_agent(name="reviewer-b", description="Desc B"),
        ]
        instruction = build_selector_instruction(target, agents)
        assert "reviewer-a" in instruction
        assert "reviewer-b" in instruction

    def test_empty_agents_list_handled(self) -> None:
        """空のエージェントリストでも例外なく動作する。"""
        target = PRTarget(pr_number=10)
        instruction = build_selector_instruction(target, [])
        assert isinstance(instruction, str)
        assert len(instruction) > 0
