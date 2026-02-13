---
name: ccusage-analysis
description: ccusage スナップショット差分と JSONL セッションログ解析による hachimoku レビューのトークン消費・コスト分析レポート生成。
---

# ccusage-analysis

ccusage の before/after スナップショットから差分を算出し、JSONL セッションログを解析して
セレクター・レビュー・集約エージェントの個別効率（リクエスト数、ツール呼び出し、重複読み取り等）を測定する。

## 使用方法

```bash
# フルワークフロー: before → 8moku 実行 → after → 分析
/ccusage-analysis 197

# 既存スナップショットからの分析のみ
/ccusage-analysis 197 --analyze-only

# 個別フェーズ実行
/ccusage-analysis 197 --phase before
/ccusage-analysis 197 --phase after

# セッションログ解析のみ（時間範囲指定）
/ccusage-analysis 197 --sessions-only --after "2026-02-13T10:00:00" --before "2026-02-13T11:00:00"
```

ラベルは PR 番号等の短い識別子。ファイル名は `before-197.json` / `after-197.json` のようになる。

## Operating Constraints

- **READ-ONLY ANALYSIS + REPORT WRITE**: ccusage コマンド実行とレポート生成のみ。hachimoku ソースコードは変更しない
- **実測値のみ使用**: 推定値は使わず、実際の JSON 値・ログデータから算出する
- **Prerequisites**: `npx ccusage` が実行可能であること（Node.js + ccusage インストール済み）
- **環境変数**: `PROJECT_ROOT` が設定済みであること

## 引数パース

`$ARGUMENTS` から以下を抽出する。

**必須引数:**

| 引数 | 説明 |
|------|------|
| `<label>` | 分析ラベル（例: `197`）。ファイル名・レポート名・8moku ターゲットに使用 |

**モードオプション（排他的）:**

| フラグ | 説明 |
|--------|------|
| なし | フルワークフロー（Phase 1〜5 すべて実行） |
| `--analyze-only` | 既存の `before-<label>.json` / `after-<label>.json` から分析のみ（Phase 4〜5） |
| `--phase before` | before スナップショットのみ取得（Phase 1） |
| `--phase after` | after スナップショット取得 + 分析（Phase 3〜5） |
| `--sessions-only` | JSONL セッションログ解析のみ（Phase 5） |

**時間範囲オプション（`--sessions-only` 時に使用）:**

| フラグ | 説明 |
|--------|------|
| `--after <ISO8601>` | セッション開始時刻の下限 |
| `--before <ISO8601>` | セッション終了時刻の上限 |

**出力パス:** `.md` で終わる引数があれば出力パスとして使用。未指定時は `$PROJECT_ROOT/ai_working/ccusage-analysis-<label>.md`。

## 実行手順

### Phase 1: Before スナップショット

```bash
npx ccusage --json > $PROJECT_ROOT/ai_working/before-<label>.json
```

1. 出力が有効な JSON であることを確認（`daily` と `totals` キーの存在チェック）
2. 取得した `totals.totalCost` をユーザーに報告
3. 現在時刻を `phase2_start_time` として記録（ISO 8601 形式）

### Phase 2: hachimoku 実行

```bash
uv --directory $PROJECT_ROOT run 8moku <label>
```

1. 実行完了を待機
2. 終了時刻を `phase2_end_time` として記録（ISO 8601 形式）
3. 終了コードを記録（0=成功, 1=Critical, 2=Important, 3=実行エラー, 4=入力エラー）

### Phase 3: After スナップショット

```bash
npx ccusage --json > $PROJECT_ROOT/ai_working/after-<label>.json
```

1. 出力が有効な JSON であることを確認
2. スナップショット取得完了をユーザーに報告

### Phase 4: コスト・トークン分析

before/after の JSON ファイルを Read ツールで読み込み、以下を計算する。

#### ccusage JSON スキーマ

```json
{
  "daily": [{
    "date": "YYYY-MM-DD",
    "inputTokens": 0, "outputTokens": 0,
    "cacheCreationTokens": 0, "cacheReadTokens": 0,
    "totalTokens": 0, "totalCost": 0.0,
    "modelsUsed": ["model-name"],
    "modelBreakdowns": [{
      "modelName": "model-name",
      "inputTokens": 0, "outputTokens": 0,
      "cacheCreationTokens": 0, "cacheReadTokens": 0,
      "cost": 0.0
    }]
  }],
  "totals": {
    "inputTokens": 0, "outputTokens": 0,
    "cacheCreationTokens": 0, "cacheReadTokens": 0,
    "totalCost": 0.0, "totalTokens": 0
  }
}
```

