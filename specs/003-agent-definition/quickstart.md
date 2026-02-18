# Quickstart: 003-agent-definition

## 概要

エージェント定義・ローダーの実装ガイド。TOML 形式のエージェント定義ファイルを読み込み、AgentDefinition モデルとして構築する。ApplicabilityRule は 005-review-engine の SelectorAgent が参照する判断ガイダンスとして機能する。

## 前提条件

- 002-domain-models が実装済み（`src/hachimoku/models/`）
- `SCHEMA_REGISTRY` に6種の出力スキーマが登録済み

## ビルドシーケンス

以下の順序で実装する（各フェーズは TDD: テスト → Red → 実装 → Green → リファクタ）。

### Phase 1: モデル定義（`agents/models.py`）

1. `Phase` StrEnum + `PHASE_ORDER` 定数
2. `ApplicabilityRule` モデル（正規表現バリデーション含む）
3. `AgentDefinition` モデル（`model_validator` による SCHEMA_REGISTRY 解決含む）
4. `LoadError` + `LoadResult` モデル

**依存**: `hachimoku.models._base.HachimokuBaseModel`, `hachimoku.models.schemas.get_schema`

### Phase 2: ローダー実装（`agents/loader.py`）

1. `_load_single_agent(path)` - 単一 TOML ファイルの読み込み
2. `load_builtin_agents()` - ビルトイン定義の読み込み
3. `load_custom_agents(custom_dir)` - カスタム定義の読み込み
4. `load_agents(custom_dir)` - 統合読み込み（上書きロジック含む）

**依存**: Phase 1 のモデル, `tomllib`, `importlib.resources`

### Phase 3: ビルトイン定義ファイル（`agents/_builtin/*.toml`）

1. 6つのビルトインエージェント TOML 定義ファイルの作成
2. ローダーでの読み込み検証

**依存**: Phase 1 のモデル（バリデーション用）

## 使用例

### エージェント定義の読み込み

```python
from pathlib import Path
from hachimoku.agents.loader import load_agents

# ビルトインのみ
result = load_agents()
print(f"Loaded {len(result.agents)} agents, {len(result.errors)} errors")

# ビルトイン + カスタム
result = load_agents(custom_dir=Path(".hachimoku/agents"))
for agent in result.agents:
    print(f"  {agent.name}: {agent.description}")
for error in result.errors:
    print(f"  ERROR [{error.source}]: {error.message}")
```

### カスタムエージェント定義（TOML）

```toml
# .hachimoku/agents/security-reviewer.toml
name = "security-reviewer"
description = "セキュリティ脆弱性の検出"
model = "claudecode:claude-opus-4-6"
output_schema = "scored_issues"
system_prompt = """
You are a security review specialist. Focus on:
- SQL injection
- XSS vulnerabilities
- Authentication issues
"""

[applicability]
file_patterns = ["*.py", "*.js", "*.ts"]
content_patterns = ["sql", "query", "exec", "eval"]
```

## テスト構成

```text
tests/unit/agents/
├── __init__.py
├── test_models.py      # Phase, ApplicabilityRule, AgentDefinition, LoadError, LoadResult
└── test_loader.py      # load_builtin_agents, load_custom_agents, load_agents
```

各テストファイルは対応する実装モジュールの1対1対応。
