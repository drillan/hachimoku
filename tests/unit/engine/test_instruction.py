"""ReviewInstructionBuilder のテスト。

FR-RE-001: 入力モードに応じたプロンプトコンテキストの生成。
FR-RE-011: --issue オプションの Issue 番号注入。
Issue #129: resolved_content のインストラクション埋め込み。
Issue #170: セレクター向け diff メタデータサマリー。
"""

from hachimoku.agents.models import AgentDefinition, ApplicabilityRule, Phase
import pytest

from hachimoku.engine._instruction import (
    _close_unclosed_fences,
    _summarize_diff,
    _truncate_content,
    build_review_instruction,
    build_selector_context_section,
    build_selector_instruction,
)
from hachimoku.engine._selector import ReferencedContent
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget

_SAMPLE_DIFF = "diff --git a/file.py b/file.py\n+added line"
_SAMPLE_FILE_CONTENT = "--- src/main.py ---\nprint('hello')"

# Issue #170: テスト用の realistic unified diff フィクスチャ
_SINGLE_FILE_DIFF = (
    "diff --git a/src/auth.py b/src/auth.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/src/auth.py\n"
    "+++ b/src/auth.py\n"
    "@@ -1,5 +1,7 @@\n"
    " import os\n"
    "-def old_func():\n"
    "-    pass\n"
    "+def new_func():\n"
    "+    return True\n"
    "+\n"
    "+# Added comment\n"
)

_MULTI_FILE_DIFF = (
    "diff --git a/src/auth.py b/src/auth.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/src/auth.py\n"
    "+++ b/src/auth.py\n"
    "@@ -1,3 +1,4 @@\n"
    " import os\n"
    "+import sys\n"
    " def func():\n"
    "     pass\n"
    "diff --git a/src/config.py b/src/config.py\n"
    "index 2345678..bcdefgh 100644\n"
    "--- a/src/config.py\n"
    "+++ b/src/config.py\n"
    "@@ -1,3 +1,3 @@\n"
    " SETTINGS = {\n"
    '-    "timeout": 30,\n'
    '+    "timeout": 60,\n'
    " }\n"
)

_NEW_FILE_DIFF = (
    "diff --git a/src/new_file.py b/src/new_file.py\n"
    "new file mode 100644\n"
    "index 0000000..1234567\n"
    "--- /dev/null\n"
    "+++ b/src/new_file.py\n"
    "@@ -0,0 +1,3 @@\n"
    "+def hello():\n"
    '+    print("hello")\n'
    "+    return True\n"
)

_DELETED_FILE_DIFF = (
    "diff --git a/src/old_file.py b/src/old_file.py\n"
    "deleted file mode 100644\n"
    "index 1234567..0000000\n"
    "--- a/src/old_file.py\n"
    "+++ /dev/null\n"
    "@@ -1,3 +0,0 @@\n"
    "-def goodbye():\n"
    '-    print("bye")\n'
    "-    return False\n"
)

_RENAMED_FILE_DIFF = (
    "diff --git a/src/old_name.py b/src/new_name.py\n"
    "similarity index 90%\n"
    "rename from src/old_name.py\n"
    "rename to src/new_name.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/src/old_name.py\n"
    "+++ b/src/new_name.py\n"
    "@@ -1,3 +1,3 @@\n"
    " def func():\n"
    '-    return "old"\n'
    '+    return "new"\n'
)

_BINARY_FILE_DIFF = (
    "diff --git a/image.png b/image.png\n"
    "new file mode 100644\n"
    "index 0000000..1234567\n"
    "Binary files /dev/null and b/image.png differ\n"
)

_MULTI_HUNK_DIFF = (
    "diff --git a/src/multi.py b/src/multi.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/src/multi.py\n"
    "+++ b/src/multi.py\n"
    "@@ -1,5 +1,6 @@\n"
    " import os\n"
    "+import sys\n"
    " def func_a():\n"
    "     pass\n"
    " \n"
    "@@ -10,5 +11,6 @@\n"
    " def func_b():\n"
    "-    return None\n"
    "+    return True\n"
    "+    # fixed\n"
)

