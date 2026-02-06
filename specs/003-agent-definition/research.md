# Research: 003-agent-definition

**Date**: 2026-02-06

## R-001: TOML パース方法

**Decision**: Python 標準ライブラリ `tomllib`（Python 3.11+ 同梱）を使用する

**Rationale**:
- Python 3.13+ が要件なので `tomllib` は利用可能
- 外部依存の追加が不要（Art.4 Simplicity 準拠）
- TOML 1.0 仕様の完全準拠
- `tomllib.load(f)` はバイナリモードのファイルオブジェクトを受け取り `dict[str, Any]` を返す

**Alternatives considered**:
- `toml` (PyPI): サードパーティ。TOML 0.5 仕様。標準ライブラリが利用可能な場合は不要
- `tomli` (PyPI): Python 3.11 以前の互換パッケージ。3.13+ では不要

**Usage pattern**:
```python
import tomllib
from pathlib import Path

def load_toml(path: Path) -> dict[str, object]:
    with path.open("rb") as f:
        return tomllib.load(f)
```

## R-002: ビルトイン TOML ファイルのパッケージ内配置

**Decision**: `importlib.resources` を使用し、`src/hachimoku/agents/_builtin/` パッケージ内に TOML ファイルを配置する

**Rationale**:
- Python 標準ライブラリのみで完結（外部依存不要）
- `importlib.resources.files()` API（Python 3.9+）で型安全なリソースアクセスが可能
- パッケージビルド時にリソースファイルが自動的に含まれる（`uv_build` は `src/` レイアウトのリソースを自動検出）
- `__init__.py` をマーカーとして配置し、パッケージとして認識させる

**Alternatives considered**:
- `pkg_resources` (setuptools): 非推奨 API、importlib.resources が公式後継
- `__file__` ベースの相対パス解決: パッケージインストール時やzip配布で壊れる可能性
- `package_data` の明示指定: `uv_build` は `src/` レイアウトで自動検出するため不要

**Usage pattern**:
```python
from importlib.resources import files

def get_builtin_dir() -> Path:
    """ビルトイン定義ファイルのディレクトリパスを返す。"""
    return files("hachimoku.agents._builtin")
```

## R-003: fnmatch パターンマッチング

**Decision**: Python 標準ライブラリ `fnmatch.fnmatch()` を使用し、ファイル名（basename）に対してマッチングする

**Rationale**:
- 仕様の明確な要件: 「fnmatch 互換のグロブパターンを使用する」「マッチング対象はファイルパスのファイル名部分（basename）とする」
- `fnmatch.fnmatch(filename, pattern)` は大文字小文字の区別をプラットフォーム依存で行う
- パターン: `*`（任意文字列）, `?`（任意1文字）, `[seq]`（文字クラス）, `[!seq]`（否定文字クラス）

**Alternatives considered**:
- `pathlib.PurePath.match()`: Python 3.12 以降で仕様変更あり（再帰マッチ）。fnmatch 互換が明確に要求されているため不採用
- `glob.glob()`: ファイルシステムアクセスを伴う。パターンマッチングのみが必要なので不適切

**Usage pattern**:
```python
import fnmatch
from pathlib import PurePosixPath

def matches_file_pattern(file_path: str, pattern: str) -> bool:
    basename = PurePosixPath(file_path).name
    return fnmatch.fnmatch(basename, pattern)
```

## R-004: 正規表現パターンマッチング（content_patterns）

**Decision**: Python 標準ライブラリ `re.compile()` + `re.search()` を使用する

**Rationale**:
- 仕様の明確な要件: 「Python `re` 互換正規表現」
- `re.compile()` でバリデーション時にパターンをコンパイルし、無効なパターンを早期検出
- `re.search()` で部分一致を行う（diff/ファイル内容の任意の位置にパターンがあれば一致）
- バリデーション時に `re.error` を捕捉し、具体的なエラーメッセージを生成

**Alternatives considered**:
- `re.match()`: 文字列の先頭からマッチ。差分内容の任意位置でのパターン検出には不適切
- `re.fullmatch()`: 文字列全体とのマッチ。同上

**Usage pattern**:
```python
import re

def validate_regex(pattern: str) -> re.Pattern[str]:
    try:
        return re.compile(pattern)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern '{pattern}': {e}") from None
```

## R-005: Pydantic モデルと TOML の統合パターン

**Decision**: TOML を `dict` として読み込み、pydantic の `model_validate()` でバリデーション + モデル構築する

**Rationale**:
- `tomllib.load()` が返す `dict[str, Any]` を pydantic の `model_validate(data)` に直接渡せる
- TOML のネストされたテーブル（`[applicability]`）は pydantic のネストモデルに自然にマッピングされる
- バリデーションエラーは `pydantic.ValidationError` として詳細なエラー情報が得られる
- 002-domain-models で確立されたパターン（`HachimokuBaseModel`, `extra="forbid"`, `frozen=True`）を踏襲

