"""レビュー実行エンジン。

pydantic-ai ベースのマルチエージェントレビュー実行エンジン。
以下のパイプラインでコードレビューを実行する:

1. 設定解決（resolve_config）
2. エージェント読み込み（load_agents）
3. 無効エージェント除外（enabled=false）
3.5. コンテンツ事前解決（resolve_content）
3.7. セレクター向けコンテキスト事前取得（Issue #187）
4. レビュー指示構築（ReviewInstructionBuilder）
5. セレクターエージェント実行（SelectorAgent）
6. 実行コンテキスト構築（AgentExecutionContext）
7. エージェント実行（Sequential or Parallel）
8. 結果集約（ReviewReport）
"""

from hachimoku.engine._engine import EngineResult, run_review
from hachimoku.engine._prefetch import PrefetchedContext, PrefetchError
from hachimoku.engine._resolver import ContentResolveError
from hachimoku.engine._selector import ReferencedContent, SelectorError, SelectorOutput

__all__ = [
    "ContentResolveError",
    "EngineResult",
    "PrefetchedContext",
    "PrefetchError",
    "ReferencedContent",
    "SelectorError",
    "SelectorOutput",
    "run_review",
]