_NO_NEWLINE_DIFF = (
    "diff --git a/src/no_nl.py b/src/no_nl.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/src/no_nl.py\n"
    "+++ b/src/no_nl.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def func():\n"
    "-    pass\n"
    "\\ No newline at end of file\n"
    "+    return True\n"
    "\\ No newline at end of file\n"
)


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
        instruction = build_review_instruction(target, _SAMPLE_DIFF)
        assert "develop" in instruction

    def test_includes_resolved_content(self) -> None:
        """resolved_content がインストラクションに埋め込まれる。"""
        target = DiffTarget(base_branch="main")
        instruction = build_review_instruction(target, _SAMPLE_DIFF)
        assert _SAMPLE_DIFF in instruction

    def test_no_tool_guidance_for_diff_retrieval(self) -> None:
        """diff 取得のツール使用ガイダンスが含まれない。"""
        target = DiffTarget(base_branch="main")
        instruction = build_review_instruction(target, _SAMPLE_DIFF)
        assert "git merge-base" not in instruction
        assert "git diff" not in instruction


class TestBuildReviewInstructionPR:
    """build_review_instruction の PR モードを検証。"""

    def test_includes_pr_number(self) -> None:
        """PR 番号を含む。"""
        target = PRTarget(pr_number=42)
        instruction = build_review_instruction(target, _SAMPLE_DIFF)
        assert "42" in instruction

    def test_includes_resolved_content(self) -> None:
        """resolved_content がインストラクションに埋め込まれる。"""
        target = PRTarget(pr_number=42)
        instruction = build_review_instruction(target, _SAMPLE_DIFF)
        assert _SAMPLE_DIFF in instruction

    def test_no_tool_guidance_for_diff_retrieval(self) -> None:
        """diff 取得のツール使用ガイダンスが含まれない。"""
        target = PRTarget(pr_number=42)
        instruction = build_review_instruction(target, _SAMPLE_DIFF)
        assert "gh pr diff" not in instruction

    def test_metadata_guidance_still_present(self) -> None:
        """PR メタデータ取得の指示は残る。"""
        target = PRTarget(pr_number=42)
        instruction = build_review_instruction(target, _SAMPLE_DIFF)
        assert "gh pr view" in instruction


class TestBuildReviewInstructionFile:
    """build_review_instruction の file モードを検証。"""

    def test_includes_file_paths(self) -> None:
        """ファイルパスを含む。"""
        target = FileTarget(paths=("src/main.py", "tests/test.py"))
        instruction = build_review_instruction(target, _SAMPLE_FILE_CONTENT)
        assert "src/main.py" in instruction
        assert "tests/test.py" in instruction

    def test_includes_resolved_content(self) -> None:
        """resolved_content がインストラクションに埋め込まれる。"""
        target = FileTarget(paths=("src/main.py",))
        instruction = build_review_instruction(target, _SAMPLE_FILE_CONTENT)
        assert _SAMPLE_FILE_CONTENT in instruction

    def test_no_tool_guidance_for_file_read(self) -> None:
        """ファイル読み込みのツール使用ガイダンスが含まれない。"""
        target = FileTarget(paths=("src/main.py",))
        instruction = build_review_instruction(target, _SAMPLE_FILE_CONTENT)
        assert "Use file tools" not in instruction


class TestBuildReviewInstructionIssue:
    """build_review_instruction の issue_number 付加を検証。"""

    def test_includes_issue_number_when_present(self) -> None:
        """issue_number 指定時に Issue 番号を含む。"""
        target = DiffTarget(base_branch="main", issue_number=123)
        instruction = build_review_instruction(target, _SAMPLE_DIFF)
        assert "123" in instruction

    def test_excludes_issue_when_none(self) -> None:
        """issue_number=None 時に Issue 参照を含まない。"""
        target = DiffTarget(base_branch="main")
        instruction = build_review_instruction(target, _SAMPLE_DIFF)
        assert "#None" not in instruction
        assert "Related Issue" not in instruction


class TestBuildReviewInstructionFileEdgeCases:
    """build_review_instruction の file モードエッジケースを検証（US5-AC3, US5-AC4）。"""

    def test_glob_pattern_included_in_instruction(self) -> None:
        """glob パターンがレビュー指示に含まれる（US5-AC4）。"""
        target = FileTarget(paths=("src/**/*.py",))
        instruction = build_review_instruction(target, _SAMPLE_FILE_CONTENT)
        assert "src/**/*.py" in instruction

    def test_directory_path_included_in_instruction(self) -> None:
        """ディレクトリパスがレビュー指示に含まれる（US5-AC3）。"""
        target = FileTarget(paths=("src/",))
        instruction = build_review_instruction(target, _SAMPLE_FILE_CONTENT)
        assert "src/" in instruction

    def test_mixed_path_types_all_included(self) -> None:
        """ファイル・ディレクトリ・glob の全パスがレビュー指示に含まれる。"""
        target = FileTarget(paths=("src/main.py", "tests/", "**/*.md"))
        instruction = build_review_instruction(target, _SAMPLE_FILE_CONTENT)
        assert "src/main.py" in instruction
        assert "tests/" in instruction
        assert "**/*.md" in instruction

    def test_paths_listed_with_bullet_format(self) -> None:
        """各パスが '- ' プレフィックスのリスト形式で表示される。"""
        target = FileTarget(paths=("a.py", "b/"))
        instruction = build_review_instruction(target, _SAMPLE_FILE_CONTENT)
        assert "- a.py" in instruction
        assert "- b/" in instruction


