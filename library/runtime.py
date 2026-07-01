#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime coordination for processes that access the smart-screen device.

The display exposes a single USB/serial channel. This module provides a
process-wide advisory lock and a small monitor controller so the GTK app,
main monitor, video manager, and power helper cannot use the device at the
same time.
"""

from __future__ import annotations

import errno
import json
import os
import signal
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional, Sequence

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


APP_RUNTIME_DIR = "turing-smart-screen"
LOCK_FILENAME = "device.lock"


@dataclass(frozen=True)
class LockOwner:
    pid: Optional[int] = None
    role: str = "unknown"
    root: str = ""
    command: tuple[str, ...] = ()
    started_at: Optional[float] = None

    @classmethod
    def from_mapping(cls, value: object) -> "LockOwner":
        if not isinstance(value, dict):
            return cls()

        raw_pid = value.get("pid")
        try:
            pid = int(raw_pid) if raw_pid is not None else None
        except (TypeError, ValueError):
            pid = None

        raw_command = value.get("command")
        if isinstance(raw_command, list):
            command = tuple(str(part) for part in raw_command)
        else:
            command = ()

        raw_started_at = value.get("started_at")
        try:
            started_at = (
                float(raw_started_at) if raw_started_at is not None else None
            )
        except (TypeError, ValueError):
            started_at = None

        return cls(
            pid=pid,
            role=str(value.get("role") or "unknown"),
            root=str(value.get("root") or ""),
            command=command,
            started_at=started_at,
        )

    def describe(self) -> str:
        label = self.role.replace("-", " ") or "another process"
        return f"{label} (PID {self.pid})" if self.pid else label


@dataclass(frozen=True)
class RuntimeState:
    busy: bool
    owner: LockOwner = LockOwner()

    @property
    def monitor_running(self) -> bool:
        return self.busy and self.owner.role == "monitor"


@dataclass(frozen=True)
class TerminationResult:
    stopped: bool
    forced: bool = False
    message: str = ""


class DeviceBusyError(RuntimeError):
    def __init__(self, owner: LockOwner):
        self.owner = owner
        super().__init__(
            "The display is already in use by " + owner.describe() + "."
        )


def runtime_directory() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR", "").strip()
    if base:
        candidate = Path(base)
    else:
        try:
            uid = os.getuid()
        except AttributeError:  # pragma: no cover - Windows
            uid = os.getpid()
        candidate = Path(tempfile.gettempdir()) / f"{APP_RUNTIME_DIR}-{uid}"

    directory = candidate / APP_RUNTIME_DIR if base else candidate
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        directory.chmod(0o700)
    except OSError:
        pass
    return directory


def default_lock_path() -> Path:
    override = os.environ.get("TURING_DEVICE_LOCK", "").strip()
    return Path(override).expanduser() if override else runtime_directory() / LOCK_FILENAME


def _metadata_for(role: str, root: Path | str | None) -> dict[str, object]:
    return {
        "pid": os.getpid(),
        "role": role,
        "root": str(Path(root).resolve()) if root else "",
        "command": list(os.sys.argv),
        "started_at": time.time(),
    }


def _read_owner_from_handle(handle) -> LockOwner:
    try:
        handle.seek(0)
        raw = handle.read()
    except (OSError, ValueError):
        return LockOwner()

    if not raw.strip():
        return LockOwner()

    try:
        return LockOwner.from_mapping(json.loads(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        return LockOwner()


def _try_lock(handle) -> bool:
    if fcntl is None:  # pragma: no cover - project runtime is Linux-first
        raise RuntimeError("Device locking currently requires a POSIX system")

    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError as exc:
        if exc.errno in {errno.EACCES, errno.EAGAIN}:
            return False
        raise


def _unlock(handle) -> None:
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class DeviceLock:
    """Exclusive advisory lease for the USB/serial display channel."""

    def __init__(
        self,
        role: str,
        root: Path | str | None = None,
        lock_path: Path | str | None = None,
    ):
        self.role = role
        self.root = Path(root).resolve() if root else None
        self.path = Path(lock_path) if lock_path else default_lock_path()
        self._handle = None

    @property
    def acquired(self) -> bool:
        return self._handle is not None

    def acquire(self) -> "DeviceLock":
        if self._handle is not None:
            return self

        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        if not _try_lock(handle):
            owner = _read_owner_from_handle(handle)
            handle.close()
            raise DeviceBusyError(owner)

        metadata = _metadata_for(self.role, self.root)
        handle.seek(0)
        handle.truncate()
        json.dump(metadata, handle, sort_keys=True)
        handle.write("\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass

        self._handle = handle
        return self

    def release(self) -> None:
        handle = self._handle
        if handle is None:
            return

        self._handle = None
        # Keep the last owner metadata in the file. Readers only trust it while
        # the OS lock is held, and retaining it avoids a brief "busy but unknown"
        # state while the lease is being released.
        try:
            _unlock(handle)
        finally:
            handle.close()

    def __enter__(self) -> "DeviceLock":
        return self.acquire()

    def __exit__(self, _exc_type, _exc, _traceback) -> None:
        self.release()


def get_runtime_state(lock_path: Path | str | None = None) -> RuntimeState:
    path = Path(lock_path) if lock_path else default_lock_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    handle = path.open("a+", encoding="utf-8")
    try:
        if _try_lock(handle):
            _unlock(handle)
            return RuntimeState(busy=False)
        return RuntimeState(busy=True, owner=_read_owner_from_handle(handle))
    finally:
        handle.close()


def _pid_exists(pid: Optional[int]) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class MonitorController:
    """Start, discover, and stop the monitor without relying on a local Popen."""

    def __init__(
        self,
        root: Path | str,
        main_program: Path | str,
        python_executable: str,
        lock_path: Path | str | None = None,
    ):
        self.root = Path(root).resolve()
        self.main_program = Path(main_program).resolve()
        self.python_executable = python_executable
        self.lock_path = Path(lock_path) if lock_path else default_lock_path()
        self.child: Optional[subprocess.Popen] = None

    def state(self) -> RuntimeState:
        return get_runtime_state(self.lock_path)

    def start(
        self,
        env: Optional[Mapping[str, str]] = None,
        extra_arguments: Sequence[str] = (),
    ) -> subprocess.Popen:
        state = self.state()
        if state.busy:
            raise DeviceBusyError(state.owner)
        if not self.main_program.is_file():
            raise FileNotFoundError(self.main_program)

        process = subprocess.Popen(
            [
                self.python_executable,
                str(self.main_program),
                *extra_arguments,
            ],
            cwd=str(self.root),
            env=dict(env) if env is not None else None,
            start_new_session=True,
        )
        self.child = process
        return process

    def monitor_owner(self) -> Optional[LockOwner]:
        state = self.state()
        if not state.monitor_running:
            return None

        owner = state.owner
        if owner.root:
            try:
                if Path(owner.root).resolve() != self.root:
                    return None
            except OSError:
                return None
        return owner

    def terminate_monitor(
        self,
        timeout: float = 8.0,
        kill_timeout: float = 2.0,
    ) -> TerminationResult:
        state = self.state()
        if not state.busy:
            return TerminationResult(False, message="Monitor is not running")

        owner = state.owner
        if owner.role != "monitor":
            raise DeviceBusyError(owner)

        if owner.root:
            try:
                owner_root = Path(owner.root).resolve()
            except OSError:
                owner_root = None
            if owner_root is not None and owner_root != self.root:
                raise RuntimeError(
                    "The running monitor belongs to a different project path."
                )

        pid = owner.pid
        if not _pid_exists(pid):
            return TerminationResult(False, message="Monitor process disappeared")

        assert pid is not None
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            return TerminationResult(True, message="Monitor stopped")
        if self._wait_for_release(pid, timeout):
            return TerminationResult(True, message="Monitor stopped")

        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return TerminationResult(True, message="Monitor stopped")
        released = self._wait_for_release(pid, kill_timeout)
        return TerminationResult(
            stopped=released,
            forced=True,
            message=(
                "Monitor was force-stopped"
                if released
                else "Monitor did not release the device lock"
            ),
        )

    def _wait_for_release(self, pid: int, timeout: float) -> bool:
        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < deadline:
            if not _pid_exists(pid) or not self.state().busy:
                return True
            time.sleep(0.1)
        return not _pid_exists(pid) or not self.state().busy
