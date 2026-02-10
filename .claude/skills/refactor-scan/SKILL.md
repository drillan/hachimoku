---
name: refactor-scan
description: >
  similarity-py を使った重複コード検出とリファクタリング分析レポート生成。
  PR・Issue 単位のスコープ指定にも対応。
  ソースコードは変更せず分析レポートのみ生成する。
disable-model-invocation: true
argument-hint: "[--pr <number>] [--issue <number>] [--path <path>] [output.md]"
---

# refactor-scan

similarity-py を使用してコードベースの重複を検出し、優先度付けリファクタリング提案を含む Markdown レポートを生成する。DRY 原則に基づき分析し、チーム共有可能な形式で保存する。

## 使用方法

```bash
# デフォルト: src/hachimoku 全体 + tests をスキャン
/refactor-scan

# PR の変更ファイルのみスキャン
/refactor-scan --pr 149

# Issue 関連ファイルのみスキャン
/refactor-scan --issue 150

# 指定パスのスキャン
/refactor-scan --path src/hachimoku/engine

# 出力パスとオプション指定
/refactor-scan custom-report.md --pr 149 --threshold 0.90 --min-lines 20
```

## Operating Constraints

**READ-ONLY SCAN + REPORT WRITE**: similarity-py でスキャンしてレポートを生成するが、ソースコード自体は変更しない。

**CLAUDE.md 準拠**: DRY 原則、TDD 必須、品質チェックのルールを厳守する。

**Prerequisites**: similarity-py がインストール済みであること（`cargo install similarity-py`）。

**環境変数**: `PROJECT_ROOT` が設定済みであること。すべてのパス解決は `$PROJECT_ROOT` を基準とする。

## 実行手順

### 1. 引数パース

`$ARGUMENTS` から以下を抽出する。

**スキャンモード**（排他的 — 複数指定時はエラー）:

| フラグ | 値 | 説明 |
|--------|-----|------|
| `--pr` | `<number>` | PR の変更ファイルのみスキャン |
| `--issue` | `<number>` | Issue 関連ファイルのみスキャン |
| `--path` | `<path>` | 指定パスをスキャン |
| なし | — | デフォルト: `$PROJECT_ROOT/src/hachimoku` + `$PROJECT_ROOT/tests` |

**共通オプション**:

| フラグ | デフォルト | 説明 |
|--------|-----------|------|
| `--threshold` | `0.85` | 類似度閾値（0.0-1.0） |
| `--min-lines` | `15` | 最小重複行数 |

**出力パス**: `.md` で終わる引数があれば出力パスとして使用。未指定時は `$PROJECT_ROOT/ai_working/duplication-analysis-YYYY-MM-DD.md`（現在日付）。

### 2. 前提条件チェック

```bash
which similarity-py
```

未インストールの場合、以下を提示して終了:

```
similarity-py がインストールされていません。
インストール: cargo install similarity-py
```

### 3. スキャン対象ファイルの特定

#### 3a. PR モード（`--pr <number>`）

```bash
# 変更ファイル一覧を取得
gh pr diff <number> --name-only
```

1. 出力から `.py` ファイルのみをフィルタ
2. ファイルシステム上に存在しないもの（削除済み）を除外
3. 残ったファイルの共通親ディレクトリを特定
4. ファイルが 0 件の場合「PR に Python ファイルの変更がありません」と報告して終了

#### 3b. Issue モード（`--issue <number>`）

```bash
# Step 1: 関連 PR を検索
gh pr list --search "closes #<number>" --json number --jq '.[].number'

# Step 2: PR が見つからない場合、ブランチを検索
git branch -r --list "*/<number>-*"

# Step 3: ブランチが見つかった場合、差分ファイルを取得
git diff main...<branch> --name-only
```

1. 関連 PR が見つかった場合 → PR モード（3a）と同じスキャンロジックを適用
2. ブランチが見つかった場合 → 差分ファイルから `.py` ファイルをフィルタ
3. どちらも見つからない場合 → エラー表示して終了:
   ```
   Issue #<number> に関連する PR またはブランチが見つかりません。
   --path でスキャン対象を直接指定してください。
   ```

#### 3c. パスモード（`--path <path>`）

指定パスが存在することを確認。存在しない場合はエラー表示して終了。

#### 3d. デフォルトモード

スキャン対象: `$PROJECT_ROOT/src/hachimoku` と `$PROJECT_ROOT/tests`（テストは閾値 0.80、最小行数 10 で別途スキャン）。