class TestBuildReviewInstructionIssueCombinations:
    """全モードにおける issue_number 有無の組み合わせを検証（FR-RE-011）。"""

    def test_diff_with_issue_includes_both(self) -> None:
        """diff モード + issue_number で両方含まれる。"""
        target = DiffTarget(base_branch="main", issue_number=42)
        instruction = build_review_instruction(target, _SAMPLE_DIFF)
        assert "main" in instruction
        assert "#42" in instruction
        assert "Related Issue" in instruction

    def test_pr_with_issue_includes_both(self) -> None:
        """PR モード + issue_number で両方含まれる。"""
        target = PRTarget(pr_number=10, issue_number=42)
        instruction = build_review_instruction(target, _SAMPLE_DIFF)
        assert "#10" in instruction
        assert "#42" in instruction

    def test_file_with_issue_includes_both(self) -> None:
        """file モード + issue_number でパスと issue 両方含まれる。"""
        target = FileTarget(paths=("src/main.py",), issue_number=42)
        instruction = build_review_instruction(target, _SAMPLE_FILE_CONTENT)
        assert "src/main.py" in instruction
        assert "#42" in instruction

    def test_pr_without_issue_excludes_related_issue(self) -> None:
        """PR モードで issue_number=None の場合 Related Issue を含まない。"""
        target = PRTarget(pr_number=10)
        instruction = build_review_instruction(target, _SAMPLE_DIFF)
        assert "Related Issue" not in instruction

    def test_file_without_issue_excludes_related_issue(self) -> None:
        """file モードで issue_number=None の場合 Related Issue を含まない。"""
        target = FileTarget(paths=("a.py",))
        instruction = build_review_instruction(target, _SAMPLE_FILE_CONTENT)
        assert "Related Issue" not in instruction


# =============================================================================
# build_selector_instruction
# =============================================================================


