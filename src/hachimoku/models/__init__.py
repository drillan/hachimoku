"""hachimoku ドメインモデルパッケージ。"""

from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.agent_result import (
    AgentError,
    AgentResult,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
    CostInfo,
)
from hachimoku.models.history import (
    CommitHash,
    DiffReviewRecord,
    FileReviewRecord,
    PRReviewRecord,
    ReviewHistoryRecord,
)
from hachimoku.models.report import ReviewReport, ReviewSummary
from hachimoku.models.review import FileLocation, ReviewIssue
from hachimoku.models.schemas import (
    SCHEMA_REGISTRY,
    BaseAgentOutput,
    CategoryClassification,
    CoverageGap,
    DimensionScore,
    DuplicateSchemaError,
    ImprovementItem,
    ImprovementSuggestions,
    MultiDimensionalAnalysis,
    SchemaNotFoundError,
    ScoredIssues,
    SeverityClassified,
    TestGapAssessment,
    get_schema,
    register_schema,
)
from hachimoku.models.tool_category import ToolCategory
from hachimoku.models.severity import (
    EXIT_CODE_CRITICAL,
    EXIT_CODE_IMPORTANT,
    EXIT_CODE_SUCCESS,
    SEVERITY_ORDER,
    Severity,
    determine_exit_code,
)

__all__ = [
    "AgentError",
    "AgentResult",
    "AgentSuccess",
    "AgentTimeout",
    "AgentTruncated",
    "BaseAgentOutput",
    "CategoryClassification",
    "CommitHash",
    "CostInfo",
    "CoverageGap",
    "DiffReviewRecord",
    "DimensionScore",
    "DuplicateSchemaError",
    "EXIT_CODE_CRITICAL",
    "EXIT_CODE_IMPORTANT",
    "EXIT_CODE_SUCCESS",
    "FileLocation",
    "FileReviewRecord",
    "HachimokuBaseModel",
    "ImprovementItem",
    "ImprovementSuggestions",
    "MultiDimensionalAnalysis",
    "PRReviewRecord",
    "ReviewHistoryRecord",
    "ReviewIssue",
    "ReviewReport",
    "ReviewSummary",
    "SCHEMA_REGISTRY",
    "SEVERITY_ORDER",
    "SchemaNotFoundError",
    "ScoredIssues",
    "Severity",
    "SeverityClassified",
    "TestGapAssessment",
    "ToolCategory",
    "determine_exit_code",
    "get_schema",
    "register_schema",
]
