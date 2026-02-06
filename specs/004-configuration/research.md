# Research: 設定管理

**Feature**: 004-configuration | **Date**: 2026-02-06

## R-001: 設定の項目単位マージ戦略

### Decision
辞書の浅いマージ（`dict.update()`）で項目単位の上書きを実現する。各設定ソースを `dict[str, object]` に変換し、下位ソースから上位ソースへ順に辞書マージした後、最終辞書を `HachimokuConfig.model_validate()` に渡す。

### Rationale
- Pydantic の `model_validate` が型検証・制約チェックを一括で行うため、マージ後の辞書を渡すだけで十分
- エージェント個別設定（`agents` セクション）はネストした辞書マージが必要だが、1階層のみなので `dict.update()` の再帰は不要
- 深いマージライブラリ（`deepmerge` 等）は不要。`agents` のみ特別扱いすれば済む

### Alternatives Considered
1. **Pydantic モデルの段階的構築**: 各ソースごとに `HachimokuConfig` を構築し、フィールド単位で比較マージ → 過度に複雑。Pydantic の `frozen=True` 制約と相性が悪い
2. **`ChainMap` の使用**: `collections.ChainMap` で階層的ルックアップ → ネスト構造（agents セクション）の扱いが不自然

## R-002: pyproject.toml の `[tool.hachimoku]` 読み込み

### Decision
`tomllib.load()` で `pyproject.toml` 全体をパースし、`data.get("tool", {}).get("hachimoku", None)` で `[tool.hachimoku]` セクションを抽出する。セクションが存在しなければ `None` を返してスキップする。

### Rationale
- `tomllib` は Python 3.11+ 標準ライブラリであり、追加依存なし
- `pyproject.toml` はプロジェクト設定の標準配置であり、多くの Python ツール（ruff, mypy, pytest 等）が同様のパターンを採用
- パース失敗時（TOML 構文エラー）は例外を送出し、呼び出し元で処理する

### Alternatives Considered
1. **`configparser` 使用**: TOML ではなく INI 形式 → 仕様で TOML に統一と決定済み
2. **`[tool.hachimoku]` セクションのみパース**: TOML の部分パースは標準ライブラリでは不可能。全体パースが必須

## R-003: プロジェクトルート探索アルゴリズム

### Decision
`pathlib.Path` を使い、カレントディレクトリから親ディレクトリへ遡って `.hachimoku/` ディレクトリを探索する。`path.parent == path`（ルート到達）で終了し `None` を返す。

### Rationale
- `pathlib.Path.resolve()` でシンボリックリンクを解決し、実パスで探索する
- ファイルシステムルートまで探索する（Git リポジトリ外での file モードに対応するため）
- `.git/` での停止は行わない（仕様で Git リポジトリ外サポートが明記されているため）

### Alternatives Considered
1. **Git ルート検出（`git rev-parse --show-toplevel`）**: Git 依存になり file モードの Git リポジトリ外実行に対応できない
2. **環境変数（`HACHIMOKU_ROOT`）**: 仕様にない。将来の拡張候補

## R-004: pyproject.toml の探索戦略

### Decision
`pyproject.toml` も `.hachimoku/config.toml` と同様に、カレントディレクトリから親ディレクトリへ遡って探索する。ただし `.hachimoku/` ディレクトリとは独立に探索する（異なるディレクトリに存在する可能性があるため）。

### Rationale
- 仕様 FR-CF-005 で「カレントディレクトリから親ディレクトリへ遡って探索する」と明記
- `.hachimoku/` がプロジェクトルートにあり、`pyproject.toml` がその親（monorepo ルート等）にある場合にも対応

### Alternatives Considered
1. **プロジェクトルートの `pyproject.toml` のみ**: `.hachimoku/` と同じディレクトリに限定 → 仕様の「親ディレクトリへ遡って探索」に反する
2. **全ての `pyproject.toml` をマージ**: 複数の `pyproject.toml` が見つかった場合にマージ → 過度に複雑。最初に見つかったもののみ使用

## R-005: CLI オプションの辞書形式インターフェース

### Decision
CLI オプションは `dict[str, object]` 形式で `resolve_config()` に渡される。キーは設定モデルのフィールド名（`model`, `timeout` 等）を使用する。`None` 値のキーは「未指定」として扱い、マージ対象から除外する。

