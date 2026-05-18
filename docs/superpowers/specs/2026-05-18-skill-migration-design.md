# hachimoku Agent Skills 移行 設計書

- 作成日: 2026-05-18
- 対象: hachimoku（マルチエージェントコードレビュー CLI）
- 種別: 破壊的変更（アーキテクチャ移行）
- 移行後バージョン: 0.1.0

## 1. 背景と動機

2026-06-15 以降、Claude の有料プランでは `claude -p` などの**プログラム的利用**が
対話サブスクリプションとは別の**従量課金枠**（月次クレジット → API レート課金）から
引かれるようになる。

hachimoku は現在、自身が `claude -p` をオーケストレーションする CLI である
（`claudecode_model.ClaudeCodeModel` を pydantic-ai 経由で使用）。このため、
`hachimoku review` を実行するたびにプログラム枠を消費することになる。

本移行の目的は、**追加の従量課金を回避すること**である。レビュー処理を、
すでに起動しているユーザーの対話エージェント（Claude Code）の**セッション内**で
実行すれば、利用は従来どおり対話サブスクリプションのレート枠に収まる。

> 注: 対話レート枠の消費自体は従来どおりであり、本移行が削減対象とするのは
> 6/15 以降に新設される「追加の従量課金」のみである。

## 2. ゴール / 非ゴール

### ゴール

- `claude -p` 直接実行（プログラム的課金経路）の撤廃。
- レビュー処理を Claude Code セッション内のサブエージェントで実行する。
- 集約・重要度分類・レポート化・JSONL 履歴を、LLM 不要の決定的処理として維持する。
- TOML によるデータ駆動エージェント定義（憲法 Art.3）を維持する。
- `respond-review` が参照する JSONL フィールド（findings / severity / status）の互換を維持する。

### 非ゴール（v1）

- **CI / 非対話実行**（GitHub Actions 等）。旧 `claude -p` CI 経路は削除する。
  改善余地があれば将来検討する。
- **Codex / GitHub Copilot 対応**、**APM 配布**。v2 で扱う。
- **per-agent トークン / コスト追跡**。Claude Code ネイティブのセッションログに委譲する。
- **LLM ベースのセレクター / アグリゲーター**。決定的 CLI に置換する。

## 3. 最終形態

hachimoku は「`claude -p` をオーケストレーションする CLI」から、
**Claude Code プラグイン + 薄い CLI** の 2 部構成へ移行する。

```text
┌─ Claude Code プラグイン (hachimoku) ───────────────┐
│  commands/   /hachimoku:review  ← エントリポイント   │
│  skills/     orchestrator SKILL.md                  │
│  agents/     13 個の変換済みサブエージェント .md      │
│  scripts/    block-git-mutations.sh                 │
│  plugin.json                                        │
└─────────────────────────────────────────────────────┘
              │ 呼び出し（LLM 不要・無課金）
              ▼
┌─ 薄い CLI (hachimoku, Python・LLM なし) ────────────┐
│  hachimoku init       .hachimoku/ 雛形生成           │
│  hachimoku build      TOML → サブエージェント.md +    │
│                       manifest.json 変換             │
│  hachimoku select     diff + manifest → 起動リスト    │
│  hachimoku aggregate  findings JSON → 集約レポート     │
│                       + JSONL 履歴追記               │
└─────────────────────────────────────────────────────┘
```

v1 の対象は Claude Code のみ。Codex / Copilot は v2 で APM 配布として別途設計する。

### CLI エントリポイント名

薄い CLI のうちユーザーが直接タイプするのは `init` と `build` のみ。
`select` / `aggregate` はオーケストレーター skill が内部呼び出しするものであり
ユーザーは打たない。

現行 `pyproject.toml` には既に正規名と短縮エイリアスの 2 エントリポイントが
定義済みであり、本移行はこれを維持する（エントリポイント自体の新規作業はない）。

```toml
[project.scripts]
"8moku"   = "hachimoku.cli:main"   # 短縮エイリアス（八目の「八＝8」）
hachimoku = "hachimoku.cli:main"   # 正規名（パッケージ名・ドキュメントと一致）
```

両エントリポイントは同一の `hachimoku.cli:main` を指す（関数名は現行のまま
`main`。本移行で `app` 等へ改名しない）。オーケストレーター skill が生成・実行
する内部呼び出しは可読性のため正規名 `hachimoku` を使い、`8moku` は人間の
入力支援が目的とする。

## 4. コンポーネント

