# Domain Models

hachimoku's domain models are defined in the `hachimoku.models` package.
All models are Pydantic v2-based, providing type validation and strict validation (extra fields forbidden).

```{contents}
:depth: 2
:local:
```

## Severity

An enumeration that represents the severity of review issues in four levels.

| Value | Description |
|-------|-------------|
| Critical | Critical issue. Must be fixed |
| Important | Important issue. Fix recommended |
| Suggestion | Improvement suggestion |
| Nitpick | Minor remark |

Order: `Critical > Important > Suggestion > Nitpick`

In the severity field of ReviewIssue, input is accepted case-insensitively (`"critical"`, `"CRITICAL"`, `"Critical"` are all valid).

(tool-category)=
## ToolCategory

An enumeration (StrEnum) that defines the types of tools permitted for agents.
Consists of four read-only categories.

| Value | String Value | Description |
|-------|-------------|-------------|
| `GIT_READ` | `"git_read"` | Git read operations (diff, log, show, status, etc.) |
| `GH_READ` | `"gh_read"` | GitHub CLI read operations (pr view, issue view, etc.) |
| `FILE_READ` | `"file_read"` | File read operations (read, ls, etc.) |
| `WEB_FETCH` | `"web_fetch"` | Web content fetch operations |

```{code-block} python
from hachimoku.models import ToolCategory

cat = ToolCategory.GIT_READ
assert cat == "git_read"
```

## FileLocation

Represents the location within a file where a review issue was detected.

| Field | Type | Constraint |
|-------|------|------------|
| `file_path` | `str` | Non-empty |
| `line_number` | `int` | 1 or greater |

```{code-block} python
from hachimoku.models import FileLocation

loc = FileLocation(file_path="src/main.py", line_number=42)
```

## ReviewIssue

A unified representation of issues detected by each agent.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `agent_name` | `str` | Yes | Non-empty |
| `severity` | `Severity` | Yes | Case-insensitive |
| `description` | `str` | Yes | Non-empty |
| `location` | `FileLocation \| None` | No | Default `None` |
| `suggestion` | `str \| None` | No | Default `None` |
| `category` | `str \| None` | No | Default `None` |

```{code-block} python
from hachimoku.models import ReviewIssue, Severity

issue = ReviewIssue(
    agent_name="code-reviewer",
    severity=Severity.IMPORTANT,
    description="Unused variable detected",
    suggestion="Remove the variable or use it",
)
```

## CostInfo

Records token consumption and cost for LLM execution.

| Field | Type | Constraint |
|-------|------|------------|
| `input_tokens` | `int` | 0 or greater |
| `output_tokens` | `int` | 0 or greater |
| `total_cost` | `float` | 0.0 or greater |

## AgentResult

A discriminated union representing the execution result of a single agent.
One of the following four types is automatically selected based on the `status` field value.

### AgentSuccess

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `status` | `Literal["success"]` | Yes | Fixed value `"success"` |
| `agent_name` | `str` | Yes | Non-empty |
| `issues` | `list[ReviewIssue]` | Yes | Empty list allowed |
| `elapsed_time` | `float` | Yes | Positive value (0 not allowed) |
| `cost` | `CostInfo \| None` | No | Default `None` |

### AgentTruncated

Holds partial results when the maximum number of turns is reached.
Treated as a valid result (same as AgentSuccess) when calculating ReviewSummary.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `status` | `Literal["truncated"]` | Yes | Fixed value `"truncated"` |
| `agent_name` | `str` | Yes | Non-empty |
| `issues` | `list[ReviewIssue]` | Yes | Empty list allowed |
| `elapsed_time` | `float` | Yes | Positive value (0 not allowed) |
| `turns_consumed` | `int` | Yes | Positive value (0 not allowed) |

### AgentError

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `status` | `Literal["error"]` | Yes | Fixed value `"error"` |
| `agent_name` | `str` | Yes | Non-empty |
| `error_message` | `str` | Yes | Non-empty |
| `exit_code` | `int \| None` | No | CLI process exit code. Default `None` |
| `error_type` | `str \| None` | No | Structured error type. Non-empty. Default `None` |
| `stderr` | `str \| None` | No | Standard error output. Default `None` |

### AgentTimeout

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `status` | `Literal["timeout"]` | Yes | Fixed value `"timeout"` |
| `agent_name` | `str` | Yes | Non-empty |
| `timeout_seconds` | `float` | Yes | Positive value (0 not allowed) |

### Deserialization Example

```{code-block} python
from pydantic import TypeAdapter
from hachimoku.models import AgentResult, AgentSuccess

adapter = TypeAdapter(AgentResult)

# Type is automatically selected by the status field
result = adapter.validate_python({
    "status": "success",
    "agent_name": "code-reviewer",
    "issues": [],
    "elapsed_time": 2.5,
})
assert isinstance(result, AgentSuccess)
```

