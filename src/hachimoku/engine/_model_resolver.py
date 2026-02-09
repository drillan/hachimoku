"""モデルリゾルバー — プロバイダーに応じたモデルオブジェクト生成。

provider 設定に基づき、pydantic-ai Agent に渡す model 引数を解決する。
- anthropic: モデル文字列をそのまま返す（pydantic-ai が解決）
- claudecode: ClaudeCodeModel インスタンスを生成して返す
"""

from __future__ import annotations

from claudecode_model import ClaudeCodeModel
from pydantic_ai.models import Model

from hachimoku.models.config import Provider

_ANTHROPIC_PREFIX: str = "anthropic:"


def resolve_model(model: str, provider: Provider) -> str | Model:
    """プロバイダーに応じてモデル文字列を解決する。

    Args:
        model: モデル名文字列（例: "anthropic:claude-sonnet-4-5"）。
        provider: 使用するプロバイダー。

    Returns:
        anthropic の場合: モデル文字列をそのまま返す。
        claudecode の場合: ClaudeCodeModel インスタンスを返す。
    """
    if provider == Provider.ANTHROPIC:
        return model

    # provider == Provider.CLAUDECODE
    bare_name = model.removeprefix(_ANTHROPIC_PREFIX)
    return ClaudeCodeModel(model_name=bare_name)
