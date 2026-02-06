"""レビュー履歴レコードの定義。

FR-DM-011: ReviewHistoryRecord 判別共用体。
review_mode フィールドの固定値で型を一意に特定する。
"""

from __future__ import annotations

from datetime import datetime
from pathlib import PurePosixPath
from typing import Annotated, Literal, Union

from pydantic import Field, field_validator

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.agent_result import AgentResult
from hachimoku.models.report import ReviewSummary

CommitHash = Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
"""コミットハッシュの型エイリアス。40文字の16進小文字文字列。"""


class DiffReviewRecord(HachimokuBaseModel):
    """diff レビューの履歴レコード。判別キー: review_mode="diff"。

    Attributes:
        review_mode: 判別キー。固定値 "diff"。
        commit_hash: コミットハッシュ（40文字16進小文字）。
        branch_name: ブランチ名（空文字不可）。
        reviewed_at: レビュー実行日時。
        results: エージェント結果のリスト。
        summary: レビュー結果のサマリー。
    """

    review_mode: Literal["diff"] = "diff"
    commit_hash: CommitHash
    branch_name: str = Field(min_length=1)
    reviewed_at: datetime
    results: list[AgentResult]
    summary: ReviewSummary


class PRReviewRecord(HachimokuBaseModel):
    """PR レビューの履歴レコード。判別キー: review_mode="pr"。

    Attributes:
        review_mode: 判別キー。固定値 "pr"。
        commit_hash: コミットハッシュ（40文字16進小文字）。
        pr_number: PR 番号（1以上）。
        branch_name: ブランチ名（空文字不可）。
        reviewed_at: レビュー実行日時。
        results: エージェント結果のリスト。
        summary: レビュー結果のサマリー。
    """

    review_mode: Literal["pr"] = "pr"
    commit_hash: CommitHash
    pr_number: int = Field(ge=1)
    branch_name: str = Field(min_length=1)
    reviewed_at: datetime
    results: list[AgentResult]
    summary: ReviewSummary


class FileReviewRecord(HachimokuBaseModel):
    """file レビューの履歴レコード。判別キー: review_mode="file"。

    file_paths は重複排除バリデータにより一意性が保証される。
    working_directory は絶対パスバリデータにより検証される。

    Attributes:
        review_mode: 判別キー。固定値 "file"。
        file_paths: レビュー対象ファイルパスのリスト（1要素以上、重複排除済み）。
        reviewed_at: レビュー実行日時。
        working_directory: 作業ディレクトリ（絶対パス）。
        results: エージェント結果のリスト。
        summary: レビュー結果のサマリー。
    """

    review_mode: Literal["file"] = "file"
    file_paths: list[str] = Field(min_length=1)
    reviewed_at: datetime
    working_directory: str
    results: list[AgentResult]
    summary: ReviewSummary

    @field_validator("file_paths", mode="before")
    @classmethod
    def deduplicate_file_paths(cls, v: list[str]) -> list[str]:
        """file_paths の重複を排除する（順序保持）。"""
        if isinstance(v, list):
            return list(dict.fromkeys(v))
        return v

    @field_validator("working_directory", mode="after")
    @classmethod
    def validate_absolute_path(cls, v: str) -> str:
        """working_directory が絶対パスであることを検証する。"""
        if not PurePosixPath(v).is_absolute():
            raise ValueError("working_directory must be an absolute path")
        return v


ReviewHistoryRecord = Annotated[
    Union[DiffReviewRecord, PRReviewRecord, FileReviewRecord],
    Field(discriminator="review_mode"),
]
"""レビュー履歴レコードの判別共用体。review_mode フィールドの値で型を自動選択する。"""
