"""CommitHash, DiffReviewRecord, PRReviewRecord, FileReviewRecord, ReviewHistoryRecord のテスト。

FR-DM-011: ReviewHistoryRecord 判別共用体。
"""

from datetime import datetime, timezone

import pytest
from pydantic import TypeAdapter, ValidationError

from hachimoku.models.agent_result import AgentSuccess
from hachimoku.models.history import (
    CommitHash,
    DiffReviewRecord,
    FileReviewRecord,
    PRReviewRecord,
    ReviewHistoryRecord,
)
from hachimoku.models.report import ReviewSummary
from hachimoku.models.severity import Severity

VALID_COMMIT_HASH = "a" * 40
VALID_REVIEWED_AT = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
VALID_SUMMARY = ReviewSummary(
    total_issues=0,
    max_severity=None,
    total_elapsed_time=0.0,
)
VALID_SUMMARY_WITH_ISSUES = ReviewSummary(
    total_issues=1,
    max_severity=Severity.SUGGESTION,
    total_elapsed_time=1.0,
)
VALID_AGENT_SUCCESS = AgentSuccess(
    agent_name="test-agent",
    issues=[],
    elapsed_time=1.5,
)

commit_hash_adapter: TypeAdapter[str] = TypeAdapter(CommitHash)


# =============================================================================
# CommitHash
# =============================================================================


class TestCommitHashValid:
    """CommitHash の正常系を検証。"""

    def test_valid_40char_hex_lowercase(self) -> None:
        """40文字の16進小文字で検証成功。"""
        result = commit_hash_adapter.validate_python(VALID_COMMIT_HASH)
        assert result == VALID_COMMIT_HASH

    def test_valid_mixed_hex_digits(self) -> None:
        """0-9 と a-f の混在で検証成功。"""
        value = "0123456789abcdef" * 2 + "01234567"
        result = commit_hash_adapter.validate_python(value)
        assert result == value


class TestCommitHashConstraints:
    """CommitHash の制約違反を検証。"""

    def test_uppercase_rejected(self) -> None:
        """大文字を含むハッシュは拒否される。"""
        with pytest.raises(ValidationError, match="string_pattern_mismatch"):
            commit_hash_adapter.validate_python("A" * 40)

    def test_too_short_rejected(self) -> None:
        """39文字は拒否される。"""
        with pytest.raises(ValidationError, match="string_pattern_mismatch"):
            commit_hash_adapter.validate_python("a" * 39)

    def test_too_long_rejected(self) -> None:
        """41文字は拒否される。"""
        with pytest.raises(ValidationError, match="string_pattern_mismatch"):
            commit_hash_adapter.validate_python("a" * 41)

    def test_non_hex_rejected(self) -> None:
        """非16進文字 (g) は拒否される。"""
        with pytest.raises(ValidationError, match="string_pattern_mismatch"):
            commit_hash_adapter.validate_python("g" * 40)

    def test_empty_rejected(self) -> None:
        """空文字列は拒否される。"""
        with pytest.raises(ValidationError, match="string_pattern_mismatch"):
            commit_hash_adapter.validate_python("")


# =============================================================================
# DiffReviewRecord
# =============================================================================


class TestDiffReviewRecordValid:
    """DiffReviewRecord の正常系を検証。"""

    def test_valid_diff_record(self) -> None:
        """全必須フィールド設定で review_mode="diff" のインスタンスが生成される。"""
        record = DiffReviewRecord(
            commit_hash=VALID_COMMIT_HASH,
            branch_name="main",
            reviewed_at=VALID_REVIEWED_AT,
            results=[],
            summary=VALID_SUMMARY,
        )
        assert record.review_mode == "diff"
        assert record.commit_hash == VALID_COMMIT_HASH
        assert record.branch_name == "main"
        assert record.reviewed_at == VALID_REVIEWED_AT
        assert record.results == []
        assert record.summary == VALID_SUMMARY

    def test_review_mode_default(self) -> None:
        """review_mode はデフォルトで "diff" が設定される。"""
        record = DiffReviewRecord(
            commit_hash=VALID_COMMIT_HASH,
            branch_name="feature/test",
            reviewed_at=VALID_REVIEWED_AT,
            results=[],
            summary=VALID_SUMMARY,
        )
        assert record.review_mode == "diff"


