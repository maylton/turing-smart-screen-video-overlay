#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply Flatpak-only source adjustments to the staged application payload."""

from __future__ import annotations

import sys
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    source = path.read_text(encoding="utf-8")
    if old not in source:
        raise AssertionError(f"Flatpak postprocess hook not found: {label}")
    path.write_text(source.replace(old, new, 1), encoding="utf-8")


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: postprocess.py PAYLOAD_ROOT")

    root = Path(sys.argv[1]).resolve()

    replace_once(
        root / "configure_gtk_app.py",
        'self.bus_name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"',
        'self.bus_name = (os.environ.get("FLATPAK_ID") + ".StatusNotifierItem" if os.environ.get("FLATPAK_ID") else f"org.kde.StatusNotifierItem-{os.getpid()}-1")',
        "StatusNotifier bus name",
    )

    configure = root / "configure-gtk.py"
    replacements = [
        (
            "    def refresh_runtime_status(self):\n"
            "        update_runtime_status(self)\n"
            "        return True\n",
            "    def refresh_runtime_status(self):\n"
            "        update_runtime_status(self)\n"
            "        try:\n"
            "            self.refresh_overview()\n"
            "        except Exception:\n"
            "            pass\n"
            "        return True\n",
            "runtime status refresh",
        ),
        (
            "    def start_monitor(self, *_args):\n"
            "        state = self.runtime_controller.state()\n",
            "    def start_monitor(self, *_args):\n"
            "        if getattr(self, \"detection_running\", False):\n"
            "            if not getattr(self, \"monitor_start_waiting_for_detection\", False):\n"
            "                self.monitor_start_waiting_for_detection = True\n"
            "                self.toast(\"Waiting for display detection to finish…\")\n"
            "\n"
            "                def retry_start_after_detection():\n"
            "                    if getattr(self, \"detection_running\", False):\n"
            "                        return True\n"
            "                    self.monitor_start_waiting_for_detection = False\n"
            "                    self.start_monitor()\n"
            "                    return False\n"
            "\n"
            "                app.GLib.timeout_add(250, retry_start_after_detection)\n"
            "            return\n"
            "\n"
            "        existing = getattr(self, \"monitor_process\", None)\n"
            "        if existing is not None and existing.poll() is None:\n"
            "            self.toast(\"Monitor is already starting\")\n"
            "            self.refresh_overview()\n"
            "            return\n"
            "\n"
            "        state = self.runtime_controller.state()\n",
            "monitor start serialization",
        ),
        (
            "        self.toast(\"Monitor is starting\")\n"
            "        app.GLib.timeout_add(350, self.finish_monitor_start)\n",
            "        self.monitor_start_deadline = time.monotonic() + 10.0\n"
            "        self.toast(\"Monitor is starting\")\n"
            "        app.GLib.timeout_add(350, self.finish_monitor_start)\n",
            "monitor start deadline",
        ),
        (
            "    def finish_monitor_start(self):\n"
            "        process = self.monitor_process\n"
            "        if process is not None and process.poll() is not None:\n"
            "            self.toast(f\"Monitor exited with status {process.returncode}\")\n"
            "            reap_monitor_child(self, timeout=0.0)\n"
            "            self.monitor_process = None\n"
            "        self.refresh_overview()\n"
            "        return False\n",
            "    def finish_monitor_start(self):\n"
            "        process = self.monitor_process\n"
            "        state = self.runtime_controller.state()\n"
            "\n"
            "        if state.monitor_running:\n"
            "            self.refresh_overview()\n"
            "            return False\n"
            "\n"
            "        if process is not None and process.poll() is not None:\n"
            "            self.toast(f\"Monitor exited with status {process.returncode}\")\n"
            "            reap_monitor_child(self, timeout=0.0)\n"
            "            self.monitor_process = None\n"
            "            self.refresh_overview()\n"
            "            return False\n"
            "\n"
            "        self.refresh_overview()\n"
            "        deadline = float(getattr(self, \"monitor_start_deadline\", 0.0) or 0.0)\n"
            "        if process is not None and process.poll() is None and time.monotonic() < deadline:\n"
            "            return True\n"
            "\n"
            "        if process is not None and process.poll() is None:\n"
            "            try:\n"
            "                process.terminate()\n"
            "                process.wait(timeout=2.0)\n"
            "            except Exception:\n"
            "                try:\n"
            "                    process.kill()\n"
            "                except Exception:\n"
            "                    pass\n"
            "            reap_monitor_child(self, timeout=0.0)\n"
            "            self.monitor_process = None\n"
            "            self.toast(\"Monitor startup timed out; try Start Monitor again\")\n"
            "            self.refresh_overview()\n"
            "        return False\n",
            "monitor start state polling",
        ),
    ]
    source = configure.read_text(encoding="utf-8")
    for old, new, label in replacements:
        if old not in source:
            raise AssertionError(f"Flatpak postprocess hook not found: {label}")
        source = source.replace(old, new, 1)
    configure.write_text(source, encoding="utf-8")

    replace_once(
        root / "library/main_app_dashboard_polish.py",
        '''        apply_button = Gtk.Button(
            label="Apply + Start",
            icon_name="media-playback-start-symbolic",
        )
        apply_button.add_css_class("suggested-action")
        apply_button.set_tooltip_text("Apply, sync video, then start the monitor")
        apply_button.connect(
            "clicked",
            lambda *_: _call_if_available(
                self,
                "apply_current_theme_sync_and_start",
                "Apply + Sync is available from the Themes page",
            ),
        )
        attach_button(apply_button, 2, 0)
''',
        '''        start_button = Gtk.Button(
            label="Start monitor",
            icon_name="media-playback-start-symbolic",
        )
        start_button.add_css_class("suggested-action")
        start_button.set_tooltip_text("Start the monitor using the active theme")
        start_button.set_action_name("win.start-monitor")
        attach_button(start_button, 2, 0)
''',
        "dashboard Start monitor button",
    )

    replace_once(
        root / "library/runtime.py",
        '''        else:
            process_options["start_new_session"] = True
''',
        '''        else:
            # Keep the monitor in the Flatpak application's process group so a
            # real terminal interrupt/application shutdown cannot orphan it.
            # Native installs retain the historical detached-session behavior.
            process_options["start_new_session"] = not bool(os.environ.get("FLATPAK_ID"))
''',
        "monitor process group",
    )

    sensors = root / "library/sensors/sensors_python.py"
    source = sensors.read_text(encoding="utf-8")
    sensor_replacements = [
        (
            "class GpuAmd(sensors.Gpu):\n    selected_index = -1\n",
            "class GpuAmd(sensors.Gpu):\n    selected_index = -1\n    selected_gpu = None\n",
            "AMD GPU cache field",
        ),
        (
            "        if GpuAmd.selected_index < 0:\n"
            "            GpuAmd.selected_index = GpuAmd.preferred_linux_gpu_index()\n"
            "        if GpuAmd.selected_index < 0:\n"
            "            raise RuntimeError(\"No AMD GPU was detected\")\n"
            "\n"
            "        return pyamdgpuinfo.get_gpu(GpuAmd.selected_index)\n",
            "        if GpuAmd.selected_index < 0:\n"
            "            GpuAmd.selected_index = GpuAmd.preferred_linux_gpu_index()\n"
            "        if GpuAmd.selected_index < 0:\n"
            "            raise RuntimeError(\"No AMD GPU was detected\")\n"
            "\n"
            "        if GpuAmd.selected_gpu is None:\n"
            "            GpuAmd.selected_gpu = pyamdgpuinfo.get_gpu(GpuAmd.selected_index)\n"
            "        return GpuAmd.selected_gpu\n",
            "AMD GPU cache lookup",
        ),
        (
            "                    selected_gpu = pyamdgpuinfo.get_gpu(selected_index)\n"
            "                    try:\n",
            "                    selected_gpu = pyamdgpuinfo.get_gpu(selected_index)\n"
            "                    GpuAmd.selected_gpu = selected_gpu\n"
            "                    try:\n",
            "AMD GPU cache selection",
        ),
    ]
    for old, new, label in sensor_replacements:
        if old not in source:
            raise AssertionError(f"Flatpak postprocess hook not found: {label}")
        source = source.replace(old, new, 1)
    sensors.write_text(source, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
