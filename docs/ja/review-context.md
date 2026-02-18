# Review Context ガイドライン

Review Context は GitHub Issue テンプレートに含まれるセクションで、コードレビュー時にレビューエージェントが参照する補足情報を提供します。
diff に含まれない関連情報を記載することで、レビューの分析範囲を広げ、指摘の精度向上に寄与します。

```{contents}
:depth: 2
:local:
```

## 背景

hachimoku のレビューエージェントは、通常 diff 内のコードを分析対象とします。
しかし、変更が他のファイルや設定に波及する場合、diff のみの分析では影響を見逃すことがあります。

例として、設定のデフォルト値を変更した際に、テンプレート内の旧デフォルト値が更新されていないケースがあります。
このような diff 外の波及影響は、Review Context に影響範囲を記載することでエージェントの調査対象に含められます。

## 各フィールドの記入ガイド

Review Context は 3 つのフィールドで構成されます。

### 関連仕様

変更に関連する仕様書・ドキュメントへの参照を記載します。

目的
: レビューエージェントが仕様との整合性を検証するための情報源を提供する

記入する内容:

- spec ファイルのパスとセクション・要件番号
- 関連する憲法の Article
- 関連する Issue 番号や PR 番号
- docs/ 配下の関連ドキュメント

粒度の目安:

- ファイルパスだけでなく、具体的なセクションや要件 ID を併記する
- 複数の仕様に関連する場合はそれぞれ記載する

良い例:

```text
# Issue #152 より — spec のセクションと要件 ID を明示
- specs/005-review-engine/spec.md — FR-RE-002（パイプライン Step 1-9）、FR-RE-008（ReviewReport 集約）
- specs/005-review-engine/data-model.md — ReviewReport 構造

# Issue #150 より — 憲法の Article と関連する原則を明示
- 憲法 Art.4（シンプルさ）— 不必要なラッパー・過剰抽象化禁止
- specs/003-agent-definition/spec.md — エージェント定義の TOML 構造
```

不十分な例:

```text
# ファイル全体を指しており、エージェントが参照すべき箇所を特定できない
- specs/005-review-engine/spec.md
```

### 影響範囲

直接変更するファイル以外に影響を受ける可能性のあるファイル・設定を記載します。

目的
: レビューエージェントが diff 外の波及影響を調査するための対象を特定する

記入する内容:

- diff に含まれないが影響を受けるファイルのパス
- 影響の種類（設定の互換性、インターフェース変更、テスト等）
- 変更前後の具体的な値がある場合はテーブル形式も有効

粒度の目安:

- ディレクトリではなくファイル単位で記載する
- 影響の種類を括弧で補足する

良い例:

```text
# Issue #155 より — テーブル形式で影響ファイル・現在の値・変更後の値を列挙
| ファイル | 現在の値 | 変更後 |
|----------|----------|--------|
| src/hachimoku/models/config.py:83 | claudecode:claude-sonnet-4-5 | claudecode:claude-opus-4-6 |
| src/hachimoku/agents/_builtin/code-reviewer.toml:3 | anthropic:claude-sonnet-4-5 | anthropic:claude-opus-4-6 |

# Issue #148 より — ファイルパス + 変更内容の要約を箇条書き
- src/hachimoku/engine/_selector.py — SelectorOutput モデルに 4 フィールド追加
- src/hachimoku/engine/_instruction.py — build_selector_context_section() 新規関数追加
- src/hachimoku/engine/_engine.py — Step 5-6 間にメタデータ伝播ロジック追加

# Issue #150 より — 変更対象が限定的な場合は簡潔に
- src/hachimoku/agents/_builtin/type-design-analyzer.toml（唯一の変更対象）
- Python コード変更なし
```

不十分な例:

```text
# ディレクトリ全体を指しており、調査範囲を絞り込めない
- src/hachimoku/
```

### 既存パターン参照

一貫性を保つべき既存の類似実装を記載します。

目的
: レビューエージェントが一貫性の評価基準を持ち、既存パターンとの乖離を検出できるようにする

記入する内容:

- 参照先のファイルパス
- 具体的なパターン名（クラス、関数、構造等）
- 何が「類似」かの説明

粒度の目安:

- 「同様のパターン」だけでなく、何のパターンかを具体的に示す

良い例:

```text
# Issue #148 より — 関数名と役割を明示
- src/hachimoku/engine/_instruction.py の build_review_instruction() — user_message 構築の既存パターン
- src/hachimoku/engine/_engine.py Step 4-6 — 現在の user_message からコンテキスト構築フロー

# Issue #152 より — 同一アーキテクチャパターンの参照先を列挙
- src/hachimoku/engine/_selector.py の SelectorOutput — 構造化出力モデルのパターン
- src/hachimoku/agents/models.py の SelectorDefinition — TOML 定義モデルのパターン
- src/hachimoku/agents/_builtin/selector.toml — ビルトイン TOML 定義のパターン

# Issue #155 より — 処理ロジックのパターン
- _model_resolver.py でプレフィックスに応じたモデル解決を実行
```

不十分な例:

```text
# 何のパターンかが不明で、エージェントが一貫性を評価できない
- 同じパターンで実装
```

## レビュー品質への影響

Review Context の記入状況は、レビューエージェントの分析範囲に影響します。

関連仕様が記入されている場合
: エージェントは仕様との整合性を検証対象に含めます。記入されていない場合、仕様違反の検出はエージェント自身の調査能力に依存します。

影響範囲が記入されている場合
: エージェントは記載されたファイルを調査対象に含めます。記入されていない場合、diff 外の波及影響（設定ファイルの旧値残存、インターフェース不整合等）を見逃す可能性があります。

既存パターンが記入されている場合
: エージェントは既存パターンとの一貫性を評価基準に含めます。記入されていない場合、プロジェクト内の類似コードとの不整合を検出できない場合があります。

## 記入の原則

分かる範囲で記入する
: 確実に把握している情報のみ記載します。全フィールドの記入は求められません。

空欄は許容される
: 不正確な情報はエージェントを誤った方向に誘導するため、確信がない場合は空欄にします。

後から追記できる
: Issue 作成後に判明した情報はコメントで補足できます。

推測を含めない
: 「おそらく影響がある」程度の不確実な情報は記載しません。確認が取れた事実のみを記載します。
