"""Contract: SignalHandler — SIGINT/SIGTERM ハンドリング.

FR-RE-005: グレースフルシャットダウン。
SC-RE-005: SIGINT 受信後3秒以内に全プロセス終了。
"""

from __future__ import annotations

import asyncio


def install_signal_handlers(
    shutdown_event: asyncio.Event,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """SIGINT/SIGTERM シグナルハンドラを登録する.

    シグナル受信時に shutdown_event をセットし、
    Executors にキャンセルを通知する。

    Args:
        shutdown_event: 停止を通知するイベント。
        loop: 現在の asyncio イベントループ。
    """
    ...


def uninstall_signal_handlers(
    loop: asyncio.AbstractEventLoop,
) -> None:
    """シグナルハンドラを解除する.

    エンジン実行完了後にクリーンアップする。

    Args:
        loop: 現在の asyncio イベントループ。
    """
    ...