class TestBuildSelectorInstruction:
    """build_selector_instruction 関数のテスト。"""

    def test_includes_mode_header(self) -> None:
        """モード固有のヘッダー（base_branch 名）を含む。"""
        target = DiffTarget(base_branch="main")
        instruction = build_selector_instruction(target, [], _SINGLE_FILE_DIFF)
        assert "main" in instruction

    def test_diff_target_contains_summary_not_full_diff(self) -> None:
        """DiffTarget: フル diff ではなくサマリーが含まれる（Issue #170）。"""
        target = DiffTarget(base_branch="main")
        instruction = build_selector_instruction(target, [], _SINGLE_FILE_DIFF)
        # サマリーフォーマットが含まれる
        assert "Diff Summary" in instruction
        assert "src/auth.py" in instruction
        # フル diff のハンクヘッダーは含まれない
        assert "@@ -1,5 +1,7 @@" not in instruction

    def test_pr_target_contains_summary_not_full_diff(self) -> None:
        """PRTarget: フル diff ではなくサマリーが含まれる（Issue #170）。"""
        target = PRTarget(pr_number=42)
        instruction = build_selector_instruction(target, [], _SINGLE_FILE_DIFF)
        assert "Diff Summary" in instruction
        assert "@@ -1,5 +1,7 @@" not in instruction

    def test_file_target_contains_full_content(self) -> None:
        """FileTarget: フルコンテンツがそのまま含まれる（サマリーなし）。"""
        target = FileTarget(paths=("src/main.py",))
        instruction = build_selector_instruction(target, [], _SAMPLE_FILE_CONTENT)
        assert _SAMPLE_FILE_CONTENT in instruction
        assert "Diff Summary" not in instruction

    def test_includes_agent_name_and_description(self) -> None:
        """エージェント名と説明を含む。"""
        target = DiffTarget(base_branch="main")
        agent = _make_agent(name="code-reviewer", description="Code quality check")
        instruction = build_selector_instruction(target, [agent], _SINGLE_FILE_DIFF)
        assert "code-reviewer" in instruction
        assert "Code quality check" in instruction

    def test_includes_multiple_agents(self) -> None:
        """複数エージェントの情報を含む。"""
        target = PRTarget(pr_number=10)
        agents = [
            _make_agent(name="reviewer-a", description="Desc A"),
            _make_agent(name="reviewer-b", description="Desc B"),
        ]
        instruction = build_selector_instruction(target, agents, _SINGLE_FILE_DIFF)
        assert "reviewer-a" in instruction
        assert "reviewer-b" in instruction

    def test_empty_agents_list_handled(self) -> None:
        """空のエージェントリストでも例外なく動作する。"""
        target = PRTarget(pr_number=10)
        instruction = build_selector_instruction(target, [], _SINGLE_FILE_DIFF)
        assert isinstance(instruction, str)
        assert len(instruction) > 0

    def test_diff_target_with_issue_number(self) -> None:
        """DiffTarget + issue_number でサマリーと Issue 参照の両方を含む。"""
        target = DiffTarget(base_branch="main", issue_number=42)
        instruction = build_selector_instruction(target, [], _SINGLE_FILE_DIFF)
        assert "Diff Summary" in instruction
        assert "#42" in instruction
        assert "Related Issue" in instruction

    def test_diff_target_with_empty_diff(self) -> None:
        """DiffTarget + 空 diff で空コンテンツが渡されても動作する。"""
        target = DiffTarget(base_branch="main")
        instruction = build_selector_instruction(target, [], "")
        assert isinstance(instruction, str)
        assert "main" in instruction

    def test_diff_target_with_non_diff_content(self) -> None:
        """DiffTarget + diff --git ヘッダーなしのコンテンツは元のまま渡される。"""
        target = DiffTarget(base_branch="main")
        raw_content = "some non-diff content\nwithout git headers"
        instruction = build_selector_instruction(target, [], raw_content)
        # _summarize_diff が空を返すため、元のコンテンツがそのまま渡される
        assert raw_content in instruction


# =============================================================================
# _summarize_diff（Issue #170）
# =============================================================================


class TestSummarizeDiffEmpty:
    """_summarize_diff の空入力テスト。Issue #170."""

    def test_empty_content_returns_empty(self) -> None:
        """空の diff → 空文字列を返す。"""
        assert _summarize_diff("") == ""


class TestSummarizeDiffSingleFile:
    """_summarize_diff の単一ファイル diff テスト。Issue #170."""

    def test_file_path_included(self) -> None:
        """ファイルパスがサマリーに含まれる。"""
        result = _summarize_diff(_SINGLE_FILE_DIFF)
        assert "src/auth.py" in result

    def test_addition_count(self) -> None:
        """追加行数が正しくカウントされる（+++ ヘッダーを除外）。"""
        result = _summarize_diff(_SINGLE_FILE_DIFF)
        # _SINGLE_FILE_DIFF has 4 additions: new_func, return True, empty, comment
        assert "+4" in result

    def test_deletion_count(self) -> None:
        """削除行数が正しくカウントされる（--- ヘッダーを除外）。"""
        result = _summarize_diff(_SINGLE_FILE_DIFF)
        # _SINGLE_FILE_DIFF has 2 deletions: old_func, pass
        assert "-2" in result

    def test_summary_header(self) -> None:
        """サマリーヘッダーが含まれる。"""
        result = _summarize_diff(_SINGLE_FILE_DIFF)
        assert "Diff Summary" in result

    def test_preview_lines_included(self) -> None:
        """変更行のプレビューが含まれる。"""
        result = _summarize_diff(_SINGLE_FILE_DIFF)
        assert "+def new_func():" in result

    def test_hunk_headers_excluded(self) -> None:
        """@@ ハンクヘッダーがサマリーに含まれない。"""
        result = _summarize_diff(_SINGLE_FILE_DIFF)
        assert "@@" not in result

    def test_total_file_count(self) -> None:
        """ファイル数の集計が含まれる。"""
        result = _summarize_diff(_SINGLE_FILE_DIFF)
        assert "1 file(s) changed" in result


class TestSummarizeDiffMultipleFiles:
    """_summarize_diff の複数ファイル diff テスト。Issue #170."""

    def test_all_files_listed(self) -> None:
        """全ファイルがサマリーに含まれる。"""
        result = _summarize_diff(_MULTI_FILE_DIFF)
        assert "src/auth.py" in result
        assert "src/config.py" in result

    def test_file_count(self) -> None:
        """ファイル数の集計が正しい。"""
        result = _summarize_diff(_MULTI_FILE_DIFF)
        assert "2 file(s) changed" in result