class TestDiffReviewRecordConstraints:
    """DiffReviewRecord の制約違反を検証。"""

    def test_invalid_commit_hash_rejected(self) -> None:
        """不正な commit_hash は拒否される。"""
        with pytest.raises(ValidationError, match="commit_hash"):
            DiffReviewRecord(
                commit_hash="invalid",
                branch_name="main",
                reviewed_at=VALID_REVIEWED_AT,
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_empty_branch_name_rejected(self) -> None:
        """空の branch_name は拒否される。"""
        with pytest.raises(ValidationError, match="branch_name"):
            DiffReviewRecord(
                commit_hash=VALID_COMMIT_HASH,
                branch_name="",
                reviewed_at=VALID_REVIEWED_AT,
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_missing_commit_hash_rejected(self) -> None:
        """commit_hash 省略で拒否される。"""
        with pytest.raises(ValidationError):
            DiffReviewRecord(  # type: ignore[call-arg]
                branch_name="main",
                reviewed_at=VALID_REVIEWED_AT,
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_missing_summary_rejected(self) -> None:
        """summary 省略で拒否される。"""
        with pytest.raises(ValidationError):
            DiffReviewRecord(  # type: ignore[call-arg]
                commit_hash=VALID_COMMIT_HASH,
                branch_name="main",
                reviewed_at=VALID_REVIEWED_AT,
                results=[],
            )

    def test_extra_field_rejected(self) -> None:
        """extra フィールドは拒否される。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            DiffReviewRecord(
                commit_hash=VALID_COMMIT_HASH,
                branch_name="main",
                reviewed_at=VALID_REVIEWED_AT,
                results=[],
                summary=VALID_SUMMARY,
                extra_field="bad",  # type: ignore[call-arg]
            )

    def test_frozen(self) -> None:
        """frozen=True で属性変更が拒否される。"""
        record = DiffReviewRecord(
            commit_hash=VALID_COMMIT_HASH,
            branch_name="main",
            reviewed_at=VALID_REVIEWED_AT,
            results=[],
            summary=VALID_SUMMARY,
        )
        with pytest.raises(ValidationError, match="frozen"):
            record.branch_name = "other"  # type: ignore[misc]


# =============================================================================
# PRReviewRecord
# =============================================================================


class TestPRReviewRecordValid:
    """PRReviewRecord の正常系を検証。"""

    def test_valid_pr_record(self) -> None:
        """全必須フィールド設定で review_mode="pr" のインスタンスが生成される。"""
        record = PRReviewRecord(
            commit_hash=VALID_COMMIT_HASH,
            pr_number=42,
            branch_name="feat/new-feature",
            reviewed_at=VALID_REVIEWED_AT,
            results=[],
            summary=VALID_SUMMARY,
        )
        assert record.review_mode == "pr"
        assert record.pr_number == 42
        assert record.branch_name == "feat/new-feature"

    def test_pr_number_one_accepted(self) -> None:
        """pr_number=1 (最小値) が受け入れられる。"""
        record = PRReviewRecord(
            commit_hash=VALID_COMMIT_HASH,
            pr_number=1,
            branch_name="main",
            reviewed_at=VALID_REVIEWED_AT,
            results=[],
            summary=VALID_SUMMARY,
        )
        assert record.pr_number == 1


class TestPRReviewRecordConstraints:
    """PRReviewRecord の制約違反を検証。"""

    def test_empty_branch_name_rejected(self) -> None:
        """空の branch_name は拒否される。"""
        with pytest.raises(ValidationError, match="branch_name"):
            PRReviewRecord(
                commit_hash=VALID_COMMIT_HASH,
                pr_number=1,
                branch_name="",
                reviewed_at=VALID_REVIEWED_AT,
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_pr_number_zero_rejected(self) -> None:
        """pr_number=0 は拒否される (ge=1)。"""
        with pytest.raises(ValidationError, match="pr_number"):
            PRReviewRecord(
                commit_hash=VALID_COMMIT_HASH,
                pr_number=0,
                branch_name="main",
                reviewed_at=VALID_REVIEWED_AT,
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_pr_number_negative_rejected(self) -> None:
        """pr_number=-1 は拒否される。"""
        with pytest.raises(ValidationError, match="pr_number"):
            PRReviewRecord(
                commit_hash=VALID_COMMIT_HASH,
                pr_number=-1,
                branch_name="main",
                reviewed_at=VALID_REVIEWED_AT,
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_extra_field_rejected(self) -> None:
        """extra フィールドは拒否される。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            PRReviewRecord(
                commit_hash=VALID_COMMIT_HASH,
                pr_number=1,
                branch_name="main",
                reviewed_at=VALID_REVIEWED_AT,
                results=[],
                summary=VALID_SUMMARY,
                extra_field="bad",  # type: ignore[call-arg]
            )

    def test_frozen(self) -> None:
        """frozen=True で属性変更が拒否される。"""
        record = PRReviewRecord(
            commit_hash=VALID_COMMIT_HASH,
            pr_number=1,
            branch_name="main",
            reviewed_at=VALID_REVIEWED_AT,
            results=[],
            summary=VALID_SUMMARY,
        )
        with pytest.raises(ValidationError, match="frozen"):
            record.pr_number = 2  # type: ignore[misc]


# =============================================================================
# FileReviewRecord
# =============================================================================


class TestFileReviewRecordValid:
    """FileReviewRecord の正常系を検証。"""

    def test_valid_file_record(self) -> None:
        """全必須フィールド設定で review_mode="file" のインスタンスが生成される。"""
        record = FileReviewRecord(
            file_paths=frozenset({"src/main.py"}),
            reviewed_at=VALID_REVIEWED_AT,
            working_directory="/home/user/project",
            results=[],
            summary=VALID_SUMMARY,
        )
        assert record.review_mode == "file"
        assert record.file_paths == frozenset({"src/main.py"})
        assert record.working_directory == "/home/user/project"

    def test_multiple_file_paths_accepted(self) -> None:
        """複数のファイルパスが受け入れられる。"""
        record = FileReviewRecord(
            file_paths=frozenset({"a.py", "b.py", "c.py"}),
            reviewed_at=VALID_REVIEWED_AT,
            working_directory="/tmp",
            results=[],
            summary=VALID_SUMMARY,
        )
        assert len(record.file_paths) == 3

    def test_frozenset_deduplicates_structurally(self) -> None:
        """リスト入力の重複は frozenset により構造的に排除される。"""
        record = FileReviewRecord(
            file_paths=["a.py", "b.py", "a.py"],  # type: ignore[arg-type]
            reviewed_at=VALID_REVIEWED_AT,
            working_directory="/tmp",
            results=[],
            summary=VALID_SUMMARY,
        )
        assert record.file_paths == frozenset({"a.py", "b.py"})

    def test_absolute_working_directory_accepted(self) -> None:
        """絶対パスの working_directory が受け入れられる。"""
        record = FileReviewRecord(
            file_paths=frozenset({"test.py"}),
            reviewed_at=VALID_REVIEWED_AT,
            working_directory="/var/lib/app",
            results=[],
            summary=VALID_SUMMARY,
        )
        assert record.working_directory == "/var/lib/app"

    def test_results_with_agent_success(self) -> None:
        """AgentSuccess を含む results でインスタンス生成が成功する。"""
        record = FileReviewRecord(
            file_paths=frozenset({"src/main.py"}),
            reviewed_at=VALID_REVIEWED_AT,
            working_directory="/home/user/project",
            results=[VALID_AGENT_SUCCESS],
            summary=VALID_SUMMARY_WITH_ISSUES,
        )
        assert len(record.results) == 1


class TestFileReviewRecordConstraints:
    """FileReviewRecord の制約違反を検証。"""

    def test_empty_string_in_file_paths_rejected(self) -> None:
        """file_paths に空文字列を含むと拒否される。"""
        with pytest.raises(ValidationError, match="file_paths"):
            FileReviewRecord(
                file_paths=frozenset({""}),
                reviewed_at=VALID_REVIEWED_AT,
                working_directory="/tmp",
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_mixed_valid_and_empty_string_in_file_paths_rejected(self) -> None:
        """有効なパスと空文字列の混在は拒否される。"""
        with pytest.raises(ValidationError, match="file_paths"):
            FileReviewRecord(
                file_paths=frozenset({"valid.py", ""}),
                reviewed_at=VALID_REVIEWED_AT,
                working_directory="/tmp",
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_empty_file_paths_rejected(self) -> None:
        """file_paths 空集合は拒否される。"""
        with pytest.raises(ValidationError, match="file_paths"):
            FileReviewRecord(
                file_paths=frozenset(),
                reviewed_at=VALID_REVIEWED_AT,
                working_directory="/tmp",
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_relative_working_directory_rejected(self) -> None:
        """相対パスの working_directory は拒否される。"""
        with pytest.raises(ValidationError, match="working_directory"):
            FileReviewRecord(
                file_paths=frozenset({"test.py"}),
                reviewed_at=VALID_REVIEWED_AT,
                working_directory="relative/path",
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_dot_working_directory_rejected(self) -> None:
        """ドット相対パス "." は拒否される。"""
        with pytest.raises(ValidationError, match="working_directory"):
            FileReviewRecord(
                file_paths=frozenset({"test.py"}),
                reviewed_at=VALID_REVIEWED_AT,
                working_directory=".",
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_dot_dot_working_directory_rejected(self) -> None:
        """ドット相対パス ".." は拒否される。"""
        with pytest.raises(ValidationError, match="working_directory"):
            FileReviewRecord(
                file_paths=frozenset({"test.py"}),
                reviewed_at=VALID_REVIEWED_AT,
                working_directory="..",
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_empty_working_directory_rejected(self) -> None:
        """空文字列の working_directory は拒否される。"""
        with pytest.raises(ValidationError, match="working_directory"):
            FileReviewRecord(
                file_paths=frozenset({"test.py"}),
                reviewed_at=VALID_REVIEWED_AT,
                working_directory="",
                results=[],
                summary=VALID_SUMMARY,
            )

    def test_extra_field_rejected(self) -> None:
        """extra フィールドは拒否される。"""
        with pytest.raises(ValidationError, match="extra_forbidden"):
            FileReviewRecord(
                file_paths=frozenset({"test.py"}),
                reviewed_at=VALID_REVIEWED_AT,
                working_directory="/tmp",
                results=[],
                summary=VALID_SUMMARY,
                extra_field="bad",  # type: ignore[call-arg]
            )

    def test_frozen(self) -> None:
        """frozen=True で属性変更が拒否される。"""
        record = FileReviewRecord(
            file_paths=frozenset({"test.py"}),
            reviewed_at=VALID_REVIEWED_AT,
            working_directory="/tmp",
            results=[],
            summary=VALID_SUMMARY,
        )
        with pytest.raises(ValidationError, match="frozen"):
            record.working_directory = "/other"  # type: ignore[misc]


# =============================================================================
# ReviewHistoryRecord (判別共用体)
# =============================================================================

history_adapter: TypeAdapter[DiffReviewRecord | PRReviewRecord | FileReviewRecord] = (
    TypeAdapter(ReviewHistoryRecord)
)


class TestReviewHistoryRecordDiscriminator:
    """ReviewHistoryRecord の判別共用体デシリアライズを検証。"""

    def test_diff_variant_selected(self) -> None:
        """review_mode="diff" で DiffReviewRecord が選択される。"""
        data = {
            "review_mode": "diff",
            "commit_hash": VALID_COMMIT_HASH,
            "branch_name": "main",
            "reviewed_at": VALID_REVIEWED_AT.isoformat(),
            "results": [],
            "summary": VALID_SUMMARY.model_dump(),
        }
        result = history_adapter.validate_python(data)
        assert isinstance(result, DiffReviewRecord)
        assert result.review_mode == "diff"

    def test_pr_variant_selected(self) -> None:
        """review_mode="pr" で PRReviewRecord が選択される。"""
        data = {
            "review_mode": "pr",
            "commit_hash": VALID_COMMIT_HASH,
            "pr_number": 10,
            "branch_name": "feat/x",
            "reviewed_at": VALID_REVIEWED_AT.isoformat(),
            "results": [],
            "summary": VALID_SUMMARY.model_dump(),
        }
        result = history_adapter.validate_python(data)
        assert isinstance(result, PRReviewRecord)
        assert result.review_mode == "pr"

    def test_file_variant_selected(self) -> None:
        """review_mode="file" で FileReviewRecord が選択される（list 入力→frozenset 変換）。"""
        data = {
            "review_mode": "file",
            "file_paths": ["src/app.py"],
            "reviewed_at": VALID_REVIEWED_AT.isoformat(),
            "working_directory": "/home/user/project",
            "results": [],
            "summary": VALID_SUMMARY.model_dump(),
        }
        result = history_adapter.validate_python(data)
        assert isinstance(result, FileReviewRecord)
        assert result.review_mode == "file"
        assert result.file_paths == frozenset({"src/app.py"})

    def test_invalid_review_mode_rejected(self) -> None:
        """不正な review_mode は拒否される。"""
        data = {
            "review_mode": "unknown",
            "reviewed_at": VALID_REVIEWED_AT.isoformat(),
            "results": [],
            "summary": VALID_SUMMARY.model_dump(),
        }
        with pytest.raises(ValidationError):
            history_adapter.validate_python(data)

    def test_missing_review_mode_rejected(self) -> None:
        """review_mode 欠落は拒否される。"""
        data = {
            "commit_hash": VALID_COMMIT_HASH,
            "branch_name": "main",
            "reviewed_at": VALID_REVIEWED_AT.isoformat(),
            "results": [],
            "summary": VALID_SUMMARY.model_dump(),
        }
        with pytest.raises(ValidationError):
            history_adapter.validate_python(data)

    def test_diff_with_file_paths_rejected(self) -> None:
        """review_mode="diff" に file_paths を含めると拒否される (extra="forbid")。"""
        data = {
            "review_mode": "diff",
            "commit_hash": VALID_COMMIT_HASH,
            "branch_name": "main",
            "reviewed_at": VALID_REVIEWED_AT.isoformat(),
            "results": [],
            "summary": VALID_SUMMARY.model_dump(),
            "file_paths": ["a.py"],
        }
        with pytest.raises(ValidationError, match="extra_forbidden"):
            history_adapter.validate_python(data)

    def test_pr_with_working_directory_rejected(self) -> None:
        """review_mode="pr" に working_directory を含めると拒否される (extra="forbid")。"""
        data = {
            "review_mode": "pr",
            "commit_hash": VALID_COMMIT_HASH,
            "pr_number": 1,
            "branch_name": "main",
            "reviewed_at": VALID_REVIEWED_AT.isoformat(),
            "results": [],
            "summary": VALID_SUMMARY.model_dump(),
            "working_directory": "/tmp",
        }
        with pytest.raises(ValidationError, match="extra_forbidden"):
            history_adapter.validate_python(data)


class TestReviewHistoryRecordRoundTrip:
    """ReviewHistoryRecord のラウンドトリップ（JSONL 永続化）を検証。"""

    def test_diff_round_trip(self) -> None:
        """DiffReviewRecord の model_dump → validate_python ラウンドトリップ。"""
        original = DiffReviewRecord(
            commit_hash=VALID_COMMIT_HASH,
            branch_name="main",
            reviewed_at=VALID_REVIEWED_AT,
            results=[VALID_AGENT_SUCCESS],
            summary=VALID_SUMMARY_WITH_ISSUES,
        )
        restored = history_adapter.validate_python(original.model_dump())
        assert isinstance(restored, DiffReviewRecord)
        assert restored == original

    def test_pr_round_trip(self) -> None:
        """PRReviewRecord の model_dump → validate_python ラウンドトリップ。"""
        original = PRReviewRecord(
            commit_hash=VALID_COMMIT_HASH,
            pr_number=42,
            branch_name="feat/x",
            reviewed_at=VALID_REVIEWED_AT,
            results=[],
            summary=VALID_SUMMARY,
        )
        restored = history_adapter.validate_python(original.model_dump())
        assert isinstance(restored, PRReviewRecord)
        assert restored == original

    def test_file_round_trip(self) -> None:
        """FileReviewRecord の model_dump → validate_python ラウンドトリップ。"""
        original = FileReviewRecord(
            file_paths=frozenset({"src/main.py", "src/utils.py"}),
            reviewed_at=VALID_REVIEWED_AT,
            working_directory="/home/user/project",
            results=[],
            summary=VALID_SUMMARY,
        )
        restored = history_adapter.validate_python(original.model_dump())
        assert isinstance(restored, FileReviewRecord)
        assert restored == original

    def test_file_json_round_trip(self) -> None:
        """FileReviewRecord の JSON 経由ラウンドトリップ（JSONL 永続化シナリオ）。

        frozenset は JSON にネイティブで存在しないため、
        model_dump_json() → json.loads() → validate_python() の経路で
        JSON array（list）から frozenset への復元を検証する。
        """
        import json

        original = FileReviewRecord(
            file_paths=frozenset({"src/main.py", "src/utils.py"}),
            reviewed_at=VALID_REVIEWED_AT,
            working_directory="/home/user/project",
            results=[],
            summary=VALID_SUMMARY,
        )
        json_str = original.model_dump_json()
        json_dict = json.loads(json_str)
        # JSON 経由で list に変換されていることを確認
        assert isinstance(json_dict["file_paths"], list)
        restored = history_adapter.validate_python(json_dict)
        assert isinstance(restored, FileReviewRecord)
        assert isinstance(restored.file_paths, frozenset)
        assert restored == original
