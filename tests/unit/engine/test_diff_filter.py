"""差分フィルタリングのテスト。

Issue #171: エージェント別 file_patterns ベースの差分フィルタリング。
"""

from hachimoku.engine._diff_filter import filter_diff_by_file_patterns

# =============================================================================
# テスト用 diff フィクスチャ
# =============================================================================

_PY_FILE_DIFF = (
    "diff --git a/src/auth.py b/src/auth.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/src/auth.py\n"
    "+++ b/src/auth.py\n"
    "@@ -1,3 +1,4 @@\n"
    " import os\n"
    "+import sys\n"
    " def func():\n"
    "     pass\n"
)

_TS_FILE_DIFF = (
    "diff --git a/src/app.ts b/src/app.ts\n"
    "index 2345678..bcdefgh 100644\n"
    "--- a/src/app.ts\n"
    "+++ b/src/app.ts\n"
    "@@ -1,3 +1,3 @@\n"
    " const x = 1;\n"
    "-const y = 2;\n"
    "+const y = 3;\n"
)

_TEST_FILE_DIFF = (
    "diff --git a/tests/test_auth.py b/tests/test_auth.py\n"
    "index 3456789..cdefghi 100644\n"
    "--- a/tests/test_auth.py\n"
    "+++ b/tests/test_auth.py\n"
    "@@ -1,2 +1,3 @@\n"
    " def test_login():\n"
    "+    assert True\n"
    "     pass\n"
)

_MD_FILE_DIFF = (
    "diff --git a/README.md b/README.md\n"
    "index 4567890..defghij 100644\n"
    "--- a/README.md\n"
    "+++ b/README.md\n"
    "@@ -1,2 +1,3 @@\n"
    " # Project\n"
    "+\n"
    " Description\n"
)

_NEW_FILE_DIFF = (
    "diff --git a/src/new_module.py b/src/new_module.py\n"
    "new file mode 100644\n"
    "index 0000000..1234567\n"
    "--- /dev/null\n"
    "+++ b/src/new_module.py\n"
    "@@ -0,0 +1,2 @@\n"
    "+def hello():\n"
    "+    pass\n"
)

_DELETED_FILE_DIFF = (
    "diff --git a/src/old_module.ts b/src/old_module.ts\n"
    "deleted file mode 100644\n"
    "index 1234567..0000000\n"
    "--- a/src/old_module.ts\n"
    "+++ /dev/null\n"
    "@@ -1,2 +0,0 @@\n"
    "-export const x = 1;\n"
    "-export const y = 2;\n"
)

_RENAMED_FILE_DIFF = (
    "diff --git a/src/old_name.py b/src/new_name.py\n"
    "similarity index 90%\n"
    "rename from src/old_name.py\n"
    "rename to src/new_name.py\n"
    "index 1234567..abcdefg 100644\n"
    "--- a/src/old_name.py\n"
    "+++ b/src/new_name.py\n"
    "@@ -1,2 +1,2 @@\n"
    " def func():\n"
    '-    return "old"\n'
    '+    return "new"\n'
)

_BINARY_FILE_DIFF = (
    "diff --git a/assets/image.png b/assets/image.png\n"
    "new file mode 100644\n"
    "index 0000000..1234567\n"
    "Binary files /dev/null and b/assets/image.png differ\n"
)

# 複数ファイル混合 diff（py + ts + md）
_MULTI_FILE_DIFF = _PY_FILE_DIFF + _TS_FILE_DIFF + _MD_FILE_DIFF

# テスト + ソース混合 diff
_TEST_AND_SOURCE_DIFF = _PY_FILE_DIFF + _TEST_FILE_DIFF + _TS_FILE_DIFF

# 全タイプ混合 diff
_ALL_TYPES_DIFF = (
    _PY_FILE_DIFF
    + _TS_FILE_DIFF
    + _TEST_FILE_DIFF
    + _MD_FILE_DIFF
    + _NEW_FILE_DIFF
    + _DELETED_FILE_DIFF
    + _RENAMED_FILE_DIFF
    + _BINARY_FILE_DIFF
)


# =============================================================================
# filter_diff_by_file_patterns — 基本動作
# =============================================================================


