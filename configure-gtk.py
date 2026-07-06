#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime-stable launcher for the GTK4 configuration application.

The visual application remains in ``configure_gtk_app.py``. This launcher
adds process discovery, explicit autostart, and non-blocking stop operations
without duplicating the large GTK interface.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import traceback
import time
from pathlib import Path

from library.runtime import DeviceBusyError, MonitorController
from library.theme_gallery import (
    ThemeGalleryPane,
    ThemeRecord,
    set_current_theme as gallery_set_current_theme,
    show_set_current_theme_dialog,
    show_theme_gallery_diagnostics_dialog,
)

ROOT = Path(__file__).resolve().parent
APP_MODULE = ROOT / "configure_gtk_app.py"
START_MONITOR_FILE = (
    Path.home()
    / ".config"
    / "turing-smart-screen"
    / "start-monitor.conf"
)
THEME_GALLERY_DEBUG_ENV = "TURING_THEME_GALLERY_DEBUG"


def theme_gallery_debug_enabled() -> bool:
    return os.environ.get(THEME_GALLERY_DEBUG_ENV, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "debug",
    }


def theme_gallery_debug(message: str) -> None:
    if theme_gallery_debug_enabled():
        print(f"[theme-gallery] {message}", file=sys.stderr, flush=True)


def load_boolean(path: Path, default: bool = False) -> bool:
    try:
        value = path.read_text(encoding="utf-8").strip().lower()
    except OSError:
        return default
    return value in {"1", "true", "yes", "on"}