#### 差分計算手順

1. **totals 差分**: 全フィールドについて `after.totals[field] - before.totals[field]`
2. **モデル別差分（実行日のみ）**:
   - 実行日 = `phase2_start_time` の日付部分（`YYYY-MM-DD`）
   - before/after 両方の `daily` から該当日のエントリを取得
   - 同じ `modelName` について各トークンフィールドの差分を計算
   - before に該当日エントリがない場合、after の値をそのまま差分とする
3. `--analyze-only` の場合は `phase2_start_time` がないため、after の最終日付エントリを使用する

### Phase 5: セッションログ解析

#### 5-1. 対象ファイルの特定

セッションログの場所: `~/.claude/projects/-home-driller-repo-hachimoku/*.jsonl`

```bash
find ~/.claude/projects/-home-driller-repo-hachimoku/ -name "*.jsonl" -newermt "<phase2_start_time>" ! -newermt "<phase2_end_time>"
```

`--sessions-only` の場合は `--after` / `--before` の値を使用する。

#### 5-2. セッション種別の判定

各 JSONL ファイルの最初の `type=user` 行（通常は2行目）の `message.content` を読み取る。

| 種別 | 識別条件 | ソース |
|------|---------|--------|
| Selector | `"## Available Agents"` を含む | `src/hachimoku/engine/_instruction.py:334` |
| Aggregator | `"# Agent Review Results"` で始まる | `src/hachimoku/engine/_aggregator.py:56` |
| Review | 上記いずれにも該当しない | — |

#### 5-3. JSONL パース方法

**重要: JSONL パースの注意事項**

1. JSONL は 1 行 = 1 JSON。`json.load()` ではなく行ごとに `json.loads()` を使用すること
2. `message.content` は **文字列の場合とリスト（配列）の場合がある**。型チェック必須
3. `type == "queue-operation"` の行には `message` フィールドが存在しない。スキップすること
4. 同一 `requestId` を持つ複数の assistant 行が存在する（ストリーミング中間更新）。`requestId` でグループ化して 1 リクエストとしてカウントすること
5. ツール呼び出しの `input` は辞書型。重複検出時は `json.dumps(input, sort_keys=True)` で正規化して比較すること
6. `message.usage` の数値が 0 や 1 等の小さい値でも無視しないこと（ストリーミング差分値のため）

**各行の構造:**

```
{
  "type": "queue-operation" | "user" | "assistant" | "progress",
  "timestamp": "ISO 8601",
  "requestId": "req_xxx",        // assistant 行のみ
  "message": {
    "role": "user" | "assistant",
    "content": "文字列" | [{type: "text", text: "..."} | {type: "tool_use", name: "...", input: {...}, id: "..."}],
    "usage": {                    // assistant 行のみ
      "input_tokens": 0,
      "output_tokens": 0,
      "cache_creation_input_tokens": 0,
      "cache_read_input_tokens": 0
    }
  }
}
```

**Bash ツールで実行する Python パーススニペット:**

```python
import json, sys
from collections import defaultdict
from datetime import datetime

def parse_session(jsonl_path):
    entries = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entries.append(json.loads(line))

    # セッション種別判定
    session_type = "unknown"
    for entry in entries:
        if entry.get("type") == "user" and "message" in entry:
            content = entry["message"].get("content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = " ".join(
                    item.get("text", "") for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                )
            else:
                text = ""
            if "## Available Agents" in text:
                session_type = "selector"
            elif text.startswith("# Agent Review Results"):
                session_type = "aggregator"
            else:
                session_type = "review"
            break

    # メトリクス収集
    request_ids = set()
    tool_counts = defaultdict(int)
    tool_calls_detail = []
    timestamps = []

    for entry in entries:
        if "timestamp" in entry:
            timestamps.append(entry["timestamp"])
        if entry.get("type") != "assistant":
            continue
        if "message" not in entry:
            continue

        req_id = entry.get("requestId")
        if req_id:
            request_ids.add(req_id)

        content = entry["message"].get("content", [])
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "tool_use":
                    name = item.get("name", "unknown")
                    inp = item.get("input", {})
                    tool_counts[name] += 1
                    tool_calls_detail.append((name, json.dumps(inp, sort_keys=True)))

    # 重複検出
    seen = defaultdict(int)
    for name, inp_json in tool_calls_detail:
        key = f"{name}::{inp_json}"
        seen[key] += 1
    duplicates = {k: v for k, v in seen.items() if v > 1}
    total_duplicate_calls = sum(v - 1 for v in seen.values() if v > 1)

    # 所要時間
    duration_sec = 0
    if len(timestamps) >= 2:
        t0 = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))
        t1 = datetime.fromisoformat(timestamps[-1].replace("Z", "+00:00"))
        duration_sec = (t1 - t0).total_seconds()

    return {
        "type": session_type,
        "requests": len(request_ids),
        "tool_counts": dict(tool_counts),
        "total_tool_calls": sum(tool_counts.values()),
        "duplicates": total_duplicate_calls,
        "duplicate_details": {k: v for k, v in duplicates.items()},
        "duration_sec": duration_sec,
    }

# 使用例: 引数のJSONLファイルを解析して結果を出力
for path in sys.argv[1:]:
    result = parse_session(path)
    print(f"\n=== {path} ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
```