class TestFilterDiffBasic:
    """filter_diff_by_file_patterns の基本動作テスト。"""

    def test_single_file_matching_pattern(self) -> None:
        """単一ファイル diff がパターンにマッチ → そのまま返す。"""
        result = filter_diff_by_file_patterns(_PY_FILE_DIFF, ("*.py",))
        assert "src/auth.py" in result
        assert "+import sys" in result

    def test_single_file_not_matching_pattern(self) -> None:
        """単一ファイル diff がパターンに非マッチ → diff 全文にリカバリ。"""
        result = filter_diff_by_file_patterns(_PY_FILE_DIFF, ("*.ts",))
        # マッチなし → リカバリで全文返却
        assert result == _PY_FILE_DIFF

    def test_multi_file_partial_match(self) -> None:
        """複数ファイル diff から一部がマッチ → マッチ分のみ返す。"""
        result = filter_diff_by_file_patterns(_MULTI_FILE_DIFF, ("*.py",))
        assert "src/auth.py" in result
        assert "src/app.ts" not in result
        assert "README.md" not in result

    def test_multi_file_all_match(self) -> None:
        """全ファイルがマッチ → diff 全文を返す。"""
        result = filter_diff_by_file_patterns(
            _MULTI_FILE_DIFF, ("*.py", "*.ts", "*.md")
        )
        assert "src/auth.py" in result
        assert "src/app.ts" in result
        assert "README.md" in result

    def test_multi_file_no_match_recovers(self) -> None:
        """マッチなし → diff 全文にリカバリ。"""
        result = filter_diff_by_file_patterns(_MULTI_FILE_DIFF, ("*.java",))
        assert result == _MULTI_FILE_DIFF


# =============================================================================
# filter_diff_by_file_patterns — 空入力・非 diff テキスト
# =============================================================================


class TestFilterDiffEdgeCases:
    """filter_diff_by_file_patterns のエッジケーステスト。"""

    def test_empty_diff_returns_empty(self) -> None:
        """空文字列 → 空文字列。"""
        assert filter_diff_by_file_patterns("", ("*.py",)) == ""

    def test_whitespace_only_returns_as_is(self) -> None:
        """空白のみ → そのまま返す。"""
        result = filter_diff_by_file_patterns("  \n  \n", ("*.py",))
        assert result == "  \n  \n"

    def test_non_diff_text_returns_as_is(self) -> None:
        """diff --git ヘッダーのない通常テキスト → そのまま返す。"""
        text = "some regular text\nwithout diff headers"
        result = filter_diff_by_file_patterns(text, ("*.py",))
        assert result == text

    def test_empty_patterns_returns_full_diff(self) -> None:
        """空パターンタプル → diff 全文を返す。"""
        result = filter_diff_by_file_patterns(_MULTI_FILE_DIFF, ())
        assert result == _MULTI_FILE_DIFF


# =============================================================================
# filter_diff_by_file_patterns — basename マッチング
# =============================================================================


class TestFilterDiffBasenameMatching:
    """basename マッチングの検証。fnmatch はパスではなく basename に適用される。"""

    def test_wildcard_matches_nested_file(self) -> None:
        """*.py が src/auth.py（ネストしたパス）にマッチする。"""
        result = filter_diff_by_file_patterns(_PY_FILE_DIFF, ("*.py",))
        assert "src/auth.py" in result

    def test_prefix_pattern_matches(self) -> None:
        """test_*.py が tests/test_auth.py にマッチする。"""
        result = filter_diff_by_file_patterns(_TEST_FILE_DIFF, ("test_*.py",))
        assert "tests/test_auth.py" in result

    def test_prefix_pattern_excludes_non_test(self) -> None:
        """test_*.py が src/auth.py にマッチしない。"""
        result = filter_diff_by_file_patterns(_TEST_AND_SOURCE_DIFF, ("test_*.py",))
        assert "tests/test_auth.py" in result
        assert "src/auth.py" not in result
        assert "src/app.ts" not in result

    def test_deeply_nested_path(self) -> None:
        """深いネストのパスでも basename マッチが動作する。"""
        deep_diff = (
            "diff --git a/src/deep/nested/module.py b/src/deep/nested/module.py\n"
            "index 1234567..abcdefg 100644\n"
            "--- a/src/deep/nested/module.py\n"
            "+++ b/src/deep/nested/module.py\n"
            "@@ -1,1 +1,2 @@\n"
            " x = 1\n"
            "+y = 2\n"
        )
        result = filter_diff_by_file_patterns(deep_diff, ("*.py",))
        assert "src/deep/nested/module.py" in result


# =============================================================================
# filter_diff_by_file_patterns — 複数パターン
# =============================================================================


