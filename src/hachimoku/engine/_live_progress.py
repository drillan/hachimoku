"""RichProgressReporter — TTY 環境向け Rich Live テーブル進捗表示。

FR-CLI-015: エージェント実行中にリアルタイムのステータス表を stderr に表示する。
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Final

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

from hachimoku.models.agent_result import (
    AgentError,
    AgentResult,
    AgentSuccess,
    AgentTimeout,
    AgentTruncated,
)

PHASE_ORDER: Final[dict[str, int]] = {"early": 0, "main": 1, "final": 2}
"""フェーズのソート順序。"""


@dataclass
class AgentRow:
    """テーブル行の状態。"""

    phase: str
    status: str = "pending"


class RichProgressReporter:
    """TTY 環境向け Rich Live テーブル進捗レポーター。

    テーブル列: Agent | Phase | Status
    行順序: phase 順（early → main → final）、同 phase 内は名前辞書順。
    """

    def __init__(self, console: Console | None = None) -> None:
        self._console: Console = console or Console(file=sys.stderr)
        self._live: Live | None = None
        self.agents: dict[str, AgentRow] = {}

    def on_agent_pending(self, agent_name: str, phase: str) -> None:
        """エージェントを pending 状態として登録する。"""
        self.agents[agent_name] = AgentRow(phase=phase)
        self._refresh()

    def on_agent_start(self, agent_name: str) -> None:
        """エージェント実行開始を通知し、ステータスを running に更新する。"""
        if agent_name in self.agents:
            self.agents[agent_name].status = "running"
            self._refresh()

    def on_agent_complete(self, agent_name: str, result: AgentResult) -> None:
        """エージェント実行完了を通知し、ステータスを結果に応じて更新する。"""
        if agent_name in self.agents:
            self.agents[agent_name].status = _format_completion_status(result)
            self._refresh()

    def start(self) -> None:
        """Rich Live 表示を開始する。"""
        live = Live(
            self.build_table(),
            console=self._console,
            refresh_per_second=4,
        )
        live.__enter__()
        self._live = live

    def stop(self) -> None:
        """Rich Live 表示を停止する。"""
        if self._live is not None:
            try:
                self._live.__exit__(None, None, None)
            except Exception:
                pass
            self._live = None

    def build_table(self) -> Table:
        """現在の状態からテーブルを構築する。"""
        table = Table(title="Review Progress")
        table.add_column("Agent")
        table.add_column("Phase")
        table.add_column("Status")

        sorted_agents = sorted(
            self.agents.items(),
            key=lambda item: (PHASE_ORDER.get(item[1].phase, 99), item[0]),
        )

        for name, row in sorted_agents:
            table.add_row(name, row.phase, _render_status(row.status))

        return table

    def _refresh(self) -> None:
        """Live 表示を更新する（Live がアクティブな場合のみ）。"""
        if self._live is not None:
            self._live.update(self.build_table())


def _format_completion_status(result: AgentResult) -> str:
    """AgentResult から完了ステータス文字列を生成する。"""
    if isinstance(result, AgentSuccess):
        return f"✓ {len(result.issues)} issues"
    if isinstance(result, AgentTruncated):
        return f"⚠ {len(result.issues)} issues"
    if isinstance(result, AgentError):
        return "✗ error"
    if isinstance(result, AgentTimeout):
        return "⏱ timeout"
    raise TypeError(f"Unknown result type: {type(result)}")


def _render_status(status: str) -> Text | Spinner:
    """ステータス文字列を Rich レンダラブルに変換する。"""
    if status == "pending":
        return Text("⏳ pending", style="dim")
    if status == "running":
        return Spinner("dots", text="running", style="cyan")
    if status.startswith("✓"):
        return Text(status, style="green")
    if status.startswith("⚠"):
        return Text(status, style="yellow")
    if status.startswith("✗"):
        return Text(status, style="red")
    if status.startswith("⏱"):
        return Text(status, style="red")
    return Text(status)
