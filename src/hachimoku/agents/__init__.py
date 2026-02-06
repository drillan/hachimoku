"""エージェント定義・ローダー・セレクター。

公開 API:
    - モデル: Phase, PHASE_ORDER, ApplicabilityRule, AgentDefinition, LoadError, LoadResult
    - ローダー: load_builtin_agents, load_custom_agents, load_agents
    - セレクター: select_agents
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
from hachimoku.agents.selector import select_agents

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
    "select_agents",
]
