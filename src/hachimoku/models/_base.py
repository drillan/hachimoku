"""全ドメインモデルの基底クラス。

FR-DM-009: extra="forbid" で厳格モードを一元管理。
"""

from pydantic import BaseModel, ConfigDict


class HachimokuBaseModel(BaseModel):
    """全ドメインモデルの基底クラス。extra="forbid" で厳格モードを一元管理。"""

    model_config = ConfigDict(extra="forbid")
