# Quickstart: 002-domain-models

## 前提条件

- Python 3.13+
- uv（パッケージマネージャ）
- pydantic v2（pydantic-ai 経由で導入済み）

## セットアップ

```bash
# 依存関係のインストール（pydantic は pydantic-ai 経由で導入済み）
uv --directory $PROJECT_ROOT sync

# pytest を dev dependency に追加（未追加の場合）
uv --directory $PROJECT_ROOT add --dev pytest
```

## ディレクトリ構成

```text
src/hachimoku/models/
├── __init__.py              # 公開 API
├── _base.py                 # HachimokuBaseModel
├── severity.py              # Severity, 終了コードマッピング
├── review.py                # FileLocation, ReviewIssue
├── agent_result.py          # AgentSuccess/Error/Timeout, AgentResult
├── report.py                # ReviewSummary, ReviewReport
├── schemas/                 # 出力スキーマ
│   ├── __init__.py          # SCHEMA_REGISTRY
│   └── ...                  # 6種のスキーマモデル
└── history.py               # ReviewHistoryRecord

tests/unit/models/
├── test_base.py
├── test_severity.py
├── test_review.py
├── test_agent_result.py
├── test_report.py
├── test_schemas.py
└── test_history.py
```

## 実装順序

1. **`_base.py`**: `HachimokuBaseModel`（`ConfigDict(extra="forbid")`）
2. **`severity.py`**: `Severity` 列挙型 + `determine_exit_code()`
3. **`review.py`**: `FileLocation`, `ReviewIssue`
4. **`agent_result.py`**: `CostInfo`, `AgentSuccess/Error/Timeout`, `AgentResult`
5. **`report.py`**: `ReviewSummary`, `ReviewReport`
6. **`schemas/`**: `BaseAgentOutput` → 6種の出力スキーマ → `SCHEMA_REGISTRY`
7. **`history.py`**: `DiffReviewRecord/PRReviewRecord/FileReviewRecord`, `ReviewHistoryRecord`
8. **`__init__.py`**: 全モデルの re-export

各ステップで TDD サイクル（テスト作成 → Red 確認 → 実装 → Green 確認 → リファクタリング）を実行する。

## TDD サイクルの実行例

```bash
# 1. テスト作成後、Red 確認
uv --directory $PROJECT_ROOT run pytest tests/unit/models/test_severity.py -v
# → FAILED (期待通り)

# 2. 実装後、Green 確認
uv --directory $PROJECT_ROOT run pytest tests/unit/models/test_severity.py -v
# → PASSED

# 3. 全テスト実行
uv --directory $PROJECT_ROOT run pytest tests/unit/models/ -v

# 4. 品質チェック
uv --directory $PROJECT_ROOT run ruff check --fix src/hachimoku/models/
uv --directory $PROJECT_ROOT run ruff format src/hachimoku/models/
uv --directory $PROJECT_ROOT run mypy src/hachimoku/models/
```

## 使用例

```python
from hachimoku.models import (
    Severity,
    ReviewIssue,
    ReviewSummary,
    FileLocation,
    AgentSuccess,
    AgentError,
    AgentResult,
    ReviewReport,
    ScoredIssues,
    determine_exit_code,
    get_schema,
)

# ReviewIssue の作成
issue = ReviewIssue(
    agent_name="code-reviewer",
    severity=Severity.CRITICAL,
    description="SQL injection vulnerability detected",
    location=FileLocation(file_path="src/db.py", line_number=42),
    suggestion="Use parameterized queries",
)

# 大文字小文字非依存の Severity 入力
issue2 = ReviewIssue(
    agent_name="code-reviewer",
    severity="critical",  # 小文字でも受け付ける
    description="Another issue",
)

# AgentResult（判別共用体）
success: AgentResult = AgentSuccess(
    agent_name="code-reviewer",
    issues=[issue],
    elapsed_time=1.5,
)

error: AgentResult = AgentError(
    agent_name="silent-failure-hunter",
    error_message="API rate limit exceeded",
)

# ReviewReport（summary に ReviewSummary を委譲）
report = ReviewReport(
    results=[success, error],
    summary=ReviewSummary(
        total_issues=1,
        max_severity=Severity.CRITICAL,
        total_elapsed_time=1.5,
    ),
)

# 終了コード決定
exit_code = determine_exit_code(report.summary.max_severity)
assert exit_code == 1  # Critical → 1

# SCHEMA_REGISTRY
schema = get_schema("scored_issues")
assert schema is ScoredIssues
```
