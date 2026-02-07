"""レビュー実行エンジン。

pydantic-ai ベースのマルチエージェントレビュー実行エンジン。
以下の8段階パイプラインでコードレビューを実行する:

1. 設定解決（resolve_config）
2. エージェント読み込み（load_agents）
3. 無効エージェント除外（enabled=false）
4. レビュー指示構築（ReviewInstructionBuilder）
5. セレクターエージェント実行（SelectorAgent）
6. 実行コンテキスト構築（AgentExecutionContext）
7. エージェント実行（Sequential or Parallel）
8. 結果集約（ReviewReport）
"""

__all__: list[str] = []
