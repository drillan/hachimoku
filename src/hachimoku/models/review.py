"""ファイル位置とレビュー問題の定義。

FR-DM-002: ReviewIssue の統一表現。
FR-DM-010: Severity の大文字小文字非依存入力。
"""

from __future__ import annotations

from pydantic import Field, field_validator

from hachimoku.models._base import HachimokuBaseModel, normalize_enum_value
from hachimoku.models.severity import Severity


class FileLocation(HachimokuBaseModel):
    """ファイル内位置。ファイルパスと行番号の組。

    ReviewIssue のオプション属性として使用し、
    行番号がファイルパスなしに存在する不整合を型で防止する。
    """

    file_path: str = Field(min_length=1)
    line_number: int = Field(ge=1)


class ReviewIssue(HachimokuBaseModel):
    """エージェントが検出したレビュー問題の統一表現。

    severity フィールドは大文字小文字を区別せずに入力を受け付ける。
    内部では PascalCase の Severity 列挙値として保持する。
    """

    agent_name: str = Field(min_length=1)
    severity: Severity
    description: str = Field(min_length=1)
    location: FileLocation | None = None
    suggestion: str | None = None
    category: str | None = None

    @field_validator("severity", mode="before")
    @classmethod
    def normalize_severity(cls, v: object) -> object:
        """Severity 入力を PascalCase に正規化する。"""
        return normalize_enum_value(v, Severity)
