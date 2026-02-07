"""レビュー対象の入力情報モデル。

FR-RE-001: 入力モード（diff / PR / file）に応じたレビュー指示情報の構築基盤。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Union

from pydantic import Field

from hachimoku.models._base import HachimokuBaseModel


class ReviewMode(StrEnum):
    """レビュー入力モード。

    CLI 引数で指定されるモードと、ReviewTarget の discriminator 値に対応する。
    """

    DIFF = "diff"
    PR = "pr"
    FILE = "file"


class DiffTarget(HachimokuBaseModel):
    """diff モードのレビュー対象。

    マージベースからの差分をレビューする。
    エージェントが git ツールで差分を自律的に取得する。
    """

    mode: Literal["diff"] = "diff"
    base_branch: str = Field(min_length=1)
    issue_number: int | None = Field(default=None, gt=0)


class PRTarget(HachimokuBaseModel):
    """PR モードのレビュー対象。

    PR 番号を指定し、エージェントが gh/git ツールで
    PR 差分とメタデータを自律的に取得する。
    """

    mode: Literal["pr"] = "pr"
    pr_number: int = Field(gt=0)
    issue_number: int | None = Field(default=None, gt=0)


class FileTarget(HachimokuBaseModel):
    """file モードのレビュー対象。

    ファイルパス・ディレクトリ・glob パターンを指定し、
    エージェントがファイル読み込みツールで内容を取得する。
    """

    mode: Literal["file"] = "file"
    paths: tuple[str, ...] = Field(min_length=1)
    issue_number: int | None = Field(default=None, gt=0)


ReviewTarget = Annotated[
    Union[DiffTarget, PRTarget, FileTarget],
    Field(discriminator="mode"),
]
"""レビュー対象の判別共用体。mode フィールドの値で型を自動選択する。"""