| コンポーネント | 役割 | LLM | 課金 |
|---|---|---|---|
| オーケストレーター skill | ホストに「diff 特定 → select → サブエージェント並列起動 → aggregate → 提示」の手順を指示 | 対話 | サブスク枠 |
| サブエージェント .md ×13 | 各レビュー観点を実行。Bash で git/gh、Read/Grep/Glob。findings を JSON ファイルに書く | 対話（Task 委譲） | サブスク枠 |
| `hachimoku build` | TOML（正）→ サブエージェント .md + manifest.json を機械生成 | なし | 無料 |
| `hachimoku select` | diff と manifest の applicability から起動対象を決定 | なし | 無料 |
| `hachimoku aggregate` | findings JSON を検証・重複排除・重要度分類・レポート化・JSONL 履歴追記 | なし | 無料 |
| `block-git-mutations.sh` | サブエージェントの Bash を監視し git/gh 書き込み系を deny | なし | 無料 |

オーケストレーターは「指揮者」に徹し、diff 本文も findings 本文も自身のコンテキストに
載せない。コンテキストに載るのは起動プランとサブエージェントの短い完了報告のみとする。

## 5. レビュー実行フロー

```text
ユーザー: /hachimoku:review --target branch
   │
   ▼
オーケストレーター skill（メインセッション・コンテキスト軽量）
   │
   │ ① hachimoku select --target branch
   ├─▶ diff 計算（_target / _diff_filter 再利用）+ manifest の applicability 評価
   │     → 起動プラン JSON ＋ run_dir パスを出力
   │
   │ ② フェーズ順に Task ツールで並列ディスパッチ
   ├─▶ EARLY : Task(agentX) ∥ ...
   ├─▶ MAIN  : Task(code-reviewer) ∥ Task(security-analyzer) ∥ ...
   ├─▶ FINAL : Task(agentZ) ∥ ...
   │     各サブエージェント → run_dir/<agent>.json を書き出し
   │     orchestrator には「完了・N 件」程度の短報のみ返す（コンテキスト隔離）
   │
   │ ③ hachimoku aggregate <run_dir>
   ├─▶ 全 JSON を検証・重複排除・重要度分類
   │     → Markdown レポート（stdout）＋ JSONL 履歴追記 ＋ 終了コード
   │
   ▼
ユーザーにレポート提示
```

- **フェーズ**（EARLY / MAIN / FINAL）は維持。フェーズ内は並列（1 ターンに複数 Task 呼び出し）、
  フェーズ間は逐次。順序は manifest 経由でオーケストレーターが尊重する。
- **run_dir 契約**: `select` が一時ディレクトリを作成し、`aggregate` が消費する。
  `<agent>.json` ファイル群を保持する。
- 終了コードは CI 非ゴールのため情報提供用。Markdown レポートが主たる成果物。

## 6. エージェント定義と変換（`hachimoku build`）

TOML を正規定義として維持する（憲法 Art.3）。1 つの `*.toml` から 2 成果物を機械生成する。

### 成果物 ① サブエージェント `<name>.md`

```yaml
---
name:        <- TOML name
description: <- TOML description
model:       <- TOML model から claudecode: プレフィックス除去
tools: Read, Grep, Glob, Bash      <- allowed_tools カテゴリから機械マッピング
hooks:
  PreToolUse:
    - matcher: "Bash"
      hooks:
        - type: command
          command: "${CLAUDE_PLUGIN_ROOT}/scripts/block-git-mutations.sh"
---
<TOML system_prompt 本文。run_git([...]) 等のツール呼び出し記法を
 git ... 形式に定型置換する>

## Output Contract
<pydantic resolved_schema の model_json_schema() から JSON Schema を生成して埋め込み、
 「この形式で run_dir/<name>.json に書け」と指示する>
```

### 成果物 ② `manifest.json` への 1 エントリ

`applicability` / `phase` / `output_schema` 名を保持する。`select` と `aggregate` が参照する。

### 変換のマッピング

| TOML フィールド | 変換先 | 機械変換 |
|---|---|---|
| `name` / `description` | フロントマター同名 | そのまま |
| `model` | フロントマター `model` | `claudecode:` 除去 |
| `system_prompt` | `.md` 本文 | ツール呼び出し記法を定型置換 |
| `allowed_tools`（カテゴリ） | フロントマター `tools` | カテゴリ → ツール名マッピング |
| `output_schema` | 本文末「Output Contract」節 | pydantic → JSON Schema |
| `applicability` / `phase` | manifest.json | そのまま |
| `max_turns` / `timeout` | manifest.json または破棄 | そのまま |

### 配布

- ビルトイン 13 本は hachimoku のパッケージビルド時に変換済みとし、プラグインに同梱する
  （ユーザー環境での変換は不要）。
- ユーザー定義 `.hachimoku/agents/*.toml` は、ユーザーが `hachimoku build` を実行して
  プロジェクトレベルのサブエージェント `.md` を生成する。

## 7. 集約と出力（`hachimoku aggregate`）

