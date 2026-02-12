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

# レビューエージェントに許可する CLI ビルトインツールの許可リスト。
# 読み取り専用ツール（Read, Grep, Glob）のみ許可する。
# deny-list 方式では新規ツール（Task 等）の追加漏れによる
# バイパスリスクがあるため、allow-list 方式を採用する。
# pydantic-ai ツール（run_git, run_gh）は subprocess.run() を直接使用するため
# この制限の影響を受けない。
# Issue #161: ビルトインツール使用による権限拒否・ターン浪費の防止。
# Issue #184: deny-list から allow-list への切り替え。
_ALLOWED_BUILTIN_TOOLS: Final[tuple[str, ...]] = ("Read", "Grep", "Glob")


def resolve_model(model: str) -> str | Model:
    """モデル文字列のプレフィックスに基づきプロバイダーを解決する。

    Args:
        model: プレフィックス付きモデル名文字列
            （例: ``"claudecode:claude-opus-4-6"``, ``"anthropic:claude-opus-4-6"``）。

    Returns:
        claudecode の場合: ``claudecode:`` プレフィックスを除去し
            ClaudeCodeModel インスタンスを返す。読み取り専用の
            CLI ビルトインツール（Read, Grep, Glob）のみ ``allowed_tools`` で許可される。
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
            allowed_tools=list(_ALLOWED_BUILTIN_TOOLS),
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
