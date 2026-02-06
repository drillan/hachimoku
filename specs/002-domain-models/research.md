# Research: 002-domain-models

## 1. Pydantic v2 判別共用体（Discriminated Union）パターン

### Decision
`Literal` 型フィールド + `Field(discriminator="field_name")` パターンを採用する。

### Rationale
- Pydantic v2 の Rust バックエンドで最適化済み。判別キーで型を一意に特定し、単一モデルのみバリデーションを実行するため高速
- `Literal` 型により不可能な状態を型レベルで排除できる
- `AgentResult` の `status` フィールド、`ReviewHistoryRecord` の `review_mode` フィールドに適用

### Alternatives Considered
- **Callable Discriminator** (`Annotated[Union[...], Discriminator(func)]`): より柔軟だが、仕様の要件（固定フィールド値による判別）には過剰。シンプルな Field-based で十分
- **Left-to-right Union** (`union_mode="left_to_right"`): 順次検証でパフォーマンスが劣る。判別キーが明確に定義されているため不要

### 具体的パターン

```python
from typing import Literal, Union
from pydantic import BaseModel, Field

class AgentSuccess(BaseModel):
    status: Literal["success"] = "success"
    agent_name: str
    issues: list[ReviewIssue]
    elapsed_time: float

class AgentError(BaseModel):
    status: Literal["error"] = "error"
    agent_name: str
    error_message: str

class AgentTimeout(BaseModel):
    status: Literal["timeout"] = "timeout"
    agent_name: str
    timeout_seconds: float

AgentResult = Annotated[
    Union[AgentSuccess, AgentError, AgentTimeout],
    Field(discriminator="status"),
]
```

## 2. 厳格モード（extra="forbid"）の一元管理

### Decision
共通ベースモデル `HachimokuBaseModel` で `model_config = ConfigDict(extra="forbid")` を定義し、全モデルが継承する。

### Rationale
- FR-DM-009（厳格モード）を DRY に実現
- Pydantic v2 では `ConfigDict` が継承される
- `extra="forbid"` により想定外のフィールドをバリデーションエラーとして検出

### Alternatives Considered
- **各モデルに個別設定**: DRY 原則違反。設定漏れのリスク
- **メタクラスでの自動設定**: 過剰な抽象化。Pydantic の継承メカニズムで十分

## 3. Severity の大文字小文字非依存入力

### Decision
Severity を `StrEnum` として定義し、`@field_validator(mode="before")` で入力値を PascalCase に正規化する。

### Rationale
- FR-DM-010 の要件（大文字小文字非依存、内部表現は PascalCase）を実現
- `mode="before"` により Pydantic のバリデーション前に正規化される
- `StrEnum` により JSON シリアライズ時に文字列値として出力

### Alternatives Considered
- **カスタム型**: Pydantic の標準パターンから逸脱。保守性が低い
- **`BeforeValidator`**: `field_validator` と同等だが、フィールド単位での適用が煩雑

### 具体的パターン

```python
from enum import StrEnum

class Severity(StrEnum):
    CRITICAL = "Critical"
    IMPORTANT = "Important"
    SUGGESTION = "Suggestion"
    NITPICK = "Nitpick"
```

`StrEnum` を使用することで `Severity("Critical")` と `Severity("critical")` の両方が動作する...ただし大文字小文字非依存は `StrEnum` 単体では不可能。`@field_validator` で正規化が必要。

## 4. SCHEMA_REGISTRY の設計

### Decision
`dict[str, type[BaseAgentOutput]]` としてモジュールレベルで定義し、登録関数で重複チェックを行う。

### Rationale
- FR-DM-006 の要件（名前からスキーマ解決、未登録はエラー）を実現
- シンプルな辞書ベースで十分。動的なプラグインシステムは不要
- 重複登録は明確なエラーとして検出

### Alternatives Considered
- **Enum ベース**: スキーマの追加が煩雑
- **デコレータパターン**: シンプルだが暗黙的。明示的な登録の方が仕様の意図に合致

## 5. モデル継承構造

### Decision
以下の継承階層を採用:

```
BaseModel (pydantic)
└── HachimokuBaseModel (extra="forbid" 共通設定)
    ├── Severity (StrEnum, 独立)
    ├── FileLocation
    ├── ReviewIssue
    ├── AgentSuccess / AgentError / AgentTimeout
    ├── CostInfo
    ├── ReviewReport
    ├── DiffReviewRecord / PRReviewRecord / FileReviewRecord
    └── BaseAgentOutput
        ├── ScoredIssues
        ├── SeverityClassified
        ├── TestGapAssessment
        ├── MultiDimensionalAnalysis
        ├── CategoryClassification
        └── ImprovementSuggestions
```

### Rationale
- `HachimokuBaseModel` で `ConfigDict` を一元管理（DRY）
- `BaseAgentOutput` で出力スキーマの共通属性（ReviewIssue リスト）を定義
- 継承は最大2段階（HachimokuBaseModel → BaseAgentOutput → 具体スキーマ）で複雑化を回避

### Alternatives Considered
- **Mixin パターン**: 多重継承による複雑化。Pydantic では単純な継承チェーンが推奨
- **Composition のみ**: 共通属性の一元管理が困難。出力スキーマの共通インターフェースが実現しにくい

## 6. Severity → 終了コードマッピング

### Decision
`Severity` クラスに `to_exit_code()` メソッドとして実装するのではなく、モジュールレベル関数 `severity_to_exit_code()` として定義する。

### Rationale
- 終了コードの決定は「レビュー結果全体の最大重大度」から行うため、個別 Severity のメソッドではなくリスト操作が必要
- 名前付き定数で終了コードを定義（マジックナンバー禁止）
- FR-DM-008: Critical→1, Important→2, Suggestion/Nitpick/問題なし→0

### Alternatives Considered
- **Severity のメソッド**: 「最大重大度の判定」はリスト操作であり Severity の責務を超える
- **専用クラス**: 過剰な抽象化。関数で十分