def save_boolean(path: Path, enabled: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("true\n" if enabled else "false\n", encoding="utf-8")
    os.replace(temporary, path)


def load_app_module():
    spec = importlib.util.spec_from_file_location(
        "turing_smart_screen_gtk_app", APP_MODULE
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {APP_MODULE.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def install_runtime_patches(app):
    original_init = app.SmartScreenWindow.__init__
    original_refresh_overview = app.SmartScreenWindow.refresh_overview
    original_refresh_theme_list = app.SmartScreenWindow.refresh_theme_list

    def reap_monitor_child(self, timeout=2.0):
        """Collect a monitor process started by this GTK application."""
        process = (
            self.monitor_process
            if self.monitor_process is not None
            else self.runtime_controller.child
        )
        if process is None:
            return False

        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return False
        except (ChildProcessError, OSError):
            if process.poll() is None:
                return False

        if self.runtime_controller.child is process:
            self.runtime_controller.child = None
        return True

    def patched_init(self, application):
        self.runtime_controller = MonitorController(
            root=app.ROOT,
            main_program=app.MAIN_PROGRAM,
            python_executable=app.project_python(),
        )
        self.runtime_stop_in_progress = False
        original_init(self, application)
        app.GLib.timeout_add_seconds(2, self.refresh_runtime_status)

    def update_runtime_status(self):
        state = self.runtime_controller.state()
        if state.monitor_running:
            owner = state.owner
            subtitle = (
                f"Running (PID {owner.pid})" if owner.pid else "Running"
            )
        elif state.busy:
            subtitle = "Device busy: " + state.owner.describe()
        else:
            subtitle = "Stopped"
        self.process_status_row.set_subtitle(subtitle)
        return state

    def refresh_runtime_status(self):
        update_runtime_status(self)
        return True

    def patched_refresh_overview(self):
        original_refresh_overview(self)

        if self.current_theme:
            static_preview = app.THEMES_DIR / self.current_theme / "preview.png"

            if static_preview.is_file():
                cache_dir = app.ROOT / ".cache" / "overview-static-preview"
                cache_dir.mkdir(parents=True, exist_ok=True)
                cache_file = cache_dir / f"{self.current_theme}-{int(time.time() * 1000)}.png"

                try:
                    shutil.copy2(static_preview, cache_file)
                    self.set_picture(self.overview_picture, cache_file)
                except Exception as exc:
                    print(
                        f"[overview-preview] failed to copy preview.png: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
                    self.set_picture(self.overview_picture, static_preview)

            self.theme_path_label.set_label(
                str(app.THEMES_DIR / self.current_theme)
            )
        else:
            self.theme_path_label.set_label("")

        update_runtime_status(self)

    def build_themes_page(self):
        outer = app.Gtk.Box(
            orientation=app.Gtk.Orientation.VERTICAL,
            spacing=14,
            margin_top=18,
            margin_bottom=18,
            margin_start=18,
            margin_end=18,
        )

        header = app.Gtk.Box(
            orientation=app.Gtk.Orientation.HORIZONTAL,
            spacing=12,
        )
        title_box = app.Gtk.Box(
            orientation=app.Gtk.Orientation.VERTICAL,
            spacing=4,
        )
        title_box.set_hexpand(True)
        title = app.Gtk.Label(label="Themes", xalign=0)
        title.add_css_class("title-1")
        subtitle = app.Gtk.Label(
            label=(
                "Browse installed themes, inspect diagnostics, edit a theme, "
                "or choose the current theme."
            ),
            xalign=0,
            wrap=True,
        )
        subtitle.add_css_class("dim-label")
        title_box.append(title)
        title_box.append(subtitle)
        header.append(title_box)

        create_button = app.Gtk.Button(
            label="Create blank",
            icon_name="list-add-symbolic",
            tooltip_text="Create an empty theme for the selected display",
            valign=app.Gtk.Align.CENTER,
        )
        create_button.connect(
            "clicked",
            lambda *_: self.show_create_empty_theme_dialog(),
        )
        header.append(create_button)

        refresh_button = app.Gtk.Button(
            icon_name="view-refresh-symbolic",
            tooltip_text="Refresh theme gallery",
            valign=app.Gtk.Align.CENTER,
        )
        refresh_button.connect("clicked", lambda *_: self.refresh_theme_list())
        header.append(refresh_button)

        outer.append(header)

        self.theme_gallery = ThemeGalleryPane(
            on_open_theme=self.open_theme_record_editor,
            on_open_folder=self.open_theme_record_folder,
            on_theme_diagnostics=self.show_theme_record_diagnostics,
            on_set_current_theme=self.confirm_set_current_theme_from_gallery,
            on_sync_theme_video=self.sync_theme_video_from_gallery,
            on_records_changed=self.on_theme_gallery_records_changed,
        )
        self.theme_gallery.set_vexpand(True)
        self.theme_gallery.set_hexpand(True)
        outer.append(self.theme_gallery)
        return outer

    def on_theme_gallery_records_changed(self, records: list[ThemeRecord]):
        self.current_theme = app.read_current_theme()
        self.refresh_overview()

    def refresh_theme_list(self):
        gallery = getattr(self, "theme_gallery", None)
        if gallery is not None:
            gallery.reload_themes()
            return
        original_refresh_theme_list(self)

    def open_theme_record_editor(self, record: ThemeRecord):
        self.launch_script(
            app.THEME_EDITOR,
            record.name,
            use_system_python=True,
        )

    def directory_default_app(self) -> str:
        if shutil.which("xdg-mime") is None:
            return ""
        try:
            result = subprocess.run(
                ["xdg-mime", "query", "default", "inode/directory"],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
        except Exception as exc:
            theme_gallery_debug(f"xdg-mime query failed: {exc!r}")
            return ""
        default_app = result.stdout.strip()
        theme_gallery_debug(
            f"xdg-mime default inode/directory={default_app!r} returncode={result.returncode}"
        )
        return default_app

    def file_manager_commands_for_default(self, default_app: str, path: Path):
        default_key = default_app.casefold()
        commands: list[list[str]] = []

        if "nautilus" in default_key:
            commands.append(["nautilus", "--new-window", str(path)])
        elif "dolphin" in default_key:
            commands.append(["dolphin", str(path)])
        elif "thunar" in default_key:
            commands.append(["thunar", str(path)])
        elif "nemo" in default_key:
            commands.append(["nemo", str(path)])
        elif "pcmanfm" in default_key:
            commands.append(["pcmanfm", str(path)])

        for command in (
            ["nautilus", "--new-window", str(path)],
            ["dolphin", str(path)],
            ["thunar", str(path)],
            ["nemo", str(path)],
            ["pcmanfm", str(path)],
        ):
            if command not in commands:
                commands.append(command)
        return commands

    def launch_file_manager_directly(self, path: Path, default_app: str) -> bool:
        for command in file_manager_commands_for_default(self, default_app, path):
            executable = shutil.which(command[0])
            theme_gallery_debug(f"which {command[0]} -> {executable}")
            if executable is None:
                continue
            theme_gallery_debug(f"launching {' '.join(command)}")
            try:
                subprocess.Popen(
                    command,
                    cwd=str(ROOT),
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                theme_gallery_debug(f"launched {' '.join(command)}")
                return True
            except Exception as exc:
                theme_gallery_debug(f"{' '.join(command)} failed: {exc!r}")
        return False

    def open_theme_record_folder_debuggable(self, record: ThemeRecord):
        path = record.directory
        uri = path.resolve().as_uri() if path.exists() else "<missing>"
        theme_gallery_debug("open folder clicked")
        theme_gallery_debug(f"theme={record.name}")
        theme_gallery_debug(f"path={path}")
        theme_gallery_debug(f"resolved={path.resolve() if path.exists() else '<missing>'}")
        theme_gallery_debug(f"exists={path.exists()} is_dir={path.is_dir()}")
        theme_gallery_debug(f"uri={uri}")
        theme_gallery_debug(f"cwd={Path.cwd()}")
        for key in (
            "XDG_CURRENT_DESKTOP",
            "DESKTOP_SESSION",
            "WAYLAND_DISPLAY",
            "DISPLAY",
            "PATH",
        ):
            theme_gallery_debug(f"env {key}={os.environ.get(key, '<unset>')}")

        if not path.is_dir():
            raise FileNotFoundError(path)

        default_app = directory_default_app(self)
        known_default = any(
            token in default_app.casefold()
            for token in ("nautilus", "dolphin", "thunar", "nemo", "pcmanfm")
        )
        running_niri = os.environ.get("XDG_CURRENT_DESKTOP", "").casefold() == "niri"
        prefer_direct_file_manager = running_niri or not known_default

        if prefer_direct_file_manager:
            theme_gallery_debug(
                "preferring direct file manager because "
                f"running_niri={running_niri} known_default={known_default}"
            )
            if launch_file_manager_directly(self, path, default_app):
                return

        errors: list[str] = []
        try:
            theme_gallery_debug("trying app.Gio.AppInfo.launch_default_for_uri")
            launched = app.Gio.AppInfo.launch_default_for_uri(uri, None)
            theme_gallery_debug(
                f"app.Gio.AppInfo.launch_default_for_uri returned {launched!r}"
            )
            if launched and not prefer_direct_file_manager:
                return
        except Exception as exc:
            errors.append(f"app.Gio launch failed: {exc}")
            theme_gallery_debug(f"app.Gio launch failed: {exc!r}")

        for command in (
            ["gio", "open", str(path)],
            ["xdg-open", str(path)],
        ):
            executable = shutil.which(command[0])
            theme_gallery_debug(f"which {command[0]} -> {executable}")
            if executable is None:
                errors.append(f"{command[0]} not found")
                continue
            theme_gallery_debug(f"running {' '.join(command)}")
            try:
                result = subprocess.run(
                    command,
                    cwd=str(ROOT),
                    text=True,
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                errors.append(f"{' '.join(command)} timed out: {exc}")
                theme_gallery_debug(f"{' '.join(command)} timed out")
                continue
            except Exception as exc:
                errors.append(f"{' '.join(command)} failed: {exc}")
                theme_gallery_debug(f"{' '.join(command)} failed: {exc!r}")
                continue
            stdout = result.stdout.strip()
            stderr = result.stderr.strip()
            theme_gallery_debug(
                f"{' '.join(command)} returncode={result.returncode} stdout={stdout!r} stderr={stderr!r}"
            )
            if result.returncode == 0 and not prefer_direct_file_manager:
                return
            if result.returncode != 0:
                errors.append(
                    f"{' '.join(command)} exited {result.returncode}: {stderr or stdout or 'no output'}"
                )

        if launch_file_manager_directly(self, path, default_app):
            return

        raise RuntimeError("Could not open folder. " + " | ".join(errors))

    def open_theme_record_folder(self, record: ThemeRecord):
        theme_gallery_debug(f"folder button callback fired for {record.name}")
        try:
            open_theme_record_folder_debuggable(self, record)
        except Exception as exc:
            theme_gallery_debug(f"open folder failed: {exc!r}")
            self.toast(f"Could not open theme folder: {exc}")
            return
        theme_gallery_debug(f"open folder finished for {record.name}")
        self.toast(f"Opening folder for {record.name}")

    def show_theme_record_diagnostics(self, record: ThemeRecord):
        show_theme_gallery_diagnostics_dialog(self, record, self.toast)

    def parse_video_manager_json(stdout: str, stderr: str = "") -> dict:
        raw_stdout = stdout or ""

        if raw_stdout.strip():
            try:
                payload = json.loads(raw_stdout)
                if payload:
                    return payload
            except json.JSONDecodeError:
                pass

        for line in reversed(raw_stdout.splitlines()):
            candidate = line.strip()
            if not candidate.startswith("{") or not candidate.endswith("}"):
                continue
            try:
                payload = json.loads(candidate)
                if payload:
                    return payload
            except json.JSONDecodeError:
                continue

        output = (raw_stdout or stderr or "").strip()
        raise RuntimeError(
            f"video_manager.py did not return a JSON payload. Output: {output[-1200:] or '<empty>'}"
        )

    def run_video_manager_json(arguments: list[str]) -> dict:
        backend = app.ROOT / "video_manager.py"
        if not backend.is_file():
            raise FileNotFoundError(backend)

        try:
            result = subprocess.run(
                [
                    app.project_python(),
                    str(backend),
                    "--force",
                    "--json",
                    *arguments,
                ],
                cwd=str(app.ROOT),
                text=True,
                capture_output=True,
                timeout=180,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"video_manager.py timed out while running: {' '.join(arguments)}") from exc

        payload = None
        parse_error = None

        try:
            payload = parse_video_manager_json(result.stdout, result.stderr)
        except Exception as exc:
            parse_error = exc

        if isinstance(payload, dict):
            if payload.get("ok"):
                return payload

            error = payload.get("error") or {}
            message = error.get("message") or str(payload)
            raise RuntimeError(message)

        output = (result.stderr or result.stdout or "").strip()

        if result.returncode != 0:
            raise RuntimeError(
                output
                or f"video_manager.py exited {result.returncode} without JSON"
            )

        if parse_error is not None:
            raise RuntimeError(str(parse_error))

        raise RuntimeError("video_manager.py did not return a JSON payload")

    def read_theme_video_config_from_record(record: ThemeRecord) -> dict:
        if record.yaml_file is None or not record.yaml_file.is_file():
            raise RuntimeError(f"{record.name} has no theme.yaml/theme.yml")

        import yaml

        data = yaml.safe_load(record.yaml_file.read_text(encoding="utf-8")) or {}
        video = data.get("video")
        if not isinstance(video, dict):
            return {}

        enabled = bool(video.get("ENABLED", video.get("SHOW", False)))
        if not enabled:
            return {}

        local_raw = str(video.get("LOCAL_PATH") or "").strip()
        remote = str(video.get("PATH") or "").strip()

        if not local_raw and not remote:
            return {}

        local = Path(local_raw).expanduser() if local_raw else None
        if local is not None and not local.is_absolute():
            local = record.directory / local

        if not remote and local is not None:
            remote = "/mnt/SDCARD/video/" + local.name

        if not remote.startswith(("/mnt/SDCARD/video/", "/root/video/")):
            remote = "/mnt/SDCARD/video/" + Path(remote).name

        return {
            "theme": record.name,
            "local": local,
            "remote": remote,
            "filename": Path(remote).name,
            "internal": remote.startswith("/root/video/"),
        }

    def display_has_video(video: dict) -> bool:
        args = ["list"]
        if video.get("internal"):
            args.append("--internal")

        payload = run_video_manager_json_for_theme_apply(self, args)
        files = payload.get("data", {}).get("files") or []
        wanted = str(video.get("filename") or "")
        return wanted in {str(item) for item in files}

    def sync_theme_video_worker(self, record: ThemeRecord):
        error = ""
        message = ""

        try:
            video = read_theme_video_config_from_record(record)
            if not video:
                raise RuntimeError(f"{record.name} does not declare an enabled local video")

            local = video.get("local")
            if local is None or not Path(local).is_file():
                raise FileNotFoundError(f"Theme video file was not found: {local}")

            message = sync_theme_video_via_backend_for_theme_apply(self, video)

        except Exception as exc:
            error = str(exc)

        app.GLib.idle_add(self.finish_sync_theme_video, record.name, message, error)

    def sync_current_theme_video_from_gallery(self):
        gallery = getattr(self, "theme_gallery", None)
        if gallery is None:
            self.toast("Theme gallery is not loaded")
            return

        current_name = app.read_current_theme()
        if not current_name:
            self.toast("No active theme configured")
            return

        record = None
        for candidate in getattr(gallery, "records", []):
            if candidate.name == current_name:
                record = candidate
                break

        if record is None:
            gallery.reload_themes()
            for candidate in getattr(gallery, "records", []):
                if candidate.name == current_name:
                    record = candidate
                    break

        if record is None:
            self.toast(f"Active theme was not found in gallery: {current_name}")
            return

        self.sync_theme_video_from_gallery(record)

    def sync_theme_video_from_gallery(self, record: ThemeRecord):
        state = self.runtime_controller.state()
        if state.busy:
            if state.monitor_running:
                self.toast("Stop the monitor before syncing theme video")
            else:
                self.toast("Display is busy: " + state.owner.describe())
            update_runtime_status(self)
            return

        self.toast(f"Syncing video for {record.name}…")
        threading.Thread(
            target=sync_theme_video_worker,
            args=(self, record),
            daemon=True,
        ).start()

    def finish_sync_theme_video(self, theme_name: str, message: str, error: str):
        update_runtime_status(self)
        if error:
            self.toast(f"Could not sync video for {theme_name}: {error}")
        else:
            self.toast(message or f"Video synced for {theme_name}")
        return False

    def confirm_set_current_theme_from_gallery(self, record: ThemeRecord):
        show_set_current_theme_dialog(
            self,
            record,
            self.apply_set_current_theme_from_gallery,
        )

    def wait_until_display_free_for_theme_apply(self, timeout: float = 12.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            state = self.runtime_controller.state()
            if not state.busy:
                return True
            time.sleep(0.25)
        return not self.runtime_controller.state().busy

    def process_exists_for_theme_apply(pid: int | None) -> bool:
        if not pid:
            return False
        try:
            os.kill(int(pid), 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except Exception:
            return False
        return True

    def list_screen_serial_devices_for_theme_apply() -> list[Path]:
        """Return ttyACM devices that look like the real display, not UsbMonitor."""
        try:
            result = subprocess.run(
                [
                    app.project_python(),
                    "-c",
                    (
                        "import json\n"
                        "from serial.tools import list_ports\n"
                        "print(json.dumps([p._asdict() for p in list_ports.comports()]))\n"
                    ),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                ports = json.loads(result.stdout)
                devices = []
                for port in ports:
                    device = str(port.get("device") or "")
                    haystack = " ".join(
                        str(port.get(key) or "")
                        for key in ("description", "manufacturer", "product", "interface")
                    ).casefold()
                    if not device.startswith("/dev/ttyACM"):
                        continue
                    if "usbmonitor" in haystack:
                        continue
                    if Path(device).exists():
                        devices.append(Path(device))
                if devices:
                    return sorted(devices)
        except Exception:
            pass

        # Fallback only when pyserial metadata is unavailable.
        return sorted(Path("/dev").glob("ttyACM*"))

    def wait_for_serial_device_for_theme_apply(timeout: float = 30.0) -> list[Path]:
        """Wait until the real display serial port is visible and stable."""
        deadline = time.monotonic() + timeout
        stable_key = None
        stable_count = 0

        try:
            subprocess.run(
                ["udevadm", "settle", "--timeout=5"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

        while time.monotonic() < deadline:
            devices = list_screen_serial_devices_for_theme_apply()
            key = tuple(str(device) for device in devices)

            if devices and key == stable_key:
                stable_count += 1
            else:
                stable_key = key
                stable_count = 1 if devices else 0

            if devices and stable_count >= 4:
                time.sleep(1.2)
                return devices

            time.sleep(0.4)

        devices = list_screen_serial_devices_for_theme_apply()
        if devices:
            time.sleep(1.2)
        return devices

    def monitor_pids_for_theme_apply() -> list[int]:
        current_pid = os.getpid()
        pids: set[int] = set()
        patterns = [
            str(app.MAIN_PROGRAM),
            "[m]ain.py",
        ]

        for pattern in patterns:
            try:
                result = subprocess.run(
                    ["pgrep", "-f", pattern],
                    cwd=str(app.ROOT),
                    text=True,
                    capture_output=True,
                    timeout=3,
                    check=False,
                )
            except Exception:
                continue

            for line in result.stdout.splitlines():
                try:
                    pid = int(line.strip())
                except ValueError:
                    continue
                if pid != current_pid:
                    pids.add(pid)

        return sorted(pids)

    def wait_until_monitor_processes_exit_for_theme_apply(timeout: float = 10.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not monitor_pids_for_theme_apply():
                return True
            time.sleep(0.35)
        return not monitor_pids_for_theme_apply()

    def force_release_monitor_for_theme_apply(self, timeout: float = 18.0) -> None:
        """Stop any running main.py and wait until it releases the serial port."""
        deadline = time.monotonic() + timeout

        def wait_free(seconds: float) -> bool:
            wait_deadline = time.monotonic() + seconds
            while time.monotonic() < wait_deadline:
                if not self.runtime_controller.state().busy:
                    return True
                time.sleep(0.25)
            return not self.runtime_controller.state().busy

        state = self.runtime_controller.state()
        if state.monitor_running:
            try:
                self.runtime_controller.terminate_monitor(timeout=5.0, kill_timeout=3.0)
                reap_monitor_child(self, timeout=0.0)
            except Exception:
                pass

        # The runtime lock can be released before main.py has fully finished
        # closing the native video worker. Wait for the actual process too.
        if wait_free(2.0) and wait_until_monitor_processes_exit_for_theme_apply(timeout=6.0):
            time.sleep(1.0)
            return

        patterns = [
            str(app.MAIN_PROGRAM),
            "[m]ain.py",
        ]

        for pattern in patterns:
            try:
                subprocess.run(
                    ["pkill", "-TERM", "-f", pattern],
                    cwd=str(app.ROOT),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass

        while time.monotonic() < deadline:
            if wait_free(0.5) and wait_until_monitor_processes_exit_for_theme_apply(timeout=0.5):
                time.sleep(1.2)
                return
            time.sleep(0.25)

        for pattern in patterns:
            try:
                subprocess.run(
                    ["pkill", "-KILL", "-f", pattern],
                    cwd=str(app.ROOT),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except Exception:
                pass

        if wait_free(3.0) and wait_until_monitor_processes_exit_for_theme_apply(timeout=3.0):
            time.sleep(1.2)
            return

        state = self.runtime_controller.state()
        pids = monitor_pids_for_theme_apply()
        if state.busy or pids:
            detail = state.owner.describe() if state.busy else f"monitor pids still alive: {pids}"
            raise RuntimeError("Display is still busy after stopping monitor: " + detail)


    def theme_apply_video_error_is_retryable(message: str) -> bool:
        lowered = message.casefold()
        retry_tokens = (
            "already in use by monitor",
            "devicebusyerror",
            "display is already in use",
            "serialexception",
            "failed to read serial data",
            "failed to send serial data",
            "cannot open com port",
            "cannot find com port automatically",
            "select com port manually",
            "could not open port",
            "arquivo ou diretório inexistente",
            "no such file or directory",
            "/dev/ttyacm",
            "invalid or unsupported id",
            "display returned invalid",
            "did not return a valid id",
            "input/output error",
            "i/o error",
            "device disconnected",
            "descriptor de arquivo inválido",
            "bad file descriptor",
        )
        return any(token in lowered for token in retry_tokens)

    def run_video_manager_json_for_theme_apply(self, arguments: list[str]) -> dict:
        last_error: Exception | None = None
        delays = (1.0, 2.5, 4.0, 6.0, 8.0)

        for attempt, delay in enumerate(delays, start=1):
            force_release_monitor_for_theme_apply(self, timeout=18.0)
            wait_for_serial_device_for_theme_apply(timeout=15.0)

            if attempt > 1:
                time.sleep(delay)
                wait_for_serial_device_for_theme_apply(timeout=15.0)

            try:
                return run_video_manager_json(arguments)
            except Exception as exc:
                last_error = exc
                message = str(exc)
                print(
                    "[theme-video-sync] "
                    f"attempt {attempt}/{len(delays)} failed for "
                    f"{' '.join(arguments)}: {message}",
                    file=sys.stderr,
                    flush=True,
                )

                if attempt < len(delays) and theme_apply_video_error_is_retryable(message):
                    continue

                raise

        if last_error is not None:
            raise last_error

        raise RuntimeError("video_manager.py did not complete")

    def display_has_video_for_theme_apply(self, video: dict) -> bool:
        args = ["list"]
        if video.get("internal"):
            args.append("--internal")

        payload = run_video_manager_json_for_theme_apply(self, args)
        files = payload.get("data", {}).get("files") or []
        wanted = str(video.get("filename") or "")
        return wanted in {str(item) for item in files}

    def load_video_manager_backend_for_theme_apply():
        backend_file = app.ROOT / "video_manager_backend.py"
        if not backend_file.is_file():
            raise FileNotFoundError(backend_file)

        spec = importlib.util.spec_from_file_location(
            "turing_theme_apply_video_backend",
            backend_file,
        )
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load {backend_file.name}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


    def install_theme_video_sync_bounded_hello(backend) -> None:
        """Prevent Rev. C hello detection from looping forever during video sync.

        LcdCommRevC._hello normally retries forever when the display returns an
        empty/invalid ID. That is OK for the long-running monitor, but during
        theme video sync it can permanently stall the GTK worker. Bound it here
        so the outer sync retry loop can wait, try another ttyACM candidate, or
        fail with a visible toast.
        """
        if getattr(backend.LcdCommRevC, "_theme_video_sync_bounded_hello", False):
            return

        def bounded_hello(self):
            import string as _string

            self.sub_revision = self._get_sub_revision()
            printable = set(_string.printable)
            response = ""
            last_error = None

            for attempt in range(6):
                try:
                    self.serial_flush_input()
                    self._send_command(backend.Command.HELLO, bypass_queue=True)
                    response = "".join(
                        filter(
                            lambda x: x in printable,
                            str(self.serial_read(23).decode(errors="ignore")),
                        )
                    )
                    self.serial_flush_input()
                    print(
                        f"[theme-video-sync] hello attempt {attempt + 1}/6 returned: {response!r}",
                        file=sys.stderr,
                        flush=True,
                    )
                    if response.startswith("chs_"):
                        break
                except Exception as exc:
                    last_error = exc
                    print(
                        f"[theme-video-sync] hello attempt {attempt + 1}/6 failed: {exc!r}",
                        file=sys.stderr,
                        flush=True,
                    )

                time.sleep(1.0)
            else:
                detail = f"; last error: {last_error!r}" if last_error else ""
                raise RuntimeError(
                    "Display did not return a valid ID during theme video sync: "
                    f"{response!r}{detail}"
                )

            self.sub_revision = self._get_sub_revision()
            try:
                self.rom_version = int(response.split(".")[2])
                if self.rom_version < 80 or self.rom_version > 100:
                    self.rom_version = 87
            except Exception:
                self.rom_version = 87

        backend.LcdCommRevC._hello = bounded_hello
        backend.LcdCommRevC._theme_video_sync_bounded_hello = True



    def cleanup_previous_theme_videos_for_theme_apply(manager, current_remote: str) -> list[str]:
        """Keep the display video storage in single-theme-video mode.

        The original app behavior kept only one theme video on the display at a
        time. Recreate that behavior by deleting stale video files before
        uploading the active theme video.
        """
        video_extensions = (".mp4", ".mov", ".mkv", ".avi", ".webm")
        current_remote = str(current_remote)
        current_name = Path(current_remote).name
        current_base = (
            "/root/video/"
            if current_remote.startswith("/root/video/")
            else "/mnt/SDCARD/video/"
        )

        locations = [
            ("/mnt/SDCARD/video/", False),
            ("/root/video/", True),
        ]

        removed: list[str] = []

        for base, internal in locations:
            try:
                _directories, files = manager.list_videos(internal=internal)
            except Exception as exc:
                print(
                    f"[theme-video-sync] could not list stale videos in {base}: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
                continue

            for item in files:
                filename = Path(str(item).strip()).name
                if not filename:
                    continue
                if not filename.casefold().endswith(video_extensions):
                    continue
                if base == current_base and filename == current_name:
                    continue

                remote_path = base + filename
                try:
                    manager.delete(remote_path)
                    removed.append(remote_path)
                    print(
                        f"[theme-video-sync] removed stale display video: {remote_path}",
                        file=sys.stderr,
                        flush=True,
                    )
                    time.sleep(0.25)
                except Exception as exc:
                    print(
                        f"[theme-video-sync] could not remove stale display video "
                        f"{remote_path}: {exc}",
                        file=sys.stderr,
                        flush=True,
                    )

        return removed


    def sync_theme_video_via_backend_for_theme_apply(self, video: dict) -> str:
        """Sync theme video using single-video storage semantics."""
        from library.runtime import DeviceLock

        log_file = Path("/tmp/turing-theme-video-sync.log")

        wanted = str(video.get("filename") or Path(str(video["remote"])).name)
        local = Path(video["local"])
        remote = str(video["remote"])
        internal = bool(video.get("internal"))

        del internal  # get_size/upload use the full remote path.

        last_error: Exception | None = None
        last_com_port = "AUTO"
        last_candidates: list[str] = []

        for attempt in range(6):
            force_release_monitor_for_theme_apply(self, timeout=22.0)
            devices = wait_for_serial_device_for_theme_apply(timeout=25.0)

            if attempt:
                time.sleep(min(2.0 * attempt, 7.0))
                retry_devices = wait_for_serial_device_for_theme_apply(timeout=25.0)
                if retry_devices:
                    devices = retry_devices

            candidates = [str(device) for device in devices]
            if not candidates:
                candidates = ["AUTO"]

            last_candidates = candidates

            for com_port in candidates:
                last_com_port = com_port
                print(
                    f"[theme-video-sync] attempt {attempt + 1}/6 using display port {com_port}",
                    file=sys.stderr,
                    flush=True,
                )

                try:
                    backend = load_video_manager_backend_for_theme_apply()
                    install_theme_video_sync_bounded_hello(backend)

                    with DeviceLock(role="theme-video-sync", root=app.ROOT):
                        manager = backend.VideoManager(com_port=com_port)
                        try:
                            removed = cleanup_previous_theme_videos_for_theme_apply(
                                manager,
                                remote,
                            )

                            # Single-video mode: even if the target filename already
                            # exists, replace it so the display storage mirrors the
                            # currently selected theme.
                            manager.upload(
                                local_path=local,
                                remote_path=remote,
                                overwrite=True,
                                packet_delay=0.0,
                            )

                            try:
                                remote_size = manager.get_size(remote)
                                detail = f"Uploaded {wanted} ({remote_size} bytes)"
                            except Exception:
                                detail = f"Uploaded {wanted}"

                            if removed:
                                return detail + f"; removed {len(removed)} old video(s)"
                            return detail
                        finally:
                            manager.close()

                except Exception as exc:
                    last_error = exc
                    log_file.write_text(
                        "[theme-video-sync]\n"
                        f"attempt={attempt + 1}\n"
                        f"wanted={wanted}\n"
                        f"local={local}\n"
                        f"remote={remote}\n"
                        f"com_port={last_com_port}\n"
                        f"candidates={last_candidates}\n"
                        f"error={exc!r}\n\n"
                        + traceback.format_exc(),
                        encoding="utf-8",
                    )

                    message = str(exc).casefold()
                    if theme_apply_video_error_is_retryable(message):
                        continue

                    raise

            time.sleep(min(2.0 * (attempt + 1), 8.0))

        if last_error is not None:
            raise last_error

        raise RuntimeError("Theme video sync did not complete")


    def apply_set_current_theme_from_gallery(self, record: ThemeRecord):
        if self.runtime_stop_in_progress:
            self.toast("Another runtime operation is already in progress")
            return

        try:
            old_theme, new_theme = gallery_set_current_theme(record)
        except Exception as exc:
            self.toast(f"Could not update config.yaml: {exc}")
            return

        self.current_theme = new_theme
        self.refresh_all()

        self.runtime_stop_in_progress = True

        if old_theme and old_theme != new_theme:
            self.toast(f"Active theme changed: {old_theme} → {new_theme}; syncing video…")
        else:
            self.toast(f"Active theme set to {new_theme}; syncing video…")

        threading.Thread(
            target=apply_used_theme_video_and_start_worker,
            args=(self, record, new_theme),
            daemon=True,
        ).start()

    def apply_used_theme_video_and_start_worker(self, record: ThemeRecord, new_theme: str):
        error = ""
        message = ""

        try:
            force_release_monitor_for_theme_apply(self, timeout=18.0)

            video = read_theme_video_config_from_record(record)
            if not video:
                message = f"{new_theme} has no enabled theme video; starting monitor"
            else:
                local = video.get("local")
                if local is None or not Path(local).is_file():
                    raise FileNotFoundError(f"Theme video file was not found: {local}")

                message = sync_theme_video_via_backend_for_theme_apply(self, video)

        except Exception as exc:
            error = str(exc)

        app.GLib.idle_add(
            self.finish_used_theme_video_and_start,
            new_theme,
            message,
            error,
        )

    def finish_used_theme_video_and_start(self, new_theme: str, message: str, error: str):
        self.runtime_stop_in_progress = False
        self.monitor_process = None
        self.refresh_overview()

        def start_monitor_when_display_is_stable():
            try:
                # After video sync/upload, the display may briefly expose only
                # the UsbMonitor port. Starting main.py during that window makes
                # COM auto-detection fail even though the device is about to
                # become available. Wait for the real ttyACM display port to
                # settle before launching the monitor again.
                wait_for_serial_device_for_theme_apply(timeout=30.0)
                time.sleep(1.4)
            except Exception as exc:
                print(
                    f"[theme-video-sync] display settle wait failed before monitor start: {exc}",
                    file=sys.stderr,
                    flush=True,
                )

            app.GLib.idle_add(self.start_monitor)

        if error:
            print(
                f"[theme-video-sync] {new_theme}: {error}",
                file=sys.stderr,
                flush=True,
            )
            self.toast(
                f"Theme set to {new_theme}, but video sync failed. Starting monitor anyway."
            )
            threading.Thread(target=start_monitor_when_display_is_stable, daemon=True).start()
            return False

        self.toast(message or f"{new_theme} synced; starting monitor")
        threading.Thread(target=start_monitor_when_display_is_stable, daemon=True).start()
        return False

    def build_settings_page(self):
        clamp = app.Adw.Clamp(maximum_size=760)
        scrolled = app.Gtk.ScrolledWindow()
        scrolled.set_child(clamp)

        box = app.Gtk.Box(
            orientation=app.Gtk.Orientation.VERTICAL,
            spacing=18,
            margin_top=28,
            margin_bottom=28,
            margin_start=24,
            margin_end=24,
        )
        clamp.set_child(box)

        title = app.Gtk.Label(label="Settings", xalign=0)
        title.add_css_class("title-1")
        box.append(title)

        appearance = app.Adw.PreferencesGroup(
            title="Appearance",
            description=(
                "Choose the application appearance. The selection is saved "
                "for the next session."
            ),
        )
        self.style_row = app.Adw.ComboRow(title="Color scheme")
        self.style_row.set_model(
            app.Gtk.StringList.new(["Follow system", "Light", "Dark"])
        )
        self.style_row.set_selected(
            {"system": 0, "light": 1, "dark": 2}.get(
                self.saved_color_scheme, 0
            )
        )
        self.style_row.connect(
            "notify::selected", self.on_color_scheme_changed
        )
        appearance.add(self.style_row)

        self.start_minimized_row = app.Adw.SwitchRow(
            title="Start application minimized to tray",
            subtitle=(
                "Controls only the GTK window. It does not start the display "
                "monitor."
            ),
        )
        self.start_minimized_row.set_active(app.load_start_minimized())
        self.start_minimized_row.connect(
            "notify::active", self.on_start_minimized_changed
        )
        appearance.add(self.start_minimized_row)
        box.append(appearance)

        runtime_group = app.Adw.PreferencesGroup(
            title="Runtime",
            description=(
                "The monitor owns the display connection exclusively while it "
                "is running."
            ),
        )
        self.start_monitor_row = app.Adw.SwitchRow(
            title="Start monitor automatically",
            subtitle=(
                "Start main.py when this application opens. Keep this disabled "
                "to start the monitor manually."
            ),
        )
        self.start_monitor_row.set_active(
            load_boolean(START_MONITOR_FILE, default=False)
        )
        self.start_monitor_row.connect(
            "notify::active", self.on_start_monitor_changed
        )
        runtime_group.add(self.start_monitor_row)
        box.append(runtime_group)

        maintenance = app.Adw.PreferencesGroup(
            title="Maintenance",
            description=(
                "Verify GTK, Python dependencies, project files, and theme "
                "YAML files."
            ),
        )
        checkup_row = app.Adw.ActionRow(
            title="Program check",
            subtitle=(
                "Verify dependencies, project files, themes, and Python syntax"
            ),
            icon_name="emblem-ok-symbolic",
            activatable=True,
        )
        checkup_row.connect("activated", lambda *_: self.run_checkup())
        checkup_row.add_suffix(
            app.Gtk.Image.new_from_icon_name("go-next-symbolic")
        )
        maintenance.add(checkup_row)
        box.append(maintenance)
        return scrolled

    def on_start_monitor_changed(self, row, _param):
        enabled = row.get_active()
        try:
            save_boolean(START_MONITOR_FILE, enabled)
        except Exception as exc:
            self.toast(f"Could not save monitor startup preference: {exc}")
            return
        self.toast(
            "Monitor will start with the application"
            if enabled
            else "Monitor will be started manually"
        )

    def auto_apply_last_theme(self):
        if not load_boolean(START_MONITOR_FILE, default=False):
            return False
        if not app.read_current_theme():
            self.toast("No saved theme to start automatically")
            return False
        start_monitor(self)
        return False

    def start_monitor(self, *_args):
        state = self.runtime_controller.state()
        if state.busy:
            if state.monitor_running:
                self.toast("Monitor is already running")
            else:
                self.toast("Display is busy: " + state.owner.describe())
            update_runtime_status(self)
            return

        monitor_env = os.environ.copy()
        monitor_env["TURING_DISABLE_PYSTRAY"] = "1"
        try:
            self.monitor_process = self.runtime_controller.start(
                env=monitor_env
            )
        except DeviceBusyError as exc:
            self.toast("Display is busy: " + exc.owner.describe())
            return
        except Exception as exc:
            self.toast(f"Could not start monitor: {exc}")
            return

        self.toast("Monitor is starting")
        app.GLib.timeout_add(350, self.finish_monitor_start)

    def finish_monitor_start(self):
        process = self.monitor_process
        if process is not None and process.poll() is not None:
            self.toast(f"Monitor exited with status {process.returncode}")
            reap_monitor_child(self, timeout=0.0)
            self.monitor_process = None
        self.refresh_overview()
        return False

    def stop_monitor(self, *_args):
        if self.runtime_stop_in_progress:
            self.toast("Monitor stop is already in progress")
            return
        state = self.runtime_controller.state()
        if not state.busy:
            self.toast("Monitor is not running")
            return
        if not state.monitor_running:
            self.toast("Display is busy: " + state.owner.describe())
            return

        self.runtime_stop_in_progress = True
        self.toast("Stopping monitor…")

        def worker():
            try:
                result = self.runtime_controller.terminate_monitor()
                reap_monitor_child(self)
                error = ""
            except Exception as exc:
                result = None
                error = str(exc)
            app.GLib.idle_add(self.finish_monitor_stop, result, error)

        threading.Thread(target=worker, daemon=True).start()

    def finish_monitor_stop(self, result, error):
        self.runtime_stop_in_progress = False
        self.monitor_process = None
        self.refresh_overview()
        if error:
            self.toast(f"Could not stop monitor: {error}")
        elif result is not None:
            self.toast(result.message or "Monitor stopped")
        return False

    def turn_off_display(self, *_args):
        if not app.SCREEN_CONTROL.is_file():
            self.toast("screen-control.py was not found")
            return
        if self.runtime_stop_in_progress:
            self.toast("Another runtime operation is already in progress")
            return

        self.runtime_stop_in_progress = True
        self.toast("Turning off display…")

        def worker():
            try:
                state = self.runtime_controller.state()
                if state.monitor_running:
                    self.runtime_controller.terminate_monitor()
                    reap_monitor_child(self)
                elif state.busy:
                    raise DeviceBusyError(state.owner)

                result = subprocess.run(
                    [app.project_python(), str(app.SCREEN_CONTROL), "off"],
                    cwd=str(app.ROOT),
                    text=True,
                    capture_output=True,
                    check=False,
                )
                returncode = result.returncode
                stdout = result.stdout
                stderr = result.stderr
            except Exception as exc:
                returncode = 1
                stdout = ""
                stderr = str(exc)
            app.GLib.idle_add(
                self.finish_turn_off_display,
                returncode,
                stdout,
                stderr,
            )

        threading.Thread(target=worker, daemon=True).start()

    original_finish_turn_off = app.SmartScreenWindow.finish_turn_off_display

    def finish_turn_off_display(self, returncode, stdout, stderr):
        self.runtime_stop_in_progress = False
        self.monitor_process = None
        return original_finish_turn_off(self, returncode, stdout, stderr)

    app.SmartScreenWindow.__init__ = patched_init
    app.SmartScreenWindow.update_runtime_status = update_runtime_status
    app.SmartScreenWindow.refresh_runtime_status = refresh_runtime_status
    app.SmartScreenWindow.refresh_overview = patched_refresh_overview
    app.SmartScreenWindow.build_themes_page = build_themes_page
    app.SmartScreenWindow.refresh_theme_list = refresh_theme_list
    app.SmartScreenWindow.open_theme_record_editor = open_theme_record_editor
    app.SmartScreenWindow.open_theme_record_folder = open_theme_record_folder
    app.SmartScreenWindow.show_theme_record_diagnostics = show_theme_record_diagnostics
    app.SmartScreenWindow.confirm_set_current_theme_from_gallery = confirm_set_current_theme_from_gallery
    app.SmartScreenWindow.sync_current_theme_video_from_gallery = sync_current_theme_video_from_gallery
    app.SmartScreenWindow.sync_theme_video_from_gallery = sync_theme_video_from_gallery
    app.SmartScreenWindow.finish_sync_theme_video = finish_sync_theme_video
    app.SmartScreenWindow.wait_until_display_free_for_theme_apply = wait_until_display_free_for_theme_apply
    app.SmartScreenWindow.force_release_monitor_for_theme_apply = force_release_monitor_for_theme_apply
    app.SmartScreenWindow.run_video_manager_json_for_theme_apply = run_video_manager_json_for_theme_apply
    app.SmartScreenWindow.display_has_video_for_theme_apply = display_has_video_for_theme_apply
    app.SmartScreenWindow.apply_set_current_theme_from_gallery = apply_set_current_theme_from_gallery
    app.SmartScreenWindow.finish_used_theme_video_and_start = finish_used_theme_video_and_start
    app.SmartScreenWindow.on_theme_gallery_records_changed = on_theme_gallery_records_changed
    app.SmartScreenWindow.build_settings_page = build_settings_page
    app.SmartScreenWindow.on_start_monitor_changed = on_start_monitor_changed
    app.SmartScreenWindow.auto_apply_last_theme = auto_apply_last_theme
    app.SmartScreenWindow.start_monitor = start_monitor
    app.SmartScreenWindow.finish_monitor_start = finish_monitor_start
    app.SmartScreenWindow.stop_monitor = stop_monitor
    app.SmartScreenWindow.finish_monitor_stop = finish_monitor_stop
    app.SmartScreenWindow.turn_off_display = turn_off_display
    app.SmartScreenWindow.finish_turn_off_display = finish_turn_off_display


def main() -> int:
    app = load_app_module()
    install_runtime_patches(app)
    return app.main()


if __name__ == "__main__":
    raise SystemExit(main())
