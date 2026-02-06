# Documentation Guidelines

このファイルは、hachimoku プロジェクトのドキュメンテーションガイドラインを提供します。

## Documentation System

Sphinx + MyST-Parser (Markdown) + Mermaid でドキュメントをビルドします。

### Building Docs

```bash
# 推奨
make -C docs html
# Output: docs/_build/index.html

# クリーンビルド
make -C docs clean html
```

## Writing Guidelines

### Markup Syntax

すべてのドキュメントは [MyST](https://mystmd.org/guide) 形式（Markdown for Sphinx）で記述します。

使用可能な拡張機能:
- `colon_fence` - `:::` によるディレクティブ構文
- `substitution` - 変数の置換
- `tasklist` - `[ ]` と `[x]` によるタスクリスト
- `attrs_inline` - インライン属性
- `deflist` - 定義リスト

よく使うパターン:

````markdown
# Table of contents
```{contents}
:depth: 2
:local:
```

# Admonitions
```{note}
This is a note.
```

# Code blocks with line numbers
```{code-block} python
:linenos:
def example():
    pass
```
````

### Tone and Style

プロフェッショナルで簡潔な技術文書を心がけてください。

**Avoid**:
- 誇張表現: "革命的"、"画期的"、"amazing"
- マーケティング用語: "best-in-class"、"cutting-edge"、"next-generation"
- 絶対的な表現: "完全サポート"、"必ず"、"絶対"
- 感嘆符: "！"
- 内部用語: "Phase 1"、"Milestone 3" (代わりに "v0.2+" を使用)
- 内部参照: "Article 3"、"Article 8" (代わりに概念を直接参照)
- 過度な太字使用: 文中で`**`を多用すると可読性が低下する

**Prefer**:
- 事実に基づく記述: "supports"、"provides"、"enables"
- 限定的な表現: "多くの場合"、"通常"、"一般的に"
- バージョン表記: "v0.2+"、"since v0.3"、"as of v0.2"
- 明確で簡潔な技術的記述

### Emphasis

太字（`**bold**`）は本当に必要な場合のみ使用してください。過度な修飾はドキュメントの可読性を損ない、プロフェッショナルな印象を損ないます。

使用が許可される場合:
- セクション見出し（自動）
- 重要な警告や要件
- 初出の重要用語

通常の説明文では太字を使用せず、平文で記述してください。

```markdown
# ❌ 太字が多すぎる
**このライブラリ**は**すべての機能**に**優れたサポート**を提供します。

# ✅ 適切な太字使用
このライブラリはカスタムツールをサポートします。**注意**: APIキーが必要です。
```

### Code Block Highlighting

構文ハイライターエラーを避けるため、以下に注意してください。

#### TOML
```toml
# ❌ TOMLでnullを使用しない
key = null

# ✅ 代わりにコメントを使用
# key = (not set)
```

#### JSON

JSON はコメントをサポートしないため、コメント付きの例は `jsonc` を使用する:

```jsonc
// ❌ 省略記号を使用しない
{
  "items": [...]
}

// ✅ 完全な構造を示す
{
  "items": ["item1", "item2"]
}
```

#### Unknown lexers
````text
# ❌ サポートされていないlexerを使用しない
```unknownlang
code here
```

# ✅ 'text'または'bash'を使用
```text
code here
```
````

#### Special characters
```python
# ❌ コードブロック内で矢印記号を避ける
result → value  # ハイライトエラーの原因となる可能性

# ✅ 標準的なASCIIを使用
result = value
```

#### Nested code blocks

コードブロック内にさらにコードブロックを記載する場合は、外側のバッククォートの数を増やします:
- 通常のコードブロック: 3つのバッククォート（```）
- 1段階ネスト: 4つのバッククォート（````）
- 2段階ネスト: 5つのバッククォート（`````）

`````markdown
# ❌ 正しくレンダリングされない
```markdown
# MyST構文の例
```{note}
This is a note.
```
```

# ✅ 正しいネスト構文
````markdown
# MyST構文の例
```{note}
This is a note.
```
````
`````

参考:
- [MyST Parser - Roles and Directives](https://myst-parser.readthedocs.io/en/latest/syntax/roles-and-directives.html)

## Structure Guidelines

### File Organization

```
docs/
├── index.md              # Main landing page
├── conf.py               # Sphinx 設定
├── Makefile              # ビルドヘルパー
├── _static/              # 静的ファイル
└── _templates/           # カスタムテンプレート
```

### Document Sections

機能ドキュメントの標準セクション:

1. Overview - 簡潔な紹介（2-3文）
2. Quick Start - 最小限の動作例
3. Features - 詳細な機能リスト
4. Limitations - 既知の制約
5. Troubleshooting - よくある問題と解決策
6. FAQ - よくある質問
7. Examples - サンプルコードへのリンク

### Cross-References

```markdown
# 別のドキュメントへのリンク
[Features](features.md)

# セクションへのリンク
[Installation](#installation)

# カスタムテキストでリンク
See the [features guide](features.md) for details.
```

#### MyST ターゲット参照（別ファイルへのアンカーリンク）

MyST で別ファイルの特定セクションにリンクする場合、明示的なターゲットを使用する:

```markdown
# ❌ file.md#anchor 形式は Sphinx で警告が出る
[Guide](other-page.md#section-name)

# ✅ ターゲットを定義してターゲット名のみで参照
# 参照先ファイルでターゲットを定義:
(section-target)=
# セクション見出し

# 参照元ファイルでターゲット名のみで参照:
[Guide](section-target)
```

#### docs 外ファイルへのリンク

Sphinx は `docs/` ディレクトリをルートとしてビルドするため、`docs/` 外のファイルへの相対パスは解決できない。

```markdown
# ❌ docs 外への相対パスは解決されない
[spec](../specs/002-domain-models/spec.md)

# ✅ GitHub リポジトリへの絶対 URL を使用
[spec](https://github.com/drillan/hachimoku/tree/main/specs/002-domain-models/spec.md)
```

対象ディレクトリ:
- `specs/` - 仕様書
- `src/` - Python ソースコード
- その他 `docs/` 外のファイル

## Version Documentation

### Feature Status Labels

機能の成熟度を示すラベル:

- **v0.2+** - バージョン0.2以降で利用可能
- **Experimental** - 動作するが変更される可能性がある
- **Deprecated** - 将来削除される予定
- **Planned** - まだ実装されていない

```markdown
## Custom Tools (v0.2+)

### Basic Tools
Dependency-free tools are supported (v0.2+).

### Advanced Features (Experimental)
Advanced dependency injection is supported as an experimental feature.
```

### Version-Specific Notes

バージョン固有の動作を記載する場合:

```markdown
- v0.1: Basic support only
- v0.2+: Enhanced features
- v0.2+ (Experimental): Experimental features
```

## Common Warnings to Avoid

ドキュメントビルド時の一般的な警告を避けるため:

1. Missing cross-references
   ```markdown
   # ❌ 壊れたリンク
   [Non-existent file](missing.md)

   # ✅ 有効なリンク
   [Existing file](user-guide.md)
   ```

2. Empty sections before transitions
   ```markdown
   # ❌ 空のセクション
   ### Section Title

   ---

   # ✅ コンテンツを追加
   ### Section Title

   Content here.

   ---
   ```

3. Missing toctree entries
   - すべてのドキュメントファイルを`index.md`のtoctreeに含める
   - ビルド出力で "document isn't included in any toctree" をチェック

4. Heading level skips
   ```markdown
   # ❌ 見出しレベルをスキップ
   # Heading 1
   ### Heading 3  # Skipped level 2

   # ✅ 連続したレベル
   # Heading 1
   ## Heading 2
   ### Heading 3
   ```

## Build Verification

### Before Committing

コミット前にドキュメントをビルドしてください:

```bash
make -C docs html
```

確認事項:
- Errors (修正必須)
- Warnings (修正推奨)
- Success message

### Clean Build

キャッシュなしでクリーンビルド:

```bash
make -C docs clean html
```

## Configuration

Sphinx の設定は `docs/conf.py` に記述されています。

```python
project = "hachimoku"
language = "ja"

extensions = [
    "myst_parser",
    "sphinxcontrib.mermaid",
]

myst_enable_extensions = [
    "colon_fence",
    "substitution",
    "tasklist",
    "attrs_inline",
    "deflist",
]

html_theme = "shibuya"
```

## References

- [MyST Parser Documentation](https://mystmd.org/guide)
- [Sphinx Documentation](https://www.sphinx-doc.org/)
- [Mermaid Diagram Syntax](https://mermaid.js.org/)
- [Shibuya Theme](https://shibuya.lepture.com/)
