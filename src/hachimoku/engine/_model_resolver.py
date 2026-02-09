"""モデルリゾルバー — プレフィックスベースのプロバイダー解決。

モデル文字列のプレフィックスに基づき、pydantic-ai Agent に渡す model 引数を解決する。
- claudecode: ClaudeCodeModel インスタンスを生成して返す
- anthropic: モデル文字列をそのまま返す（pydantic-ai が解決）
"""

from __future__ import annotations

import os

from claudecode_model import ClaudeCodeModel
from pydantic_ai.models import Model

_ANTHROPIC_PREFIX: str = "anthropic:"
_CLAUDECODE_PREFIX: str = "claudecode:"


def resolve_model(model: str) -> str | Model:
    """モデル文字列のプレフィックスに基づきプロバイダーを解決する。

    Args:
        model: プレフィックス付きモデル名文字列
            （例: ``"claudecode:claude-sonnet-4-5"``, ``"anthropic:claude-sonnet-4-5"``）。

    Returns:
        claudecode の場合: ``claudecode:`` プレフィックスを除去し
            ClaudeCodeModel インスタンスを返す。
        anthropic の場合: モデル文字列をそのまま返す。

    Raises:
        ValueError: anthropic プレフィックスで ANTHROPIC_API_KEY が未設定の場合。
        ValueError: 未知のプレフィックスが指定された場合。
    """
    if model.startswith(_CLAUDECODE_PREFIX):
        bare_name = model.removeprefix(_CLAUDECODE_PREFIX)
        if not bare_name:
            raise ValueError(
                f"Model name cannot be empty after prefix in '{model}'. "
                "Specify a model name, e.g. 'claudecode:claude-sonnet-4-5'."
            )
        return ClaudeCodeModel(model_name=bare_name)

    if model.startswith(_ANTHROPIC_PREFIX):
        bare_name = model.removeprefix(_ANTHROPIC_PREFIX)
        if not bare_name:
            raise ValueError(
                f"Model name cannot be empty after prefix in '{model}'. "
                "Specify a model name, e.g. 'anthropic:claude-sonnet-4-5'."
            )
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required when using "
                "model prefix 'anthropic:'. Set it with: export ANTHROPIC_API_KEY='your-key'"
            )
        return model

    raise ValueError(
        f"Unknown model prefix in '{model}'. "
        "Use 'claudecode:model-name' or 'anthropic:model-name'."
    )