## ReviewSummary

An overall summary of review results.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `total_issues` | `int` | Yes | 0 or greater |
| `max_severity` | `Severity \| None` | Yes | `None` when no issues |
| `total_elapsed_time` | `float` | Yes | 0.0 or greater |
| `total_cost` | `CostInfo \| None` | No | Default `None` |

## Priority

An enumeration that represents the priority of recommended actions in three levels.
A separate concept from Severity (issue severity), used in RecommendedAction.

| Value | Description |
|-------|-------------|
| `HIGH` | High priority |
| `MEDIUM` | Medium priority |
| `LOW` | Low priority |

## RecommendedAction

Recommended actions generated by the aggregation agent.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `description` | `str` | Yes | Non-empty |
| `priority` | `Priority` | Yes | - |

## AggregatedReport

Structured output from the LLM-based aggregation agent.
Includes deduplicated issues, positive feedback, recommended actions, and failed agent information.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `issues` | `list[ReviewIssue]` | Yes | Empty list allowed. Deduplicated and merged |
| `strengths` | `list[str]` | Yes | Empty list allowed |
| `recommended_actions` | `list[RecommendedAction]` | Yes | Empty list allowed |
| `agent_failures` | `list[str]` | Yes | Failed agent names. Empty list allowed |

## ReviewReport

A report aggregating results from all agents.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `results` | `list[AgentResult]` | Yes | Empty list allowed |
| `summary` | `ReviewSummary` | Yes | - |
| `load_errors` | `tuple[`[LoadError](load-error)`, ...]` | No | Default empty tuple |
| `aggregated` | `AggregatedReport \| None` | No | Default `None`. No aggregation/disabled/failed |
| `aggregation_error` | `str \| None` | No | Default `None`. Error info on aggregation failure |

`load_errors` holds errors that occurred during agent definition loading.
A report can be generated with empty `results` even if all agents fail.

`aggregated` is the result of LLM-based aggregation (Step 9.5). It is `None` when aggregation is disabled or fails; on failure, `aggregation_error` is set with error information.

```{code-block} python
from hachimoku.models import ReviewReport, ReviewSummary

report = ReviewReport(
    results=[],
    summary=ReviewSummary(
        total_issues=0,
        max_severity=None,
        total_elapsed_time=0.0,
    ),
)
```

## Review History Records

Record models for persisting review results in JSONL format.
Defined as a discriminated union where the type is automatically selected by the `review_mode` field value.

### CommitHash

A type alias for Git commit hashes. Constrained to a 40-character lowercase hexadecimal string.

```{code-block} python
from hachimoku.models import CommitHash
from pydantic import TypeAdapter

adapter = TypeAdapter(CommitHash)
hash_value = adapter.validate_python("a" * 40)  # Valid
```

### DiffReviewRecord

Review history record for diff mode.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `review_mode` | `Literal["diff"]` | Yes | Fixed value `"diff"` |
| `commit_hash` | `CommitHash` | Yes | 40-character lowercase hex |
| `branch_name` | `str` | Yes | Non-empty |
| `reviewed_at` | `datetime` | Yes | - |
| `results` | `list[AgentResult]` | Yes | - |
| `summary` | `ReviewSummary` | Yes | - |

### PRReviewRecord

Review history record for PR mode.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `review_mode` | `Literal["pr"]` | Yes | Fixed value `"pr"` |
| `commit_hash` | `CommitHash` | Yes | 40-character lowercase hex |
| `pr_number` | `int` | Yes | 1 or greater |
| `branch_name` | `str` | Yes | Non-empty |
| `reviewed_at` | `datetime` | Yes | - |
| `results` | `list[AgentResult]` | Yes | - |
| `summary` | `ReviewSummary` | Yes | - |

### FileReviewRecord

Review history record for file mode.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `review_mode` | `Literal["file"]` | Yes | Fixed value `"file"` |
| `file_paths` | `frozenset[str]` | Yes | At least 1 element, each non-empty |
| `reviewed_at` | `datetime` | Yes | - |
| `working_directory` | `str` | Yes | Absolute path |
| `results` | `list[AgentResult]` | Yes | - |
| `summary` | `ReviewSummary` | Yes | - |

### Deserialization Example

```{code-block} python
from pydantic import TypeAdapter
from hachimoku.models import ReviewHistoryRecord, DiffReviewRecord

adapter = TypeAdapter(ReviewHistoryRecord)

# Type is automatically selected by the review_mode field
record = adapter.validate_python({
    "review_mode": "diff",
    "commit_hash": "a" * 40,
    "branch_name": "feature/example",
    "reviewed_at": "2026-01-01T00:00:00",
    "results": [],
    "summary": {
        "total_issues": 0,
        "max_severity": None,
        "total_elapsed_time": 0.0,
    },
})
assert isinstance(record, DiffReviewRecord)
```

