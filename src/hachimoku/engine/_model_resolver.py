"""モデルリゾルバー — プレフィックスベースのプロバイダー解決。

モデル文字列のプレフィックスに基づき、pydantic-ai Agent に渡す model 引数を解決する。
- claudecode: ClaudeCodeModel インスタンスを生成して返す
- anthropic: モデル文字列をそのまま返す（pydantic-ai が解決）
"""

from __future__ import annotations

import os
from typing import Final

from claudecode_model import ClaudeCodeModel
from pydantic_ai.models import Model

_ANTHROPIC_PREFIX: str = "anthropic:"
_CLAUDECODE_PREFIX: str = "claudecode:"

# Claude CLI ビルトインツールのブロックリスト。
# pydantic-ai 登録ツール（run_git, run_gh, read_file, list_directory）のみを
# 使用させるため、CLI ビルトインツールを無効化する。
# Issue #161: ビルトインツール使用による権限拒否・ターン浪費の防止。
_DISALLOWED_BUILTIN_TOOLS: Final[tuple[str, ...]] = (
    "Bash",
    "Read",
    "Write",
    "Edit",
    "MultiEdit",
    "Glob",
    "Grep",
    "WebSearch",
    "WebFetch",
    "NotebookEdit",
    "TodoRead",
    "TodoWrite",
)


def resolve_model(model: str) -> str | Model:
    """モデル文字列のプレフィックスに基づきプロバイダーを解決する。

    Args:
        model: プレフィックス付きモデル名文字列
            （例: ``"claudecode:claude-opus-4-6"``, ``"anthropic:claude-opus-4-6"``）。

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
                "Specify a model name, e.g. 'claudecode:claude-opus-4-6'."
            )
        return ClaudeCodeModel(
            model_name=bare_name,
            disallowed_tools=list(_DISALLOWED_BUILTIN_TOOLS),
        )

    if model.startswith(_ANTHROPIC_PREFIX):
        bare_name = model.removeprefix(_ANTHROPIC_PREFIX)
        if not bare_name:
            raise ValueError(
                f"Model name cannot be empty after prefix in '{model}'. "
                "Specify a model name, e.g. 'anthropic:claude-opus-4-6'."
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