class TestSummarizeDiffNewFile:
    """_summarize_diff の新規ファイル diff テスト。Issue #170."""

    def test_new_file_status(self) -> None:
        """新規ファイルが 'new' ステータスで表示される。"""
        result = _summarize_diff(_NEW_FILE_DIFF)
        assert "new" in result.lower()
        assert "src/new_file.py" in result


class TestSummarizeDiffDeletedFile:
    """_summarize_diff の削除ファイル diff テスト。Issue #170."""

    def test_deleted_file_status(self) -> None:
        """削除ファイルが 'deleted' ステータスで表示される。"""
        result = _summarize_diff(_DELETED_FILE_DIFF)
        assert "deleted" in result.lower()
        assert "src/old_file.py" in result


class TestSummarizeDiffRenamedFile:
    """_summarize_diff のリネームファイル diff テスト。Issue #170."""

    def test_renamed_file_shows_both_paths(self) -> None:
        """リネームファイルが old → new の形式で表示される。"""
        result = _summarize_diff(_RENAMED_FILE_DIFF)
        assert "src/old_name.py" in result
        assert "src/new_name.py" in result


class TestSummarizeDiffBinaryFile:
    """_summarize_diff のバイナリファイル diff テスト。Issue #170."""

    def test_binary_file_status(self) -> None:
        """バイナリファイルが 'binary' ステータスで表示される。"""
        result = _summarize_diff(_BINARY_FILE_DIFF)
        assert "binary" in result.lower()
        assert "image.png" in result

    def test_binary_file_no_diff_preview(self) -> None:
        """バイナリファイルにはプレビュー内容が含まれない。"""
        result = _summarize_diff(_BINARY_FILE_DIFF)
        assert "differ" not in result


class TestSummarizeDiffPreviewLimit:
    """_summarize_diff のプレビュー行数制限テスト。Issue #170."""

    def test_preview_lines_limited(self) -> None:
        """preview_lines パラメータでプレビュー行数が制限される。"""
        result = _summarize_diff(_SINGLE_FILE_DIFF, preview_lines=2)
        # _SINGLE_FILE_DIFF has 6 changed lines (4 additions + 2 deletions).
        # With preview_lines=2, only the first 2 changed lines appear.
        # Count actual diff-prefixed lines in the preview section
        preview_section = (
            result.split("Change Preview")[1] if "Change Preview" in result else ""
        )
        diff_lines = [
            line
            for line in preview_section.splitlines()
            if line.startswith("+") or line.startswith("-")
        ]
        assert len(diff_lines) == 2

    def test_custom_preview_lines_zero(self) -> None:
        """preview_lines=0 でプレビューセクションが省略される。"""
        result = _summarize_diff(_SINGLE_FILE_DIFF, preview_lines=0)
        assert "Change Preview" not in result


class TestSummarizeDiffMultiHunk:
    """_summarize_diff のマルチハンク diff テスト。Issue #170."""

    def test_multi_hunk_counts_accumulated(self) -> None:
        """複数ハンクのファイルで行数カウントが累積される。"""
        result = _summarize_diff(_MULTI_HUNK_DIFF)
        # _MULTI_HUNK_DIFF: hunk1 adds 1 (import sys), hunk2 adds 2 (return True, # fixed) deletes 1 (return None)
        assert "+3" in result
        assert "-1" in result


class TestSummarizeDiffNoNewline:
    """_summarize_diff の No newline at end of file テスト。Issue #170."""

    def test_no_newline_marker_excluded_from_counts(self) -> None:
        """'\\\\No newline at end of file' がカウントに含まれない。"""
        result = _summarize_diff(_NO_NEWLINE_DIFF)
        # 1 deletion (-    pass) and 1 addition (+    return True)
        assert "+1" in result
        assert "-1" in result


class TestSummarizeDiffToolGuidance:
    """_summarize_diff のツールガイダンスノートテスト。Issue #170."""

    def test_tool_guidance_included(self) -> None:
        """git_read ツール使用のガイダンスノートが含まれる。"""
        result = _summarize_diff(_SINGLE_FILE_DIFF)
        assert "git_read" in result


# =============================================================================
# build_selector_context_section（Issue #148）
# =============================================================================


