# Data Model: CLI インターフェース・初期化

**Feature**: 006-cli-interface | **Date**: 2026-02-07

## 新規エンティティ

### ExitCode

**場所**: `src/hachimoku/cli/_exit_code.py`

| フィールド | 型 | 値 | 説明 |
|-----------|-----|-----|------|
| SUCCESS | int | 0 | 問題なし、またはレビュー対象なし |
| CRITICAL | int | 1 | Critical 重大度の問題検出 |
| IMPORTANT | int | 2 | Important 重大度の問題検出（Critical なし） |
| EXECUTION_ERROR | int | 3 | 全エージェント失敗 |
| INPUT_ERROR | int | 4 | 入力エラー（引数解析・ファイル未発見等） |

**型**: `IntEnum`（`enum.IntEnum` を継承。`IntEnum` 自体が `int` のサブクラス）
**関係**: `EngineResult.exit_code`（0-3）から `ExitCode` への変換は直接キャスト可能。INPUT_ERROR(4) は CLI 層で直接設定。
**移行**: 既存の `severity.py` の `EXIT_CODE_SUCCESS` 等の定数は、ExitCode 導入後に ExitCode メンバーへの参照に置き換える。`determine_exit_code()` の戻り値型も `ExitCode` に変更する。

---

### ResolvedInput

**場所**: `src/hachimoku/cli/_input_resolver.py`

位置引数の解析結果を表す判別共用体。

| バリアント | フィールド | 型 | 説明 |
|-----------|-----------|-----|------|
| DiffInput | (なし) | - | diff モード（引数なし） |
| PRInput | pr_number | int (gt=0) | PR モード |
| FileInput | paths | tuple[str, ...] (min_length=1) | file モード（未展開パス） |

**型**: `Annotated[Union[DiffInput, PRInput, FileInput], Field(discriminator="mode")]`
**バリデーション**: PRInput と FileInput の混在は `resolve_input()` 関数がエラーを返す
**関係**: ResolvedInput → ReviewTarget への変換を `_app.py` が行う（config の base_branch と CLI `--issue` オプションの issue_number を付加）

---

### ResolvedFiles

**場所**: `src/hachimoku/cli/_file_resolver.py`

ファイル解決の結果。

| フィールド | 型 | 説明 |
|-----------|-----|------|
| paths | tuple[str, ...] | 展開・正規化済みのファイルパスリスト |
| warnings | tuple[str, ...] | 循環参照等の警告メッセージ |

**型**: `HachimokuBaseModel`（frozen=True, extra="forbid"）
**バリデーション**: paths は min_length=1（空の場合は呼び出し側で処理）

---

### InitResult

**場所**: `src/hachimoku/cli/_init_handler.py`

init コマンドの実行結果。

| フィールド | 型 | デフォルト | 説明 |
|-----------|-----|-----------|------|
| created | tuple[Path, ...] | () | 新規作成されたファイル/ディレクトリ |
| skipped | tuple[Path, ...] | () | 既存のためスキップされたファイル/ディレクトリ |

**型**: `HachimokuBaseModel`（frozen=True, extra="forbid"）
**関係**: `run_init()` の戻り値。`_app.py` の `init` サブコマンドが結果を stderr に表示する。

---

## 既存エンティティの利用（変更なし）

### ReviewTarget（005-review-engine）

CLI 層が構築して `run_review()` に渡す。

| バリアント | 構築元 |
|-----------|--------|
| DiffTarget(mode="diff", base_branch, issue_number) | DiffInput + config.base_branch + --issue |
| PRTarget(mode="pr", pr_number, issue_number) | PRInput + --issue |
| FileTarget(mode="file", paths, issue_number) | FileInput → ResolvedFiles + --issue |

### HachimokuConfig（004-configuration）

CLI オプション → `config_overrides: dict[str, object]` → `resolve_config()` で解決。

### EngineResult（005-review-engine）

`run_review()` の戻り値。`exit_code` (0-3) と `report` を含む。

### AgentDefinition / LoadResult（003-agent-definition）

`agents` サブコマンドで `load_agents()` を使ってエージェント一覧を取得。

---

## 状態遷移

### CLI 実行フロー

```
[引数パース] → [入力モード判定] → [設定上書き辞書構築]
    │                                      │
    ├─ InputError → ExitCode.INPUT_ERROR   │
    │                                      │
    └─ OK → [ReviewTarget 構築] → [run_review(target, config_overrides)]
                                           │
                                    EngineResult
                                           │
                                    ExitCode(exit_code)
```

### init サブコマンドフロー

```
[Git リポジトリ確認] → [.hachimoku/ 確認]
    │                        │
    ├─ Not Git → EXIT 4      ├─ 存在しない → 全ファイル生成
    │                        ├─ 存在 + --force → 全ファイル上書き
    └─ OK ─────────────────→ └─ 存在 + no force → 不足ファイルのみ生成
```