**Alternatives considered**:
- カスタムパーサーの実装: pydantic が提供するバリデーション機能と重複。DRY 原則違反
- dataclasses + 手動バリデーション: pydantic の方が宣言的で型安全

## R-006: AgentDefinition の frozen 設計

**Decision**: `AgentDefinition` は `HachimokuBaseModel` を継承し、`frozen=True` の不変オブジェクトとする

**Rationale**:
- 002-domain-models の全モデルが `frozen=True`（`HachimokuBaseModel` の `model_config`）を採用しており、一貫性を保つ
- エージェント定義は TOML から読み込み後に変更されるべきでない（不変性の保証）
- pydantic の `frozen=True` により、属性の再代入が型チェッカー・ランタイム双方で防止される

## R-007: LoadResult の設計

**Decision**: `LoadResult` を名前付きタプル的な pydantic モデルとして設計し、正常結果とエラー情報を分離する

**Rationale**:
- 仕様 FR-AD-008 で「スキップされたエージェント情報（ファイル名・エラー内容）はエラーレポートとして返却する」と明記
- 呼び出し元（将来の 005-review-engine）がエラー情報の表示方法を決定できる柔軟性が必要
- `LoadResult.agents: list[AgentDefinition]` + `LoadResult.errors: list[LoadError]` の構成
- `LoadError` はファイルパスとエラーメッセージを保持する軽量モデル

## R-008: ビルトイン6エージェントの適用ルール設計

**Decision**: 各エージェントの専門領域に基づいた `file_patterns` / `content_patterns` / `always` を設定する

**Rationale**:
- 仕様 FR-AD-005 で「各エージェントは専門領域に特化した適用ルールとシステムプロンプトを持つ」と明記
- 仕様 US4 AS3 で「各エージェントの専門領域に適したファイルパターンまたはコンテンツパターンが設定されている」と明記

**Design**:

| Agent | Phase | Applicability Strategy |
|-------|-------|----------------------|
| code-reviewer | main | `always = true`（全ファイルを対象） |
| silent-failure-hunter | main | `content_patterns = ["try\\s*:", "except\\s", "catch\\s*\\(", "\\.catch\\s*\\("]` |
| pr-test-analyzer | main | `file_patterns = ["test_*.py", "*_test.py", "*.test.ts", "*.test.js", "*.spec.ts", "*.spec.js"]` |
| type-design-analyzer | main | `file_patterns = ["*.py", "*.ts", "*.tsx"]` + `content_patterns = ["class\\s+\\w+", "interface\\s+\\w+", "type\\s+\\w+\\s*="]` |
| comment-analyzer | final | `content_patterns = ["\"\"\"", "'''", "/\\*\\*", "//\\s*TODO", "#\\s*TODO"]` |
| code-simplifier | final | `always = true`（全ファイルを対象） |

**Notes**:
- `code-reviewer` と `code-simplifier` は汎用的な分析なので `always = true`
- `silent-failure-hunter` はエラーハンドリングパターンの存在をコンテンツで判定
- `pr-test-analyzer` はテストファイルのファイルパターンで判定
- `type-design-analyzer` は型定義・クラス定義のパターンで判定
- `comment-analyzer` はドキュメントコメントの存在をコンテンツで判定
- Phase: 大半は `main`、`comment-analyzer` と `code-simplifier` は `final`（主要レビュー後に実行）

## R-009: TOML ファイル名とエージェント名の関係

**Decision**: TOML ファイル名は `{agent-name}.toml` 形式とし、ファイル名からエージェント名を推測しない。エージェント名は TOML 内の `name` フィールドで明示的に定義する

**Rationale**:
- 仕様でエージェント名のバリデーションルール（アルファベット小文字・数字・ハイフンのみ）が明示されている
- ファイル名とエージェント名の一致を強制すると、リネームが困難になる
- ただし、ビルトイン定義ではファイル名とエージェント名を一致させる（慣例として）
- ファイル名はエラーメッセージで使用する（「どのファイルに問題があるか」を特定するため）

## R-010: ApplicabilityRule のデフォルト値

**Decision**: TOML に `[applicability]` セクションが存在しない場合、`ApplicabilityRule(always=True)` をデフォルトとして適用する

**Rationale**:
- 仕様 FR-AD-001 で明示: 「TOML に `[applicability]` セクションが存在しない場合、`{always: true}` がデフォルトとして適用される」
- これにより、適用ルールを指定しないシンプルなエージェント定義でも常に実行対象となる
- 明示的にオプトアウトする場合は `[applicability]` セクションを追加し `always = false` を設定する