class TestBuildSelectorContextSectionEmpty:
    """build_selector_context_section の空メタデータテスト。"""

    def test_all_empty_returns_empty_string(self) -> None:
        """全メタデータが空の場合、空文字列を返す。"""
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
        )
        assert result == ""


class TestBuildSelectorContextSectionChangeIntent:
    """build_selector_context_section の change_intent テスト。"""

    def test_change_intent_included(self) -> None:
        """change_intent が設定されている場合、セクションに含まれる。"""
        result = build_selector_context_section(
            change_intent="Fix authentication bug",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
        )
        assert "## Selector Analysis Context" in result
        assert "### Change Intent" in result
        assert "Fix authentication bug" in result

    def test_other_sections_excluded_when_only_intent(self) -> None:
        """change_intent のみ設定時、他セクションは含まれない。"""
        result = build_selector_context_section(
            change_intent="Fix bug",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
        )
        assert "### Affected Files" not in result
        assert "### Relevant Project Conventions" not in result
        assert "### Issue Context" not in result


class TestBuildSelectorContextSectionAffectedFiles:
    """build_selector_context_section の affected_files テスト。"""

    def test_affected_files_listed(self) -> None:
        """affected_files がリスト形式で含まれる。"""
        result = build_selector_context_section(
            change_intent="",
            affected_files=["src/auth.py", "src/config.py"],
            relevant_conventions=[],
            issue_context="",
        )
        assert "### Affected Files (Outside Diff)" in result
        assert "- src/auth.py" in result
        assert "- src/config.py" in result


class TestBuildSelectorContextSectionConventions:
    """build_selector_context_section の relevant_conventions テスト。"""

    def test_conventions_listed(self) -> None:
        """relevant_conventions がリスト形式で含まれる。"""
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=["Art.4: Simplicity", "TDD strict"],
            issue_context="",
        )
        assert "### Relevant Project Conventions" in result
        assert "- Art.4: Simplicity" in result
        assert "- TDD strict" in result


class TestBuildSelectorContextSectionIssueContext:
    """build_selector_context_section の issue_context テスト。"""

    def test_issue_context_included(self) -> None:
        """issue_context が設定されている場合、セクションに含まれる。"""
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=[],
            issue_context="Issue #42: Login fails for OAuth users",
        )
        assert "### Issue Context" in result
        assert "Issue #42: Login fails for OAuth users" in result


class TestBuildSelectorContextSectionCombinations:
    """build_selector_context_section の組み合わせテスト。"""

    def test_all_metadata_populated(self) -> None:
        """全メタデータが設定されている場合、全セクションが含まれる。"""
        result = build_selector_context_section(
            change_intent="Refactor auth module",
            affected_files=["src/auth.py"],
            relevant_conventions=["TDD strict"],
            issue_context="Issue #42",
        )
        assert "### Change Intent" in result
        assert "### Affected Files (Outside Diff)" in result
        assert "### Relevant Project Conventions" in result
        assert "### Issue Context" in result

    def test_partial_metadata_only_includes_populated(self) -> None:
        """一部のみ設定時、設定されたセクションのみ含まれる。"""
        result = build_selector_context_section(
            change_intent="Fix bug",
            affected_files=["src/auth.py"],
            relevant_conventions=[],
            issue_context="",
        )
        assert "### Change Intent" in result
        assert "### Affected Files (Outside Diff)" in result
        assert "### Relevant Project Conventions" not in result
        assert "### Issue Context" not in result


# =============================================================================
# build_selector_context_section — referenced_content（Issue #159）
# =============================================================================


