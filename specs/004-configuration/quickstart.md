# Quickstart: 設定管理

**Feature**: 004-configuration | **Date**: 2026-02-06

## 概要

設定管理機能は、5層の設定ソースを階層的にマージして `HachimokuConfig` を構築する。

## 使用例

### 1. デフォルト設定の取得

```python
from hachimoku.config import resolve_config

# 全項目がデフォルト値で構成される
config = resolve_config()
assert config.model == "anthropic:claude-opus-4-6"
assert config.timeout == 300
assert config.parallel is True
```

### 2. プロジェクト設定からの読み込み

```toml
# .hachimoku/config.toml
model = "opus"
timeout = 600
base_branch = "develop"

[agents.code-reviewer]
enabled = false
```

```python
from pathlib import Path
from hachimoku.config import resolve_config

config = resolve_config(start_dir=Path("/path/to/project"))
assert config.model == "opus"
assert config.timeout == 600
assert config.agents["code-reviewer"].enabled is False
```

### 3. CLI オプションによる上書き

```python
from hachimoku.config import resolve_config

# CLI オプションが最高優先度
config = resolve_config(
    cli_overrides={"model": "haiku", "parallel": True}
)
assert config.model == "haiku"
assert config.parallel is True
```

### 4. プロジェクトルートの探索

```python
from pathlib import Path
from hachimoku.config import find_project_root

# サブディレクトリからでもプロジェクトルートを発見
root = find_project_root(Path("/path/to/project/src/deep/dir"))
# root == Path("/path/to/project") (.hachimoku/ がある場所)
```

### 5. pyproject.toml からの設定

```toml
# pyproject.toml
[tool.hachimoku]
output_format = "json"
save_reviews = false
```

```python
from hachimoku.config import resolve_config

config = resolve_config()
assert config.output_format.value == "json"
assert config.save_reviews is False
```

## 主要コンポーネント

| コンポーネント | モジュール | 責務 |
|--------------|----------|------|
| `HachimokuConfig` | `hachimoku.models.config` | 設定モデル（不変） |
| `AgentConfig` | `hachimoku.models.config` | エージェント個別設定 |
| `OutputFormat` | `hachimoku.models.config` | 出力形式列挙型 |
| `find_project_root` | `hachimoku.config` | .hachimoku/ 探索 |
| `resolve_config` | `hachimoku.config` | 5層マージ・構築 |

## 設定解決の優先順位

```
CLI (最高) > .hachimoku/config.toml > pyproject.toml > ~/.config/hachimoku/config.toml > デフォルト (最低)
```

## エラーハンドリング

- **ファイル不在**: スキップ（エラーとしない）
- **TOML 構文エラー**: `tomllib.TOMLDecodeError` を送出
- **バリデーションエラー**: `pydantic.ValidationError` を送出（フィールド名・期待型を含む）
- **読み取り権限エラー**: `PermissionError` を送出
