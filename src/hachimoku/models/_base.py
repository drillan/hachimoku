"""全ドメインモデルの基底クラスと共通ユーティリティ。

FR-DM-009: extra="forbid" で厳格モードを一元管理。
FR-DM-010: normalize_enum_value による StrEnum ケース正規化。
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class HachimokuBaseModel(BaseModel):
    """全ドメインモデルの基底クラス。extra="forbid" で厳格モードを一元管理。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


def normalize_enum_value[E: StrEnum](v: object, enum_cls: type[E]) -> object:
    """StrEnum 入力を正規化する（大文字小文字非依存）。

    str 入力を enum_cls のメンバー値と case-insensitive でマッチし、
    正規の値文字列に変換する。マッチしない str や str 以外の入力は
    そのまま返し、後続の Pydantic バリデーションに委ねる。

    Args:
        v: バリデーション対象の入力値。
        enum_cls: マッチ対象の StrEnum クラス。

    Returns:
        正規化された値文字列、またはマッチしない場合は入力値そのまま。
    """
    if isinstance(v, str):
        for member in enum_cls:
            if v.lower() == member.value.lower():
                return member.value
    return v
