"""設定管理モジュール。"""

from hachimoku.config._locator import find_project_root
from hachimoku.config._resolver import resolve_config

__all__ = [
    "find_project_root",
    "resolve_config",
]
