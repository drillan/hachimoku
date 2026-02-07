"""Contract: ReviewEngine — レビュー実行パイプライン.

FR-RE-002: エージェント実行パイプライン全体を統括する。
設定解決 → エージェント読み込み → 選択 → 実行 → 結果集約。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Literal

from hachimoku.agents.models import LoadResult
from hachimoku.models._base import HachimokuBaseModel
from hachimoku.models.report import ReviewReport

if TYPE_CHECKING:
    from hachimoku.engine._target import DiffTarget, FileTarget, PRTarget

# --- 既存モデル変更の追跡 (FR-RE-014, research.md R-009) ---
# ReviewReport に load_errors: tuple[LoadError, ...] = () フィールドを追加する。
# 変更対象: src/hachimoku/models/report.py
# 型: tuple[LoadError, ...] (003-agent-definition の LoadError を再利用)
# デフォルト: () (エラーなし)
# 目的: エージェント読み込みエラーをレポート内に記録する


class EngineResult(HachimokuBaseModel):
    """ReviewEngine の実行結果.

    Attributes:
        report: 生成されたレビューレポート。
        exit_code: 終了コード（0=成功, 1=Critical, 2=Important, 3=実行エラー）。
    """

    report: ReviewReport
    exit_code: Literal[0, 1, 2, 3]


async def run_review(
    target: DiffTarget | PRTarget | FileTarget,
    config_overrides: dict[str, object] | None = None,
    custom_agents_dir: Path | None = None,
) -> EngineResult:
    """レビュー実行パイプラインを実行する.

    パイプライン:
        1. 設定解決（resolve_config）
        2. エージェント読み込み（load_agents）
        3. 無効エージェント除外（enabled=false）
        4. レビュー指示構築（ReviewInstructionBuilder）
        5. セレクターエージェント実行（SelectorAgent）
        6. 実行コンテキスト構築（AgentExecutionContext）
        7. エージェント実行（Sequential or Parallel）
        8. 結果集約（ReviewReport）

    Args:
        target: レビュー対象（DiffTarget / PRTarget / FileTarget）。
        config_overrides: CLI からの設定オーバーライド。
        custom_agents_dir: カスタムエージェント定義ディレクトリ。

    Returns:
        EngineResult: レビューレポートと終了コード。
        セレクターエージェント失敗時も EngineResult を返す（exit_code=3、
        空の results リストとエラー情報）。
        全エージェント失敗時も EngineResult を返す（exit_code=3）。

    Note:
        本関数は正常系・エラー系ともに EngineResult を返す。
        例外を送出するのは入力バリデーションエラー（exit_code=4 相当）のみ:
        - diff モードで Git リポジトリ外から実行
        - diff モードで存在しない base_branch を指定
    """
    ...


def _filter_disabled_agents(
    load_result: LoadResult,
    disabled_names: frozenset[str],
) -> tuple[LoadResult, list[str]]:
    """設定で無効化されたエージェントを除外する.

    Args:
        load_result: エージェント読み込み結果。
        disabled_names: enabled=false のエージェント名集合。

    Returns:
        フィルタ済みの LoadResult と除外されたエージェント名リスト。
    """
    ...