class TestBuildSelectorContextSectionReferencedContent:
    """build_selector_context_section の referenced_content テスト。

    Issue #159: diff 内で参照されている外部リソースの取得結果をレンダリング。
    """

    def test_referenced_content_section_included(self) -> None:
        """referenced_content が非空の場合、### Referenced Content セクションが含まれる。"""
        ref = ReferencedContent(
            reference_type="issue",
            reference_id="#152",
            content="Issue body text",
        )
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
            referenced_content=[ref],
        )
        assert "## Selector Analysis Context" in result
        assert "### Referenced Content" in result

    def test_referenced_content_type_and_id_in_heading(self) -> None:
        """reference_type と reference_id が見出しフォーマットでレンダリングされる。"""
        ref = ReferencedContent(
            reference_type="issue",
            reference_id="#152",
            content="Issue body text",
        )
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
            referenced_content=[ref],
        )
        assert "#### [issue] #152" in result

    def test_referenced_content_body_in_code_block(self) -> None:
        """content がコードブロック内に含まれる。"""
        ref = ReferencedContent(
            reference_type="file",
            reference_id="src/foo.py",
            content="def foo():\n    pass",
        )
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
            referenced_content=[ref],
        )
        assert "```" in result
        assert "def foo():\n    pass" in result

    def test_multiple_references_all_rendered(self) -> None:
        """複数の参照が全てレンダリングされる。"""
        refs = [
            ReferencedContent(
                reference_type="issue",
                reference_id="#152",
                content="Issue body",
            ),
            ReferencedContent(
                reference_type="file",
                reference_id="src/foo.py",
                content="file content",
            ),
        ]
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
            referenced_content=refs,
        )
        assert "#152" in result
        assert "src/foo.py" in result
        assert "Issue body" in result
        assert "file content" in result

    def test_content_with_triple_backticks_uses_longer_fence(self) -> None:
        """content に ``` が含まれる場合、より長いフェンスが使用される。"""
        ref = ReferencedContent(
            reference_type="file",
            reference_id="README.md",
            content="Example:\n```python\nprint('hello')\n```",
        )
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
            referenced_content=[ref],
        )
        assert "````" in result
        assert "```python" in result

    def test_empty_referenced_content_excluded(self) -> None:
        """空リストの場合 Referenced Content セクションが含まれない。"""
        result = build_selector_context_section(
            change_intent="Fix bug",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
            referenced_content=[],
        )
        assert "### Referenced Content" not in result

    def test_referenced_content_with_other_metadata(self) -> None:
        """他のメタデータとの組み合わせで全セクションが正しく出力される。"""
        ref = ReferencedContent(
            reference_type="spec",
            reference_id="specs/005/spec.md",
            content="FR-RE-002: Pipeline spec",
        )
        result = build_selector_context_section(
            change_intent="Refactor engine",
            affected_files=["src/engine.py"],
            relevant_conventions=["TDD strict"],
            issue_context="Issue #42",
            referenced_content=[ref],
        )
        assert "### Change Intent" in result
        assert "### Affected Files (Outside Diff)" in result
        assert "### Relevant Project Conventions" in result
        assert "### Issue Context" in result
        assert "### Referenced Content" in result
        assert "specs/005/spec.md" in result


# ── Issue #172: コンテンツ truncation ──────────────────────────────


class TestCloseUnclosedFences:
    """_close_unclosed_fences() のテスト。Issue #172."""

    def test_no_fences(self) -> None:
        """フェンスを含まないテキストは変更されない。"""
        text = "plain text\nwithout fences"
        assert _close_unclosed_fences(text) == text

    def test_paired_backtick_fence(self) -> None:
        """開始・閉鎖ペアが揃っている場合は変更されない。"""
        text = "```python\nprint('hi')\n```"
        assert _close_unclosed_fences(text) == text

    def test_unclosed_backtick_fence(self) -> None:
        """未閉鎖の ``` フェンスが閉じられる。"""
        text = "intro\n```python\ncode here"
        result = _close_unclosed_fences(text)
        assert result == "intro\n```python\ncode here\n```"

    def test_unclosed_tilde_fence(self) -> None:
        """未閉鎖の ~~~ フェンスが閉じられる。"""
        text = "intro\n~~~\ncode here"
        result = _close_unclosed_fences(text)
        assert result == "intro\n~~~\ncode here\n~~~"

    def test_extended_backtick_fence(self) -> None:
        """4+ backtick フェンスが正しく閉じられる。"""
        text = "````\ncode with ``` inside"
        result = _close_unclosed_fences(text)
        assert result == "````\ncode with ``` inside\n````"

    def test_mixed_fence_types(self) -> None:
        """``` 閉鎖済み + ~~~ 未閉鎖 のケース。"""
        text = "```\nblock1\n```\n~~~\nblock2 truncated"
        result = _close_unclosed_fences(text)
        assert result.endswith("\n~~~")

    def test_backtick_inside_tilde_fence_ignored(self) -> None:
        """~~~ 内の ``` はリテラルとして無視される。"""
        text = "~~~\n```\nstill inside tilde\n"
        result = _close_unclosed_fences(text)
        # ~~~ が未閉鎖 → ~~~ で閉じる（``` は無関係）
        assert result.endswith("\n~~~")


