"""モデルリゾルバー — プロバイダーに応じたモデルオブジェクト生成。

provider 設定に基づき、pydantic-ai Agent に渡す model 引数を解決する。
- anthropic: モデル文字列をそのまま返す（pydantic-ai が解決）
- claudecode: ClaudeCodeModel インスタンスを生成して返す
"""

from __future__ import annotations

import os

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
        claudecode の場合: ``anthropic:`` プレフィックスを除去し
            ClaudeCodeModel インスタンスを返す。

    Raises:
        ValueError: anthropic プロバイダーで ANTHROPIC_API_KEY が未設定の場合。
        ValueError: 未知のプロバイダーが指定された場合。
    """
    if provider == Provider.ANTHROPIC:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required when using "
                "provider='anthropic'. Set it with: export ANTHROPIC_API_KEY='your-key'"
            )
        return model

    if provider == Provider.CLAUDECODE:
        bare_name = model.removeprefix(_ANTHROPIC_PREFIX)
        return ClaudeCodeModel(model_name=bare_name)

    raise ValueError(f"Unsupported provider: {provider!r}")
