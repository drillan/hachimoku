"""SelectorAgent — エージェント選択処理。

FR-RE-002 Step 5: セレクターエージェントの構築・実行・結果解釈。
FR-RE-010: 空リスト返却時の正常終了。
R-006: SelectorOutput モデル定義。
Issue #187: prefetched_context の伝播。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from anyio import fail_after
from claudecode_model import ClaudeCodeModel, ClaudeCodeModelSettings
from claudecode_model.exceptions import CLIExecutionError
from pydantic import Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.usage import UsageLimits

from hachimoku.agents.models import AgentDefinition, SelectorDefinition
from hachimoku.engine._catalog import resolve_tools
from hachimoku.engine._context import _resolve_with_agent_def
from hachimoku.engine._instruction import build_selector_instruction
from hachimoku.engine._model_resolver import resolve_model
from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.config import SelectorConfig

if TYPE_CHECKING:
    from hachimoku.engine._prefetch import PrefetchedContext

logger = logging.getLogger(__name__)


class ReferencedContent(HachimokuBaseModel):
    """diff 内で参照されている外部リソースの取得結果。

    Issue #159: セレクターが diff 内の参照（Issue 番号、ファイルパス等）を
    検出し、取得した内容をレビューエージェントに伝播するためのモデル。

    Attributes:
        reference_type: 参照の種類（"issue", "file", "spec", "other"）。
        reference_id: 参照識別子（例: "#152", "src/foo.py"）。
        content: 取得した参照先の内容テキスト。
    """

    reference_type: str = Field(min_length=1)
    reference_id: str = Field(min_length=1)
    content: str = Field(min_length=1)


class SelectorOutput(HachimokuBaseModel):
    """セレクターエージェントの構造化出力。

    Attributes:
        selected_agents: 実行すべきエージェント名リスト。
        reasoning: 選択理由（デバッグ・監査用）。
        change_intent: 変更の意図・目的の要約（レビューエージェントへの伝播用）。
        affected_files: diff 外で影響を受ける可能性のあるファイルパス。
        relevant_conventions: 当該変更に関連するプロジェクト規約。
        issue_context: Issue 関連情報の要約。
        referenced_content: diff 内で参照されている外部リソースの取得結果。
    """

    selected_agents: list[str]
    reasoning: str
    change_intent: str = ""
    affected_files: list[str] = Field(default_factory=list)
    relevant_conventions: list[str] = Field(default_factory=list)
    issue_context: str = ""
    referenced_content: list[ReferencedContent] = Field(default_factory=list)


@dataclass
class SelectorDeps:
    """セレクターエージェントの依存性コンテナ。

    Issue #195: pydantic-ai の Dependencies 機構を利用し、
    PrefetchedContext を依存性として注入する。

    Attributes:
        prefetched: 事前取得されたコンテキスト（Issue #187）。
    """

    prefetched: PrefetchedContext | None


def _prefetch_guardrail(ctx: RunContext[SelectorDeps]) -> str:
    """事前取得済みデータがある場合に再取得禁止のガードレールを注入する。

    Issue #195: PrefetchedContext の各フィールドが非空の場合に、
    対応するデータの再取得を禁止する指示を動的に生成する。
    pydantic-ai の ``instructions`` パラメータとして Agent に渡される。

    Args:
        ctx: pydantic-ai の RunContext。deps に SelectorDeps を保持。

    Returns:
        ガードレール指示テキスト。事前取得データがない場合は空文字列。
    """
    if ctx.deps.prefetched is None:
        return ""

    guardrails: list[str] = []

    if ctx.deps.prefetched.issue_context:
        guardrails.append(
            "IMPORTANT: Issue context has already been pre-fetched and is included "
            "in the user message under '## Pre-fetched Context > ### Issue Context'. "
            "Do NOT use the run_gh tool to re-fetch issue details. "
            "Use the pre-fetched data directly."
        )

    if ctx.deps.prefetched.pr_metadata:
        guardrails.append(
            "IMPORTANT: PR metadata has already been pre-fetched and is included "
            "in the user message under '## Pre-fetched Context > ### PR Metadata'. "
            "Do NOT use the run_gh tool to re-fetch PR details. "
            "Use the pre-fetched data directly."
        )

    if ctx.deps.prefetched.project_conventions:
        guardrails.append(
            "IMPORTANT: Project conventions have already been pre-fetched and are "
            "included in the user message under "
            "'## Pre-fetched Context > ### Project Conventions'. "
            "Do NOT use file reading tools to re-read these convention files. "
            "Use the pre-fetched data directly."
        )

    return "\n\n".join(guardrails)


class SelectorError(Exception):
    """セレクターエージェントの実行失敗。

    タイムアウト・実行エラー・不正な出力など、セレクター実行中の
    あらゆる失敗を表す。

    Attributes:
        exit_code: CLI プロセス終了コード（CLIExecutionError 由来、オプション）。
        error_type: 構造化エラー種別（CLIExecutionError 由来、オプション）。
        stderr: 標準エラー出力（CLIExecutionError 由来、オプション）。
        recoverable: リトライにより回復可能か（CLIExecutionError 由来、オプション）。
    """

    def __init__(
        self,
        message: str,
        *,
        exit_code: int | None = None,
        error_type: str | None = None,
        stderr: str | None = None,
        recoverable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.exit_code = exit_code
        self.error_type = error_type
        self.stderr = stderr
        self.recoverable = recoverable


async def run_selector(
    target: DiffTarget | PRTarget | FileTarget,
    available_agents: Sequence[AgentDefinition],
    selector_definition: SelectorDefinition,
    selector_config: SelectorConfig,
    global_model: str,
    global_timeout: int,
    global_max_turns: int,
    resolved_content: str,
    prefetched_context: PrefetchedContext | None = None,
) -> SelectorOutput:
    """セレクターエージェントを実行し、実行すべきエージェントを選択する。

    実行フロー:
        1. モデル解決（3層: config > definition > global）
        2. SelectorConfig からタイムアウト・ターン数を解決
        3. SelectorDefinition.allowed_tools からツールを解決
        4. build_selector_instruction() でユーザーメッセージを構築
        5. resolve_model() でモデルオブジェクトを生成
        6. pydantic-ai Agent(system_prompt=definition.system_prompt) を構築
        7. anyio.fail_after() + UsageLimits でエージェントを実行
        8. SelectorOutput を返す

    Args:
        target: レビュー対象。
        available_agents: 利用可能なエージェント定義リスト。
        selector_definition: セレクター定義（system_prompt, allowed_tools, model）。
        selector_config: セレクター個別設定（model, timeout, max_turns オーバーライド）。
        global_model: グローバルモデル名。
        global_timeout: グローバルタイムアウト秒数。
        global_max_turns: グローバル最大ターン数。
        resolved_content: 事前解決されたコンテンツ（diff テキスト、ファイル内容等）。
        prefetched_context: 事前取得されたコンテキスト（Issue #187）。

    Returns:
        SelectorOutput: 選択されたエージェント名リストと選択理由。

    Raises:
        SelectorError: セレクターエージェントの実行に失敗した場合。
    """
    # 3層モデル解決: config > definition > global
    model = _resolve_with_agent_def(
        selector_config.model, selector_definition.model, global_model
    )
    timeout = _resolve_with_agent_def(selector_config.timeout, None, global_timeout)
    max_turns = _resolve_with_agent_def(
        selector_config.max_turns, None, global_max_turns
    )

    try:
        resolved_tools = resolve_tools(selector_definition.allowed_tools)
        user_message = build_selector_instruction(
            target,
            available_agents,
            resolved_content,
            prefetched_context=prefetched_context,
        )

        resolved = resolve_model(
            model,
            allowed_builtin_tools=(),
            extra_builtin_tools=resolved_tools.claudecode_builtin_names,
        )
        agent = Agent(
            model=resolved,
            output_type=SelectorOutput,
            # ツール自体は deps を参照しないが、Agent[SelectorDeps] が
            # Tool[SelectorDeps] を要求するため型不整合が発生する。
            # TODO(#195): ツールが ctx.deps を使い始めた場合は resolve_tools を
            # TypeVar でジェネリック化して型安全性を回復すること。
            tools=list(resolved_tools.tools),  # type: ignore[arg-type]
            builtin_tools=list(resolved_tools.builtin_tools),
            system_prompt=selector_definition.system_prompt,
            deps_type=SelectorDeps,
            instructions=_prefetch_guardrail,
        )
        if isinstance(resolved, ClaudeCodeModel):
            # mypy が FunctionToolset.tools の dict[str, Tool[Any]] を
            # AgentToolset.tools の dict[str, PydanticAITool] と互換とみなせないため。
            # set_agent_toolsets の docstring が agent._function_toolset を使用例として記載。
            resolved.set_agent_toolsets(agent._function_toolset)  # type: ignore[arg-type]

        with fail_after(timeout):
            result = await agent.run(
                user_message,
                deps=SelectorDeps(prefetched=prefetched_context),
                usage_limits=UsageLimits(request_limit=max_turns),
                model_settings=ClaudeCodeModelSettings(
                    max_turns=max_turns,
                    timeout=timeout,
                ),
            )

        return result.output

    except Exception as exc:
        logger.warning(
            "Selector agent failed with %s: %s",
            type(exc).__name__,
            exc,
            exc_info=True,
        )

        exit_code: int | None = None
        error_type: str | None = None
        stderr: str | None = None
        recoverable: bool | None = None

        if isinstance(exc, CLIExecutionError):
            exit_code = exc.exit_code
            error_type = exc.error_type
            stderr = exc.stderr
            recoverable = exc.recoverable

        raise SelectorError(
            f"Selector agent failed: {exc}",
            exit_code=exit_code,
            error_type=error_type,
            stderr=stderr,
            recoverable=recoverable,
        ) from exc
