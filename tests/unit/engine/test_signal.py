"""SignalHandler のテスト。

T038: install/uninstall_signal_handlers の検証。
FR-RE-005: グレースフルシャットダウン。
"""

from __future__ import annotations

import asyncio
import signal
from unittest.mock import MagicMock

from hachimoku.engine._signal import install_signal_handlers, uninstall_signal_handlers


# =============================================================================
# install_signal_handlers
# =============================================================================


class TestInstallSignalHandlers:
    """install_signal_handlers のテスト。"""

    def test_registers_sigint_handler(self) -> None:
        """SIGINT ハンドラが登録される。"""
        event = asyncio.Event()
        loop = MagicMock(spec=asyncio.AbstractEventLoop)

        install_signal_handlers(event, loop)

        sigint_calls = [
            c
            for c in loop.add_signal_handler.call_args_list
            if c[0][0] == signal.SIGINT
        ]
        assert len(sigint_calls) == 1

    def test_registers_sigterm_handler(self) -> None:
        """SIGTERM ハンドラが登録される。"""
        event = asyncio.Event()
        loop = MagicMock(spec=asyncio.AbstractEventLoop)

        install_signal_handlers(event, loop)

        sigterm_calls = [
            c
            for c in loop.add_signal_handler.call_args_list
            if c[0][0] == signal.SIGTERM
        ]
        assert len(sigterm_calls) == 1

    def test_handler_sets_shutdown_event(self) -> None:
        """ハンドラ呼び出しで shutdown_event がセットされる。"""
        event = asyncio.Event()
        loop = MagicMock(spec=asyncio.AbstractEventLoop)

        install_signal_handlers(event, loop)

        # add_signal_handler に渡されたコールバックを取得して呼び出す
        handler = loop.add_signal_handler.call_args_list[0][0][1]
        assert not event.is_set()
        handler()
        assert event.is_set()

    def test_both_signals_registered(self) -> None:
        """SIGINT と SIGTERM の両方が登録される。"""
        event = asyncio.Event()
        loop = MagicMock(spec=asyncio.AbstractEventLoop)

        install_signal_handlers(event, loop)

        assert loop.add_signal_handler.call_count == 2
        registered_signals = {c[0][0] for c in loop.add_signal_handler.call_args_list}
        assert registered_signals == {signal.SIGINT, signal.SIGTERM}


# =============================================================================
# uninstall_signal_handlers
# =============================================================================


class TestUninstallSignalHandlers:
    """uninstall_signal_handlers のテスト。"""

    def test_removes_sigint_handler(self) -> None:
        """SIGINT ハンドラが解除される。"""
        loop = MagicMock(spec=asyncio.AbstractEventLoop)

        uninstall_signal_handlers(loop)

        sigint_calls = [
            c
            for c in loop.remove_signal_handler.call_args_list
            if c[0][0] == signal.SIGINT
        ]
        assert len(sigint_calls) == 1

    def test_removes_sigterm_handler(self) -> None:
        """SIGTERM ハンドラが解除される。"""
        loop = MagicMock(spec=asyncio.AbstractEventLoop)

        uninstall_signal_handlers(loop)

        sigterm_calls = [
            c
            for c in loop.remove_signal_handler.call_args_list
            if c[0][0] == signal.SIGTERM
        ]
        assert len(sigterm_calls) == 1

    def test_both_signals_removed(self) -> None:
        """SIGINT と SIGTERM の両方が解除される。"""
        loop = MagicMock(spec=asyncio.AbstractEventLoop)

        uninstall_signal_handlers(loop)

        assert loop.remove_signal_handler.call_count == 2
        removed_signals = {c[0][0] for c in loop.remove_signal_handler.call_args_list}
        assert removed_signals == {signal.SIGINT, signal.SIGTERM}