### 4. similarity-py 実行

特定されたスキャン対象に対して実行:

```bash
# ソースコードスキャン
similarity-py <対象パス> --threshold <閾値> --min-lines <最小行数> --cross-file --print

# デフォルトモード時のテストスキャン（追加）
similarity-py $PROJECT_ROOT/tests --threshold 0.80 --min-lines 10 --cross-file --print
```

### 5. 優先度判定

検出された重複に以下の基準で優先度を判定:

| 優先度 | 類似度 | 重複行数 | 影響範囲 |
|--------|--------|----------|---------|
| **P0** | >90% | >100行 | クロスモジュール |
| **P1** | >85% | >50行 | 同一モジュール内 |
| **P2** | >80% | >30行 | 同一ファイル内 |
| **P3** | >75% | >15行 | 局所的 |

### 6. レポート生成

以下の構造で Markdown レポートを生成する。

```markdown
# Code Duplication Analysis Report

**Generated**: [ISO 8601 形式]
**Scan Mode**: [Default / PR #NNN / Issue #NNN / Path: xxx]
**Scanned Paths**: [スキャンしたパス一覧]
**Scanned Files**: [PR/Issue モード時: 対象ファイル一覧]
**Threshold**: [閾値]
**Min Lines**: [最小行数]
**Tool**: similarity-py

---

## Executive Summary

- **Total Duplications Found**: [件数]
- **Total Duplicate Lines**: [行数]
- **Estimated Code Reduction Potential**: [削減可能行数]
- **Priority Distribution**: P0: [件数], P1: [件数], P2: [件数], P3: [件数]

---

## Priority Findings

### P0: Critical Duplications

#### P0-[番号]: [タイトル]

**Metrics**: Similarity [XX]%, [行数] lines, [ファイル数] files
**Location**:
- `[ファイルパス1]:[開始行]-[終了行]`
- `[ファイルパス2]:[開始行]-[終了行]`

**Common Pattern**: [共通ロジックの箇条書き]
**Differences**: [差異の箇条書き]
**Suggested Pattern**: [Template Method / Strategy / Factory / 共通関数抽出 / 基底クラス拡張]

**Refactoring Proposal**:
（型注釈付きのコード例）

**Estimated Impact**: ~[削減行数] lines reduced, [HIGH/MEDIUM/LOW] maintainability improvement

---

### P1-P3

（P0 と同じ構造で、優先度が下がるにつれ詳細度を低くする。P3 は件数と概要のみ。）

---

## Refactoring Roadmap

### Immediate Actions
[P0 項目: 実装方針と検証方法]

### Short-term Actions
[P1 項目]

### Backlog
[P2-P3 概要]

---

## Metrics

- **Total Files Scanned**: [ファイル数]
- **Duplication Percentage**: [重複率]%
- **Potential Code Reduction**: ~[行数] lines

---

## Appendix: Raw Output

（similarity-py の生出力を details タグで添付）
```

CLAUDE.md のルール違反（DRY 原則、マジックナンバー等）を検出した場合は、該当する Priority Finding 内で明記すること。

### 7. レポート保存と報告

Write ツールで出力パスに保存。保存後、ユーザーに以下を報告:

```
レポート: [保存先パス]
検出件数: [件数]（P0: [件数], P1: [件数], P2: [件数], P3: [件数]）
削減可能行数: ~[行数] lines

次のアクション:
1. レポートをレビュー
2. GitHub Issue 作成: gh issue create --body-file [保存先パス]
3. P0 リファクタリング実行
```

## エラーハンドリング

- **similarity-py 未インストール**: インストール方法を提示して終了
- **スキャン対象パスが存在しない**: エラーメッセージと有効なパス例を表示
- **PR/Issue 番号が無効**: `gh` コマンドのエラーを表示して終了
- **重複 0 件**: 「重複は検出されませんでした」の成功レポートを生成
- **`--pr`, `--issue`, `--path` の複数指定**: エラーメッセージを表示して終了

## 分析ガイドライン

- **ソースコード変更禁止**: レポート生成のみ
- **実測値のみ使用**: similarity-py の出力を使用し、推測値は明示
- **具体的な提案**: 理論ではなく実際のコードスニペットを引用
- **型注釈付き**: レポート内のコード例は型注釈を含む
- **50 件超の場合**: 上位 30 件に集約し、残りはサマリー表示
