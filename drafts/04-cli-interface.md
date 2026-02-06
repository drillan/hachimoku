# hachimoku — CLI インターフェース仕様

**Parent Spec**: [001-architecture-spec](../specs/001-architecture-spec/spec.md)
**Implements**: FR-021（位置引数判定）, FR-029〜FR-032（file モード関連機能要件）

## コマンド構造

```bash
8moku [PR番号|ファイルパス...] [OPTIONS]  # レビュー実行（デフォルト動作）
8moku init [--force]                      # プロジェクト初期化
8moku agents list                         # 利用可能エージェント一覧
8moku agents show <name>                  # エージェント詳細表示
8moku config show                         # 現在の設定表示
```

**コマンド名**: `8moku`（推奨短縮名）および `hachimoku`（互換フルネーム）の両方で同一の機能を提供する。

## レビューコマンド（デフォルト動作）

### 位置引数

`8moku` コマンドは位置引数によってレビューモードを自動判定する。

| 引数パターン | 判定結果 | 例 |
|-----------|---------|-----|
| サブコマンド文字列 | サブコマンド実行 | `8moku init` |
| 整数のみ | PR モード（指定 PR のレビュー） | `8moku 123` |
| パスライク文字列 | file モード（指定ファイルのレビュー） | `8moku src/auth.py` |
| ファイルシステム上に存在するパス | file モード（拡張子なしファイル） | `8moku Makefile` |
| なし | diff モード（現在ブランチの変更差分） | `8moku` |

**位置引数の判定ルール**（優先順）:

1. サブコマンド文字列（`init`, `agents`, `config`）→ サブコマンド
2. 整数のみ → PR 番号
3. `/`, `\`, `*`, `?`, `.` のいずれかを含む → ファイルパス
4. ファイルシステム上に存在するパス（`Makefile`, `Dockerfile`, `LICENSE` 等の拡張子なしファイル名）→ ファイルパス
5. 引数なし → diff モード
6. 上記のいずれにも該当しない → エラー（終了コード 4）

**注意事項**:
- PR 番号とファイルパスの同時指定は不可（`8moku 123 src/auth.py` はエラー）
- 複数のファイルパスは同時に指定可能（`8moku file1.py file2.py`）

### 使用例

```bash
# diff モード: 全適用可能エージェントを逐次実行
8moku

# PR モード: PR #123 をレビュー
8moku 123

# PR モード + Issue 連携
8moku 123 --issue 122

# file モード: 単一ファイル
8moku src/auth.py

# file モード: 複数ファイル
8moku src/auth.py src/api/client.py

# file モード: ディレクトリ（再帰探索）
8moku src/

# file モード: glob パターン（シェル展開を避けるためクォート推奨）
8moku "src/**/*.py"

# file モード + Issue 連携
8moku src/auth.py --issue 122

# file モード: Git 管理外のドキュメントレビュー
8moku ~/documents/article.md

# 並列実行
8moku --parallel

# 特定エージェントのみ
8moku --agents code-reviewer,test-analyzer

# JSON 出力
8moku --format json

# base ブランチ指定（diff モード）
8moku --base develop

# タイムアウトとモデルのオーバーライド
8moku --timeout 600 --model opus

# 結果をファイルに書き出し
8moku --output review-result.md

# コスト情報表示
8moku --cost
```

### オプション一覧

| オプション | 短縮 | 型 | デフォルト | 説明 |
|-----------|------|-----|----------|------|
| `--agents` | `-a` | str | "all" | 実行エージェント（カンマ区切り） |
| `--parallel` | `-p` | flag | false | 並列実行モード |
| `--format` | `-f` | str | "markdown" | 出力形式: "markdown" \| "json" |
| `--output` | `-o` | Path | None | 結果ファイル出力先 |
| `--model` | `-m` | str | None | 全エージェントのモデルオーバーライド |
| `--max-turns` | | int | 30 | エージェントあたりの最大ターン数 |
| `--timeout` | `-t` | int | 300 | エージェントあたりのタイムアウト(秒) |
| `--base` | `-b` | str | "main" | diff 比較元ブランチ（diff モードのみ、他モードでは無視） |
| `--issue` | | int | None | 関連 Issue 番号（全モードで使用可能） |
| `--verbose` | `-v` | flag | false | 詳細出力（エラー詳細、進行状況） |
| `--cost` | | flag | false | コスト情報を表示 |
| `--no-confirm` | | flag | false | ファイル数制限の確認をスキップ（file モードのみ、他モードでは無視） |

### file モードの詳細

**ディレクトリ指定**:
```bash
8moku src/        # src/ 配下を再帰探索（深さ制限なし）
```

**glob パターン**:
```bash
8moku "src/**/*.py"   # シェル展開を避けるためクォート推奨
```

**Git 非依存**: file モードは Git リポジトリ外でも動作可能。git 管理外の執筆タスク（ドキュメント、文章等）のレビューに対応する。

**ファイル数制限**: 指定されたファイル数（glob 展開・ディレクトリ再帰探索後の最終ファイル数）が設定項目 `max_files_per_review`（デフォルト: 100）を超える場合、警告メッセージを表示し確認を求める。`--no-confirm` オプションで回避可能。

**その他の動作**:
- シンボリックリンクを指定した場合、リンク先の実体ファイルをレビュー対象とする
- `.hachimoku/` ディレクトリが見つからない場合、デフォルト設定でレビューを実行する（警告メッセージを表示）
- diff モード・PR モードと file モードは同時に指定できない（`8moku 123 src/auth.py` はエラー）
- `--issue` オプションは file モードでも使用可能。Issue 番号がエージェントのプロンプトコンテキストに含まれ、エージェントが `gh` コマンド等のツールで自律的に詳細情報を取得する（FR-031）

## agents サブコマンド

### agents list

利用可能な全エージェント（ビルトイン + カスタム）を一覧表示。

```
$ 8moku agents list
Name                    Model   Phase   Schema
──────────────────────────────────────────────────
code-reviewer           opus    main    scored_issues
silent-failure-hunter   sonnet  main    severity_issues
test-analyzer           sonnet  main    rated_gaps
type-design-analyzer    sonnet  main    multi_dimension_analysis
comment-analyzer        sonnet  main    categorized_findings
code-simplifier         opus    final   suggestions
security-reviewer *     opus    main    scored_issues     ← カスタム