(output-schemas)=
## Output Schemas

Schemas that define the output format of agents. All schemas inherit from `BaseAgentOutput` and share the common attribute `issues: list[ReviewIssue]`.

### BaseAgentOutput

The common base model for all output schemas.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `issues` | `list[ReviewIssue]` | Yes | Empty list allowed |

### ScoredIssues

An output schema combining a numerical score with review issues. Used by code-reviewer, among others.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `issues` | `list[ReviewIssue]` | Yes | Empty list allowed |
| `overall_score` | `float` | Yes | 0.0 to 10.0 inclusive |

```{code-block} python
from hachimoku.models import ScoredIssues, ReviewIssue, Severity

scored = ScoredIssues(
    issues=[
        ReviewIssue(
            agent_name="code-reviewer",
            severity=Severity.IMPORTANT,
            description="Missing error handling",
        ),
    ],
    overall_score=7.5,
)
```

### SeverityClassified

An output schema with issue lists classified by severity. Used by silent-failure-hunter, among others.

The `issues` field is automatically derived from the four classification lists. Only the four classification lists need to be specified at input.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `critical_issues` | `list[ReviewIssue]` | Yes | - |
| `important_issues` | `list[ReviewIssue]` | Yes | - |
| `suggestion_issues` | `list[ReviewIssue]` | Yes | - |
| `nitpick_issues` | `list[ReviewIssue]` | Yes | - |
| `issues` | `list[ReviewIssue]` | - | Auto-derived (read-only) |

```{code-block} python
from hachimoku.models import SeverityClassified, ReviewIssue, Severity

classified = SeverityClassified(
    critical_issues=[
        ReviewIssue(
            agent_name="silent-failure-hunter",
            severity=Severity.CRITICAL,
            description="Silent exception swallowed",
        ),
    ],
    important_issues=[],
    suggestion_issues=[],
    nitpick_issues=[],
)

# issues is auto-derived from the concatenation of the four lists
assert len(classified.issues) == 1
```

### TestGapAssessment

An output schema for evaluating test coverage gaps. Used by pr-test-analyzer.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `issues` | `list[ReviewIssue]` | Yes | Empty list allowed |
| `coverage_gaps` | `list[CoverageGap]` | Yes | Empty list allowed |
| `risk_level` | `Severity` | Yes | - |

CoverageGap has the following fields.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `file_path` | `str` | Yes | Non-empty |
| `description` | `str` | Yes | Non-empty |
| `priority` | `Severity` | Yes | - |

### MultiDimensionalAnalysis

An output schema that scores across multiple evaluation dimensions. Used by type-design-analyzer.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `issues` | `list[ReviewIssue]` | Yes | Empty list allowed |
| `dimensions` | `list[DimensionScore]` | Yes | Empty list allowed |

DimensionScore has the following fields.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `name` | `str` | Yes | Non-empty |
| `score` | `float` | Yes | 0.0 to 10.0 inclusive |
| `description` | `str` | Yes | Non-empty |

### CategoryClassification

An output schema that classifies issues by category. Used by comment-analyzer.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `issues` | `list[ReviewIssue]` | Yes | Empty list allowed |
| `categories` | `dict[str, list[ReviewIssue]]` | Yes | Empty dict allowed |

### ImprovementSuggestions

An output schema that provides a list of specific improvement suggestions. Used by code-simplifier.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `issues` | `list[ReviewIssue]` | Yes | Empty list allowed |
| `suggestions` | `list[ImprovementItem]` | Yes | Empty list allowed |

ImprovementItem has the following fields.

| Field | Type | Required | Constraint |
|-------|------|----------|------------|
| `title` | `str` | Yes | Non-empty |
| `description` | `str` | Yes | Non-empty |
| `priority` | `Severity` | Yes | - |
| `location` | `FileLocation \| None` | No | Default `None` |

(schema-registry)=
## SCHEMA_REGISTRY

A registry that resolves schema names to their corresponding schema classes. Used to identify schemas from the `output_schema` field in agent definition files.

Registered schemas:

| Name | Schema Class |
|------|-------------|
| `scored_issues` | `ScoredIssues` |
| `severity_classified` | `SeverityClassified` |
| `test_gap_assessment` | `TestGapAssessment` |
| `multi_dimensional_analysis` | `MultiDimensionalAnalysis` |
| `category_classification` | `CategoryClassification` |
| `improvement_suggestions` | `ImprovementSuggestions` |

```{code-block} python
from hachimoku.models import get_schema, ScoredIssues

schema_cls = get_schema("scored_issues")
assert schema_cls is ScoredIssues
```

Specifying an unregistered schema name raises `SchemaNotFoundError`. New schemas can be added with `register_schema`, and registering a duplicate name raises `DuplicateSchemaError`.
