"""pydantic-ai ツール実装。

エージェントが使用するツール関数を提供する。
ToolCategory（git_read, gh_read, file_read）ごとにモジュールを分割し、
_catalog.py 経由で解決される。web_fetch は pydantic-ai の WebFetchTool
ビルトインを使用するため、本パッケージにはツール関数を持たない。
本パッケージはプライベートであり直接インポートしない。
"""

__all__: list[str] = []