* = プロジェクトカスタムエージェント
```

### agents show \<name\>

エージェントの詳細情報を表示。

```
$ 8moku agents show code-reviewer

Name:         code-reviewer
Model:        opus
Tools:        Read, Glob, Grep
Schema:       scored_issues
Phase:        main
Source:        builtin (agents/code-reviewer.toml)

Applicability:
  Always:     true

Description:
  Review code for bugs, security vulnerabilities, and project
  guidelines compliance. Reports only high-confidence issues (>=80).
```

## config サブコマンド

### config show

現在有効な設定を表示（設定ファイル階層の解決結果）。

## 終了コード

| コード | 意味 |
|-------|------|
| 0 | レビュー完了、Critical / Important issue なし |
| 1 | レビュー完了、Critical issue あり |
| 2 | レビュー完了、Important issue あり（Critical なし） |
| 3 | 実行エラー（SDK 接続失敗、全エージェント失敗等） |
| 4 | 入力エラー（PR 未発見、ファイル未発見、diff/PR モードでの Git リポジトリ外実行、`gh` 未認証等） |

**file モード特有のエラー**:
- 指定ファイルが存在しない → 終了コード 4
- glob パターンにマッチするファイルがない → 終了コード 0（レビュー対象なし、正常終了）
- ディレクトリが空 → 終了コード 0（レビュー対象なし、正常終了）

CI/CD で利用:

```yaml
# GitHub Actions
- run: 8moku --parallel --format json
  continue-on-error: true
  id: review
- if: steps.review.outcome == 'failure'
  run: echo "Review found critical issues"
```

## レビュー結果蓄積

レビュー結果は `.hachimoku/reviews/` に JSONL 形式で自動蓄積される（デフォルト ON、`save_reviews = false` で無効化）。

共通メタデータ（全モード共通）: レビューモード判別キー（`review_mode`）、レビュー実行日時、AgentResult リスト、全体サマリー

| レビューモード | 蓄積先ファイル | モード固有メタデータ |
|------------|-------------|-----------------|
| diff | `diff.jsonl` | コミットハッシュ、ブランチ名 |
| PR | `pr-{番号}.jsonl` | コミットハッシュ、PR 番号 |
| file | `files.jsonl` | ファイルパスリスト、作業ディレクトリ |

各行は独立した JSON オブジェクトとして追記される。

## 出力例

### Markdown 出力（デフォルト）

```markdown
# hachimoku Review Report

## Critical Issues (2 found)

### [code-reviewer] Null reference bug
- **File**: src/auth/login.py:45
- **Confidence**: 95
- **Issue**: `user.email` accessed without null check after `find_user()` which can return None
- **Fix**: Add `if user is None: raise UserNotFoundError(username)`

### [silent-failure-hunter] Silent failure in API client
- **File**: src/api/client.py:78
- **Severity**: CRITICAL
- **Issue**: Broad `except Exception` catches and logs but continues, masking connection errors
- **Fix**: Catch specific `httpx.HTTPError` and re-raise

## Important Issues (3 found)
...

## Suggestions (1 found)
...

## Strengths
- Well-designed type invariants in domain models
- Comprehensive error messages in validation logic

## Agents Summary
| Agent                  | Status  | Duration | Issues |
|------------------------|---------|----------|--------|
| code-reviewer          | ✓       | 45s      | 1C 2I  |
| silent-failure-hunter  | ✓       | 32s      | 1C 1I  |
| test-analyzer          | ✓       | 28s      | 0C 0I  |
| type-design-analyzer   | skipped | -        | -      |
| comment-analyzer       | timeout | -        | -      |
| code-simplifier        | ✓       | 38s      | 1S     |
```

### JSON 出力

`--format json` 時は `ReviewReport.model_dump_json()` の完全な構造化出力。
詳細は `06-output-format.md` を参照。