### Markdown レポート

`aggregate` は全 `<agent>.json` を読み、検証・重複排除・重要度分類のうえ
`ReviewReport` を組み立て、Markdown を stdout に出力する。

### JSONL 履歴の維持

`save_review_history()` と `models/history.py` を再利用する。`aggregate` が組み立てた
`ReviewReport` から `ReviewHistoryRecord` を構築し、`.hachimoku/reviews/<target>.jsonl` に
1 行追記する。`ReviewHistoryRecord` の discriminator（diff / pr / file / commit）は
不変だが、`results` 配下の `AgentResult` スキーマは §10 のとおり変化する。
`respond-review` は `cost` / `elapsed_time` を機能的に参照しない（findings /
severity / status のみ使用）ため、動作互換は保たれる。

## 8. セキュリティ（読み取り専用担保）

レビュー対象 diff は信頼できない入力であり、プロンプトインジェクションの経路になり得る。
サブエージェントが `git`/`gh` でリポジトリを変更しないことを担保する。

### 担保の方式

- グローバル hook やユーザー設定の変更は**一切使わない**。Claude Code のプラグイン hook は
  全セッションにグローバル発火するため不適切。
- 各サブエージェント `.md` の frontmatter に閉じ込める:
  - `tools` 許可リスト: Edit / Write を渡さない（当該サブエージェント内のみ）。
  - frontmatter `PreToolUse` hook: `git`/`gh` の書き込み系を deny する検証スクリプトを
    指定。当該サブエージェント実行中のみ発火し、終了で解除される。
- プラグインはユーザーの permission ルール（`settings.json`）を破壊的に変更しない。
  Claude Code の仕様上、プラグインは permission ルールを同梱できず、設定の優先順位は
  user / project が上位である。

### `block-git-mutations.sh`

- 脅威モデルは **best-effort の多層防御**であり、完全なサンドボックスではない（ドキュメントに明記）。
- `git`/`gh` の第 1 サブコマンドを**許可リスト方式**で判定する
  （`diff` / `log` / `show` / `status` / `merge-base` / `rev-parse` / `branch` / `ls-files`、
  `gh pr view` / `gh pr diff` / `gh issue view` / `gh api`（GET）など）。
- パイプ・サブシェル・`bash -c` ラップ・`git -c ...` などは deny する。
- 許可リストは既存 `engine/_tools/_git.py` / `_gh.py` の読み取り専用サブコマンド定義を流用する。

### 確認済みの不確実性

サブエージェント frontmatter hook が「当該サブエージェント実行中に完全に隔離される」ことは
公式ドキュメントで強く示唆されるが 100% 明文化されていない。実装フェーズで
「hook が他コンテキストで発火しないこと」を手動検証ステップとして含める。

## 9. エラー処理

旧来 pydantic がモデル境界で型保証していた部分が「parse-and-recover」に変わる。
`aggregate` は破損入力を**明示的にエラー伝播**する（フォールバックせず可視化する）。

| 事象 | 扱い |
|---|---|
| サブエージェントが JSON ファイルを書かなかった | `AgentError(agent_name, "no output")` として記録 |
| JSON が壊れている / スキーマ不適合 | `AgentError(agent_name, 詳細)` として記録 |
| 一部エージェント失敗 | run 全体は失敗させず、レポートに「失敗エージェント」節を出し、成功分で集約継続 |

## 10. スキーマ変更まとめ

| 変更 | 内容 | 理由 |
|---|---|---|
| `CostInfo` クラス削除 | `models/agent_result.py` から全廃 | サブスク前提で金額不要、トークンは CC ネイティブログに存在 |
| `AgentSuccess.cost` 削除 | フィールド削除 | 同上 |
| `AgentResult` 判別共用体の縮小 | `AgentTruncated` / `AgentTimeout` を削除し `AgentSuccess \| AgentError` の 2 肢にする。`ReviewSummary` の集計ロジックも追従 | truncation / timeout は撤去対象の旧エンジン（`max_turns`・asyncio タイムアウト）固有の概念。薄い CLI の `aggregate` は subagent JSON が有効か否かしか判定できず、両肢の生成元が存在しない |
| `elapsed_time` を optional 化 | `AgentSuccess.elapsed_time` を `float \| None` へ。`ReviewSummary` の時間集計も調整 | 薄い CLI から per-agent 実行時間を観測できない |
| issues / score | 不変 | 互換維持 |
| `ReviewHistoryRecord` | discriminator（diff / pr / file / commit）は不変。ただし `results` 配下の `AgentResult` は本表のとおり変化する | `respond-review` は `cost` / `elapsed_time` を機能的に参照しないため動作互換は保たれる |

## 11. 資産の扱い

### 再利用

