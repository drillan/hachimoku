"""エージェント定義・ローダー。

公開 API:
    - モデル: Phase, PHASE_ORDER, ApplicabilityRule, AgentDefinition, LoadError, LoadResult
    - ローダー: load_builtin_agents, load_custom_agents, load_agents
"""

from hachimoku.agents.loader import load_agents, load_builtin_agents, load_custom_agents
from hachimoku.agents.models import (
    PHASE_ORDER,
    AgentDefinition,
    ApplicabilityRule,
    LoadError,
    LoadResult,
    Phase,
)

__all__ = [
    "PHASE_ORDER",
    "AgentDefinition",
    "ApplicabilityRule",
    "LoadError",
    "LoadResult",
    "Phase",
    "load_agents",
    "load_builtin_agents",
    "load_custom_agents",
]

# ReviewReport.load_errors の遅延型参照を解決。
# report.py は循環 import 回避のため LoadError を TYPE_CHECKING ガード内で import する。
# agents パッケージのロード完了後に model_rebuild() で型を解決する。
from hachimoku.models.report import ReviewReport as _ReviewReport

_ReviewReport.model_rebuild(_types_namespace={"LoadError": LoadError})
