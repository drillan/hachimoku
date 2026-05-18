"""Manifest — レビューエージェントのディスパッチメタデータ契約。

build（SP2）が TOML 定義から生成し、select（SP1-2b-2）/ aggregate（SP1-3）が
消費する純粋データモデル。AgentDefinition から system_prompt 等を除いた、
ディスパッチ判定に必要なサブセットを保持する。
"""

from __future__ import annotations

from typing import Final

from pydantic import Field

from hachimoku.agents.models import ApplicabilityRule, Phase
from hachimoku.models._base import HachimokuBaseModel

MANIFEST_VERSION: Final[str] = "1"
"""Manifest スキーマのバージョン。互換性のない変更時に繰り上げる。"""


class ManifestEntry(HachimokuBaseModel):
    """1エージェント分のディスパッチメタデータ。

    Attributes:
        name: エージェント名（一意識別子）。
        applicability: 適用ルール。
        phase: 実行フェーズ。
        output_schema: 出力スキーマ名（SCHEMA_REGISTRY のキー）。
    """

    name: str = Field(min_length=1)
    applicability: ApplicabilityRule
    phase: Phase
    output_schema: str = Field(min_length=1)


class Manifest(HachimokuBaseModel):
    """全レビューエージェントのディスパッチメタデータ。

    Attributes:
        version: Manifest スキーマのバージョン。
        entries: エージェントごとのエントリ。
    """

    version: str = Field(min_length=1)
    entries: tuple[ManifestEntry, ...]
