"""全出力スキーマの共通ベースモデル。

FR-DM-005: BaseAgentOutput は全出力スキーマの共通属性を定義する。
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, model_validator

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.review import ReviewIssue


def unwrap_data_envelope(data: dict[str, Any]) -> dict[str, Any]:
    """LLM が出力を単一キー dict でラップした場合に unwrap する。

    LLM がテキスト出力モードで構造化 JSON を返す際、
    {"data": {...}} や {"result": {...}} 等の単一キー dict エンベロープで
    ラップすることがある。入力が dict かつキーが1つのみで、
    その値が dict の場合に内側の dict を取り出す。

    全出力スキーマは BaseAgentOutput を継承し最低2フィールド
    （issues, overall_score）を持つため、正当な出力が単一キー dict
    になることはなく、誤 unwrap のリスクはない。

    Pydantic v2 では model_validator(mode="before") の実行順が
    子クラス → 親クラスのため、子クラスが独自の model_validator を
    持つ場合は親の unwrap が後に実行される。そのため、子クラスの
    バリデータ冒頭でもこの関数を呼び出す必要がある。
    """
    if (
        isinstance(data, dict)
        and len(data) == 1
        and isinstance(next(iter(data.values())), dict)
    ):
        return next(iter(data.values()))
    return data


class BaseAgentOutput(HachimokuBaseModel):
    """全出力スキーマの共通ベースモデル。

    全エージェントの出力は issues (ReviewIssue のリスト) と
    overall_score (品質スコア 0.0-10.0) を共通属性として持つ。
    各具体スキーマはこのクラスを継承し、固有フィールドを追加する。
    """

    issues: list[ReviewIssue]
    overall_score: float = Field(ge=0.0, le=10.0, allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def _unwrap_data_envelope(cls, data: dict[str, Any]) -> dict[str, Any]:
        """単一キー dict エンベロープの unwrap を model_validator 経由で適用する。"""
        return unwrap_data_envelope(data)