### Rationale
- 仕様の Assumptions に「CLI オプションの値は 006-cli-interface から辞書形式で渡される想定」と明記
- `None` 除外により、CLI で明示的に指定されたオプションのみが上書きされる
- 006-cli-interface は FR-CF-002 の対応表に基づいてパーサーを構築し、この辞書を生成する

### Alternatives Considered
1. **専用の CLI オプションモデル**: `CliOptions` クラスを定義 → 過度な抽象化。辞書で十分
2. **全フィールドを含む辞書**: `None` 値も含める → マージ時に「未指定」と「明示的 None」の区別が必要になり複雑化

## R-006: エージェント個別設定のマージ戦略

### Decision
エージェント個別設定（`agents` セクション）は、辞書のキー（エージェント名）単位でマージし、各エージェントの設定項目はフィールド単位でマージする。

例:
```toml
# ~/.config/hachimoku/config.toml
[agents.code-reviewer]
timeout = 600

# .hachimoku/config.toml
[agents.code-reviewer]
model = "haiku"
```

結果: `code-reviewer` は `model="haiku"`, `timeout=600` になる（両ソースの値がマージされる）。

### Rationale
- 仕様 FR-CF-007 で「項目単位で行われなければならない」と明記
- エージェント個別設定もこの原則に従い、フィールド単位でマージする
- Edge Case 仕様にも「複数の設定ソースにエージェント個別設定がある場合、設定階層に従い上位のソースの値が優先される（項目単位でのマージ）」と明記

### Alternatives Considered
1. **エージェント単位で上書き（マージなし）**: 上位ソースに `code-reviewer` があれば全体を上書き → 仕様の「項目単位でのマージ」に反する

## R-007: ユーザーグローバル設定パスの決定

### Decision
`~/.config/hachimoku/config.toml` を固定パスとして使用する。`Path.home() / ".config" / "hachimoku" / "config.toml"` で構築する。

### Rationale
- 仕様の Assumptions に「ユーザーグローバル設定のパスは `~/.config/hachimoku/config.toml` に固定する。XDG_CONFIG_HOME 環境変数への対応は将来の拡張とする」と明記
- `Path.home()` は全プラットフォームで動作する

### Alternatives Considered
1. **XDG_CONFIG_HOME 対応**: `$XDG_CONFIG_HOME/hachimoku/config.toml` → 仕様で将来の拡張と明記されており、現時点ではスコープ外

## R-008: デフォルト値の定義方法

### Decision
デフォルト値は `HachimokuConfig` モデルのフィールドデフォルト引数として定義する。名前付き定数は使用しない（Pydantic のフィールドデフォルトがそのまま「名前付き」の役割を果たすため）。

### Rationale
- Pydantic のフィールドデフォルトは型安全であり、`model_json_schema()` でスキーマ出力にも反映される
- Art.6 の「名前付き定数」の要件は、Pydantic フィールドのデフォルト値として `HachimokuConfig.model_fields["timeout"].default` でアクセスできることで満たされる
- 別途定数モジュールを設けると DRY 違反（デフォルト値の二重定義）になるリスクがある

### Alternatives Considered
1. **定数モジュール（`defaults.py`）**: `DEFAULT_TIMEOUT = 300` 等の定数を別途定義 → モデルのデフォルトと二重定義になり DRY 違反
2. **環境変数からデフォルト取得**: 仕様にない。過度な複雑化

## R-009: 設定ファイルのアクセスエラー処理

### Decision
設定ファイルの読み取りアクセスエラー（`PermissionError` 等）は、パースエラーと同様に例外として送出する。ファイルの「不在」と「アクセス不可」は明確に区別する。

### Rationale
- 仕様の Edge Case に「`.hachimoku/config.toml` の読み取り権限がない場合、明確なエラーメッセージとともにバリデーションエラーが報告される」と明記
- ファイルが存在するがアクセスできない状態は、ユーザーが対処すべき問題であり、黙ってスキップすべきではない

### Alternatives Considered
1. **アクセスエラーもスキップ**: ファイル不在と同様に扱う → 仕様の Edge Case に明示的に反する
