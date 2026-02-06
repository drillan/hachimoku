"""全出力スキーマの共通ベースモデル。

FR-DM-005: BaseAgentOutput は全出力スキーマの共通属性を定義する。
"""

from __future__ import annotations

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.review import ReviewIssue


class BaseAgentOutput(HachimokuBaseModel):
    """全出力スキーマの共通ベースモデル。

    全エージェントの出力は issues (ReviewIssue のリスト) を共通属性として持つ。
    各具体スキーマはこのクラスを継承し、固有フィールドを追加する。
    """

    issues: list[ReviewIssue]