class TestTruncateContent:
    """_truncate_content() のテスト。Issue #172."""

    def test_short_content_unchanged(self) -> None:
        """上限以下のコンテンツは変更されない。"""
        content = "short text"
        assert _truncate_content(content, 100) == content

    def test_exact_limit_unchanged(self) -> None:
        """ちょうど上限のコンテンツは変更されない。"""
        content = "A" * 100
        assert _truncate_content(content, 100) == content

    def test_over_limit_truncated(self) -> None:
        """上限超過時に切り詰められマーカーが付く。"""
        content = "A" * 200
        result = _truncate_content(content, 100)
        assert result.startswith("A" * 100)
        assert "... (truncated, original: 200 chars)" in result

    def test_marker_format(self) -> None:
        """マーカーの形式が正しい。"""
        content = "X" * 150
        result = _truncate_content(content, 50)
        assert result.endswith("... (truncated, original: 150 chars)")

    def test_unclosed_fence_closed_before_marker(self) -> None:
        """未閉鎖フェンスが閉じられた後にマーカーが付く。"""
        # 30文字でカット → ```python\n が残り未閉鎖
        content = "```python\nlong code line\n" + "X" * 100
        result = _truncate_content(content, 30)
        marker_pos = result.index("... (truncated")
        fence_close_pos = result.rindex("```", 0, marker_pos)
        assert fence_close_pos > 0

    def test_closed_fence_no_extra_closing(self) -> None:
        """閉鎖済みフェンスに余分な閉鎖を追加しない。"""
        content = "```\ncode\n```\n" + "X" * 100
        result = _truncate_content(content, 100)
        # ``` の出現回数: 元の開始(1) + 元の閉鎖(1) のみ（truncation前に閉じている）
        truncated_before_marker = result.split("\n\n... (truncated")[0]
        assert truncated_before_marker.count("```") == 2

    def test_zero_max_chars_raises(self) -> None:
        """max_chars=0 で ValueError が発生する。"""
        with pytest.raises(ValueError, match="max_chars"):
            _truncate_content("content", 0)

    def test_negative_max_chars_raises(self) -> None:
        """負の max_chars で ValueError が発生する。"""
        with pytest.raises(ValueError, match="max_chars"):
            _truncate_content("content", -1)


class TestBuildSelectorContextSectionTruncation:
    """build_selector_context_section の truncation 統合テスト。Issue #172."""

    def test_short_content_not_truncated(self) -> None:
        """上限以下の referenced_content は変更されない。"""
        ref = ReferencedContent(
            reference_type="issue",
            reference_id="#100",
            content="Short body",
        )
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
            referenced_content=[ref],
            max_referenced_content_chars=100,
        )
        assert "Short body" in result
        assert "truncated" not in result

    def test_long_content_truncated(self) -> None:
        """上限超過の referenced_content が truncation される。"""
        content = "B" * 200
        ref = ReferencedContent(
            reference_type="file",
            reference_id="spec.md",
            content=content,
        )
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
            referenced_content=[ref],
            max_referenced_content_chars=50,
        )
        assert "... (truncated, original: 200 chars)" in result
        assert content not in result

    def test_dynamic_fence_accounts_for_truncation_closing(self) -> None:
        """Truncation で追加された ``` が動的フェンス生成で考慮される。"""
        # 未閉鎖 ``` → truncation で ``` を追加 → 動的フェンスは ```` に昇格
        content = "```python\n" + "X" * 100
        ref = ReferencedContent(
            reference_type="file",
            reference_id="code.py",
            content=content,
        )
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
            referenced_content=[ref],
            max_referenced_content_chars=30,
        )
        assert "````" in result

    def test_multiple_refs_each_truncated(self) -> None:
        """複数の referenced_content が各々独立に truncation される。"""
        refs = [
            ReferencedContent(
                reference_type="issue", reference_id="#1", content="A" * 200
            ),
            ReferencedContent(
                reference_type="file", reference_id="f.py", content="B" * 200
            ),
        ]
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
            referenced_content=refs,
            max_referenced_content_chars=50,
        )
        assert result.count("... (truncated") == 2

    def test_default_max_chars_applied(self) -> None:
        """max_referenced_content_chars 省略時にデフォルト 5000 が適用される。"""
        content = "Z" * 6000
        ref = ReferencedContent(
            reference_type="spec",
            reference_id="spec.md",
            content=content,
        )
        result = build_selector_context_section(
            change_intent="",
            affected_files=[],
            relevant_conventions=[],
            issue_context="",
            referenced_content=[ref],
        )
        assert "... (truncated, original: 6000 chars)" in result