class TestFilterDiffMultiplePatterns:
    """複数パターンの OR マッチング検証。"""

    def test_two_patterns_match_respective_files(self) -> None:
        """["*.py", "*.ts"] が py と ts ファイルの両方にマッチする。"""
        result = filter_diff_by_file_patterns(_MULTI_FILE_DIFF, ("*.py", "*.ts"))
        assert "src/auth.py" in result
        assert "src/app.ts" in result
        assert "README.md" not in result

    def test_overlapping_patterns(self) -> None:
        """複数パターンが同一ファイルにマッチしても重複しない。"""
        result = filter_diff_by_file_patterns(_PY_FILE_DIFF, ("*.py", "auth.*"))
        # 同じファイルが2回出現しない
        assert result.count("diff --git") == 1


# =============================================================================
# filter_diff_by_file_patterns — ファイルステータス別
# =============================================================================


class TestFilterDiffFileStatuses:
    """新規・削除・リネーム・バイナリファイルのフィルタリング検証。"""

    def test_new_file_matched(self) -> None:
        """新規ファイルがパターンにマッチする。"""
        result = filter_diff_by_file_patterns(_NEW_FILE_DIFF, ("*.py",))
        assert "src/new_module.py" in result

    def test_deleted_file_matched(self) -> None:
        """削除ファイルがパターンにマッチする。"""
        result = filter_diff_by_file_patterns(_DELETED_FILE_DIFF, ("*.ts",))
        assert "src/old_module.ts" in result

    def test_renamed_file_matched_by_new_name(self) -> None:
        """リネームファイルが新しい名前（b/側）でマッチする。"""
        result = filter_diff_by_file_patterns(_RENAMED_FILE_DIFF, ("new_name.*",))
        assert "src/new_name.py" in result

    def test_binary_file_matched(self) -> None:
        """バイナリファイルがパターンにマッチする。"""
        result = filter_diff_by_file_patterns(_BINARY_FILE_DIFF, ("*.png",))
        assert "assets/image.png" in result

    def test_binary_file_excluded(self) -> None:
        """バイナリファイルがパターンに非マッチ → 除外。"""
        combined = _PY_FILE_DIFF + _BINARY_FILE_DIFF
        result = filter_diff_by_file_patterns(combined, ("*.py",))
        assert "src/auth.py" in result
        assert "assets/image.png" not in result


# =============================================================================
# filter_diff_by_file_patterns — 実践的パターン
# =============================================================================


class TestFilterDiffPracticalPatterns:
    """ビルトインエージェントで実際に使用されるパターンの検証。"""

    def test_pr_test_analyzer_patterns(self) -> None:
        """pr-test-analyzer の file_patterns でテストファイルのみ抽出。"""
        patterns = (
            "test_*.py",
            "*_test.py",
            "*.test.ts",
            "*.test.js",
            "*.spec.ts",
            "*.spec.js",
        )
        result = filter_diff_by_file_patterns(_TEST_AND_SOURCE_DIFF, patterns)
        assert "tests/test_auth.py" in result
        assert "src/auth.py" not in result
        assert "src/app.ts" not in result

    def test_type_design_analyzer_patterns(self) -> None:
        """type-design-analyzer の file_patterns で py/ts/tsx のみ抽出。"""
        patterns = ("*.py", "*.ts", "*.tsx")
        result = filter_diff_by_file_patterns(_ALL_TYPES_DIFF, patterns)
        assert "src/auth.py" in result
        assert "src/app.ts" in result
        assert "src/new_module.py" in result
        assert "src/old_module.ts" in result
        assert "src/new_name.py" in result
        assert "README.md" not in result
        assert "assets/image.png" not in result


# =============================================================================
# filter_diff_by_file_patterns — diff 整合性
# =============================================================================


class TestFilterDiffIntegrity:
    """フィルタリング後の diff が有効な unified diff フォーマットを維持する検証。"""

    def test_filtered_diff_starts_with_diff_header(self) -> None:
        """フィルタ後の diff が diff --git で始まる。"""
        result = filter_diff_by_file_patterns(_MULTI_FILE_DIFF, ("*.py",))
        assert result.startswith("diff --git")

    def test_filtered_diff_preserves_complete_sections(self) -> None:
        """フィルタ後の diff が各ファイルのセクションを完全に保持する。"""
        result = filter_diff_by_file_patterns(_MULTI_FILE_DIFF, ("*.py",))
        # auth.py セクションの内容が完全に含まれる
        assert "index 1234567..abcdefg 100644" in result
        assert "--- a/src/auth.py" in result
        assert "+++ b/src/auth.py" in result
        assert "@@ -1,3 +1,4 @@" in result
        assert "+import sys" in result