このスニペットを対象 JSONL ファイルに対して実行し、結果をレポートに反映する。

#### 5-4. メトリクス収集

各セッションについて以下を算出する:

| メトリクス | 算出方法 |
|-----------|---------|
| API リクエスト数 | `requestId` のユニーク数 |
| ツール呼び出し合計 | `type == "tool_use"` の要素数 |
| 重複ツール呼び出し | 同一 `name` + 同一 `input` の超過分 |
| 所要時間 | 最初〜最後のエントリの `timestamp` 差 |

**セレクター固有メトリクス:**
- `StructuredOutput` ツール呼び出しの `input.selected_agents` リスト長
- 情報収集ツール（Read, Grep, Glob, Bash）の使用回数

### Phase 6: レポート生成

以下の構造で Markdown レポートを生成し、Write ツールで保存する。

```markdown
# ccusage Analysis Report: <label>

**Generated**: <ISO 8601>
**Execution**: <phase2_start_time> - <phase2_end_time>
**Target**: <label>
**hachimoku Exit Code**: <exit code>

---

## Cost Summary

| Metric | Before | After | Diff |
|--------|--------|-------|------|
| Total Cost ($) | <before> | <after> | **<diff>** |
| Input Tokens | <before> | <after> | <diff> |
| Output Tokens | <before> | <after> | <diff> |
| Cache Creation Tokens | <before> | <after> | <diff> |
| Cache Read Tokens | <before> | <after> | <diff> |
| Total Tokens | <before> | <after> | <diff> |

## Model Breakdown (execution day)

| Model | Input | Output | Cache Create | Cache Read | Cost ($) |
|-------|-------|--------|-------------|------------|----------|
| <modelName> | <diff> | <diff> | <diff> | <diff> | <diff> |
| **Total** | <sum> | <sum> | <sum> | <sum> | **<sum>** |

---

## Session Analysis

### Overview

| Session | Type | Requests | Tool Calls | Duplicates | Duration |
|---------|------|----------|------------|------------|----------|
| <uuid-short> | Selector | <N> | <N> | <N> | <N>s |
| <uuid-short> | Review | <N> | <N> | <N> | <N>s |
| <uuid-short> | Aggregator | <N> | <N> | <N> | <N>s |
| **Total** | — | **<sum>** | **<sum>** | **<sum>** | **<sum>s** |

### Selector Session Detail

**Session**: <uuid>
**Requests**: <N> API round-trips
**Duration**: <N>s

#### Tool Call Breakdown

| Tool | Count | Unique | Duplicate |
|------|-------|--------|-----------|
| <tool> | <N> | <N> | <N> |

#### Duplicate Tool Calls

- `<tool_name>(<input概要>)` x <N> 回

### Review Agent Sessions

(各レビューエージェントのツール呼び出しサマリー)

### Aggregator Session

(集約エージェントのメトリクス)

---

## Appendix: Raw Data

<details>
<summary>Before Snapshot Totals</summary>
(JSON)
</details>

<details>
<summary>After Snapshot Totals</summary>
(JSON)
</details>
```

レポート生成後、ユーザーに以下を報告する:
- レポート保存先パス
- 総コスト差分
- セレクターのリクエスト数・ツール呼び出し数

## エラーハンドリング

| エラー | アクション |
|--------|----------|
| `npx ccusage` 実行失敗 | Node.js / ccusage のインストール状態を確認するメッセージを表示して終了 |
| before/after JSON が不正 | パースエラーの詳細を表示して終了 |
| `--phase after` で `before-<label>.json` が存在しない | 不足ファイルを明示してエラー終了 |
| `--analyze-only` で before/after どちらかが存在しない | 不足ファイルを明示してエラー終了 |
| 対象 JSONL ファイルが 0 件 | 「該当時間帯にセッションログが見つかりません」と報告。コスト分析部分のみ出力 |
| hachimoku 実行がエラー終了 | 終了コードをレポートに記録し、分析は続行 |
