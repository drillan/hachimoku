# Data Model: 設定管理

**Feature**: 004-configuration | **Date**: 2026-02-06

## Entity Definitions

### OutputFormat（出力形式列挙型）

| Field | Type | Description |
|-------|------|-------------|
| `MARKDOWN` | `"markdown"` | Markdown 形式出力 |
| `JSON` | `"json"` | JSON 形式出力 |

- Python `StrEnum` として定義
- 大文字小文字区別あり（値は小文字のみ）

---

### AgentConfig（エージェント個別設定モデル）

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `enabled` | `bool` | `True` | - | エージェントの有効/無効 |
| `model` | `str \| None` | `None` | `min_length=1` | エージェント固有モデル上書き。`None` でグローバル値を使用 |
| `timeout` | `int \| None` | `None` | `> 0` | エージェント固有タイムアウト上書き。`None` でグローバル値を使用 |
| `max_turns` | `int \| None` | `None` | `> 0` | エージェント固有最大ターン数上書き。`None` でグローバル値を使用 |

- `HachimokuBaseModel` を継承（`extra="forbid"`, `frozen=True`）
- `enabled` はデフォルト `True` の必須フィールド。`model`, `timeout`, `max_turns` はオプショナル（`None` 可）で、`None` の場合はグローバル設定値が適用される

**Validation Rules**:
- `model` が非 `None` の場合、空文字列でないこと（`min_length=1`）
- `timeout` が非 `None` の場合、正の整数であること
- `max_turns` が非 `None` の場合、正の整数であること

---

### SelectorConfig（セレクターエージェント設定モデル）

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `model` | `str \| None` | `None` | `min_length=1` | セレクターモデル上書き。`None` で SelectorDefinition.model → グローバル値を使用 |
| `timeout` | `int \| None` | `None` | `> 0` | セレクタータイムアウト上書き。`None` でグローバル値を使用 |
| `max_turns` | `int \| None` | `None` | `> 0` | セレクター最大ターン数上書き。`None` でグローバル値を使用 |

- `HachimokuBaseModel` を継承（`extra="forbid"`, `frozen=True`）
- 全フィールドはオプショナル（`None` 可）で、`None` の場合は SelectorDefinition の値またはグローバル設定値が適用される
- Issue #64 で導入。Issue #118 で `allowed_tools` を SelectorDefinition に移管

---

### HachimokuConfig（メイン設定モデル）

| Field | Type | Default | Constraints | CLI Option | Description |
|-------|------|---------|-------------|------------|-------------|
| `model` | `str` | `"anthropic:claude-opus-4-6"` | `min_length=1` | `--model` | 使用する LLM モデル名 |
| `timeout` | `int` | `300` | `> 0` | `--timeout` | エージェント実行タイムアウト（秒） |
| `max_turns` | `int` | `10` | `> 0` | `--max-turns` | エージェント最大ターン数 |
| `parallel` | `bool` | `True` | - | `--parallel` | 並列実行モード |
| `base_branch` | `str` | `"main"` | `min_length=1` | `--base-branch` | diff 比較対象ブランチ |
| `output_format` | `OutputFormat` | `OutputFormat.MARKDOWN` | enum | `--format` | 出力形式 |
| `save_reviews` | `bool` | `True` | - | `--save-reviews` | レビュー結果蓄積の有効/無効 |
| `show_cost` | `bool` | `False` | - | `--show-cost` | コスト表示の有効/無効 |
| `max_files_per_review` | `int` | `100` | `> 0` | `--max-files` | file モードの最大ファイル数 |
| `selector` | `SelectorConfig` | `SelectorConfig()` | - | - | セレクターエージェント設定 |
| `agents` | `dict[str, AgentConfig]` | `{}` | key: `^[a-z0-9-]+$` | - | エージェント個別設定マップ |

- `HachimokuBaseModel` を継承（`extra="forbid"`, `frozen=True`）
- デフォルト値のみで有効なインスタンスを構築可能（FR-CF-001 層5: デフォルト値）
- `agents` キーはエージェント名形式（アルファベット小文字・数字・ハイフンのみ）

**Validation Rules**:
- `timeout` > 0
- `max_turns` > 0
- `max_files_per_review` > 0
- `output_format` は `"markdown"` または `"json"` のみ
- `agents` キーは `^[a-z0-9-]+$` パターンに合致

---

## Relationships

```text
HachimokuConfig
├── output_format: OutputFormat (enum)
├── selector: SelectorConfig (selector overrides)
│       └── model, timeout, max_turns
└── agents: dict[str, AgentConfig] (0..N)
        └── AgentConfig (per-agent overrides)
```

- `HachimokuConfig` は `SelectorConfig` をセレクター設定として保持し、0 個以上の `AgentConfig` をエージェント名キーで保持
- `OutputFormat` は `HachimokuConfig.output_format` の型制約として使用
- `SelectorConfig` のオプショナルフィールドが `None` の場合、SelectorDefinition の値またはグローバル値が適用される。この解決は設定消費側（005-review-engine）の責務
- `AgentConfig` のオプショナルフィールドが `None` の場合、`HachimokuConfig` のグローバル値が適用される（FR-CF-008）。この解決は設定消費側（005-review-engine）の責務

---

## State Transitions

設定モデルは `frozen=True` により不変。状態遷移は存在しない。

設定解決のデータフロー:

```text
Layer 5 (Default)
    ↓ dict merge
Layer 4 (~/.config/hachimoku/config.toml)
    ↓ dict merge
Layer 3 (pyproject.toml [tool.hachimoku])
    ↓ dict merge
Layer 2 (.hachimoku/config.toml)
    ↓ dict merge
Layer 1 (CLI options, None excluded)
    ↓ model_validate
HachimokuConfig (immutable)
```
