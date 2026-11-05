# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn the display off when logind announces a system shutdown.

At poweroff the compositor exits early, and GTK then ends the HTML worker
before it can power the display off. logind announces the shutdown first
(``PrepareForShutdown(true)``) and, for holders of a *delay* inhibitor,
waits up to ``InhibitDelayMaxSec`` (5 s by default) before going on. The
monitor takes such an inhibitor and runs its normal cleanup on the signal,
while the worker and the compositor are still alive.
"""

from __future__ import annotations

import os
import threading
from typing import Callable

from library.log import logger

LOGIND_BUS_NAME = "org.freedesktop.login1"
LOGIND_PATH = "/org/freedesktop/login1"
LOGIND_MANAGER = "org.freedesktop.login1.Manager"


class ShutdownInhibitor:
    """Hold a logind delay lock and call ``on_shutdown`` before poweroff."""

    def __init__(self, on_shutdown: Callable[[], None], *, who: str = "Turing Smart Screen") -> None:
        self._on_shutdown = on_shutdown
        self._who = who
        self._fd: int | None = None
        self._fd_lock = threading.Lock()
        self._fired = threading.Event()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop = None

    def start(self, timeout: float = 3.0) -> bool:
        """Start listening; False when logind is not reachable."""
        self._thread = threading.Thread(target=self._run, name="shutdown-inhibitor", daemon=True)
        self._thread.start()
        self._ready.wait(timeout)
        return self._fd is not None

    def _run(self) -> None:
        try:
            from gi.repository import Gio, GLib
        except Exception as exc:
            logger.debug("Shutdown inhibitor unavailable: %s", exc)
            self._ready.set()
            return

        context = GLib.MainContext()
        context.push_thread_default()
        try:
            bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
            bus.signal_subscribe(
                LOGIND_BUS_NAME,
                LOGIND_MANAGER,
                "PrepareForShutdown",
                LOGIND_PATH,
                None,
                Gio.DBusSignalFlags.NONE,
                self._on_signal,
            )
            self._take_lock(bus, Gio, GLib)
        except Exception as exc:
            logger.warning("Could not register for shutdown notifications: %s", exc)
            self._ready.set()
            context.pop_thread_default()
            return
        self._ready.set()
        self._loop = GLib.MainLoop.new(context, False)
        try:
            self._loop.run()
        finally:
            context.pop_thread_default()

    def _take_lock(self, bus, Gio, GLib) -> None:
        reply, fds = bus.call_with_unix_fd_list_sync(
            LOGIND_BUS_NAME,
            LOGIND_PATH,
            LOGIND_MANAGER,
            "Inhibit",
            GLib.Variant("(ssss)", ("shutdown", self._who, "Turn the display off before shutdown", "delay")),
            GLib.VariantType.new("(h)"),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
            None,
        )
        index = reply.unpack()[0]
        with self._fd_lock:
            self._fd = fds.get(index)
        logger.debug("Holding a logind shutdown delay lock")

    def _on_signal(self, _connection, _sender, _path, _interface, _signal, parameters) -> None:
        try:
            starting = bool(parameters.unpack()[0])
        except Exception:
            return
        if not starting or self._fired.is_set():
            return
        self._fired.set()
        logger.info("System shutdown announced; turning the display off")
        try:
            self._on_shutdown()
        except Exception as exc:
            logger.warning("Display shutdown before poweroff failed: %s", exc)
        finally:
            self.release()

    def release(self) -> None:
        """Let logind continue; safe to call more than once."""
        with self._fd_lock:
            fd, self._fd = self._fd, None
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

    def stop(self) -> None:
        self.release()
        loop = self._loop
        if loop is not None:
            loop.quit()