`models/schemas/*`、`models/severity.py`、`models/exit_code.py`、`models/report.py`、
`models/history.py`、`cli/_history_writer.py`、`engine/_selector.py` の applicability 評価ロジック、
`engine/_diff_filter.py`、`engine/_target.py`、`engine/_aggregator.py` の非 LLM 部分、
`engine/_tools/*` の読み取り専用サブコマンド許可リスト。

### 削除（破壊的変更）

`claudecode_model` 依存、`pydantic-ai` 依存（エンジン本体）、
`engine/_runner.py` / `_engine.py` / `_executor.py` / `_model_resolver.py` /
`_cancel_scope_guard.py` / `_live_progress.py` 等、LLM を起動する `hachimoku review` コマンド。

## 12. 実装スコープ分割

破壊的変更が広範囲なため、SpecKit の spec → plan → implement サイクルを 3 つに分割し、
SP1 から順に進める。各サブプロジェクトは独立した `specs/NNN-xxx/` を持つ。

| # | サブプロジェクト | 内容 | 依存 |
|---|---|---|---|
| SP1 | 薄い CLI 化 | エンジン（pydantic-ai / claudecode_model）削除、`select` / `aggregate` / `init` 実装、モデル再形成（`CostInfo` 削除・`AgentResult` 判別肢縮小・`elapsed_time` optional 化） | なし（基盤） |
| SP2 | 変換パイプライン | `hachimoku build`: TOML → サブエージェント `.md` + `manifest.json`、ツール記法置換、Output Contract 生成 | SP1（再形成スキーマ） |
| SP3 | Claude Code プラグイン | オーケストレーター skill、スラッシュコマンド、`block-git-mutations.sh`、frontmatter hook、`plugin.json`、ビルトイン 13 本同梱 | SP2（変換成果物） |

## 13. リリース戦略

- **移行前タグ**: SP1 着手の最初の手順として、移行前の最終コミット（現時点では
  `main` の `c01682d`・バージョン 0.0.41）にタグを打つ。旧 `claude -p`
  アーキテクチャを復元可能にする。
- **軽量な Release**: 移行前タグに対し、移行を説明するノート付きの GitHub Release を作成する。
  旧 CLI / CI 利用者に「`claude -p` 対応の最終版」を発見可能なアンカーとして提供する。
- **移行後バージョン**: `0.1.0`（pre-1.0 を維持しつつ minor bump でアーキテクチャ破壊を表現）。

## 14. テスト戦略（TDD・1 機能 = 1 テストファイル）

| 対象 | 方式 |
|---|---|
| `hachimoku build` | ゴールデンファイル: TOML fixture → 期待 `.md` + `manifest.json`（記法置換・契約生成を網羅） |
| `hachimoku select` | diff fixture → 期待ディスパッチプラン（既存 `_selector` テスト流用） |
| `hachimoku aggregate` | findings JSON fixture（破損・欠落・スキーマ不適合を含む）→ 期待レポート + 終了コード + JSONL レコード |
| `block-git-mutations.sh` | コマンド文字列 fixture → allow/deny マトリクス（パイプ・サブシェル・`bash -c`・`git -c`） |
| モデル再形成 | `CostInfo` 削除・`AgentResult` 判別肢縮小・`elapsed_time` optional 化に伴う既存テスト調整 |
| frontmatter hook 隔離 | 手動検証ステップ（§8 の不確実性の実地確認） |
| E2E | サンプル diff で 1 回通しのスモークテスト |

## 15. ドキュメント影響

| 対象 | 要否 | 内容 |
|---|---|---|
| `specs/008+` | 要 | SP1〜SP3 の新規 spec。既存 005-review-engine / 006-cli-interface に廃止・置換注記 |
| `docs/ja`・`docs/en` | 要 | `cli.md` / `agents.md` / `configuration.md` / `installation.md` 全面改訂、プラグイン導入手順を新設 |
| `README.md` | 要 | プラグイン導入・新コマンド・`claude -p` 廃止を反映した大改訂 |
| `CLAUDE.md`（プロジェクト） | 要 | Tech Stack から pydantic-ai 除去、コマンド節更新 |

## 16. 未解決事項

- **pydantic-ai 1.97 アップグレードの位置づけ**: 直近の `chore/upgrade-to-pydantic-ai-1.97.0`
  作業は既に `main`（0.0.41）へマージ済みだが、本移行は pydantic-ai 自体を撤去するため、
  当該アップグレードは結果的に無駄になる。SP1 でエンジン削除と同時に pydantic-ai 依存を
  除去する（追加判断は不要）。
- **`<usage>` ブロックの不使用を確定**: per-agent トークンは未ドキュメントの `<usage>`
  ブロックや LLM 転記には頼らず記録しない（§2 非ゴール、§10）。
