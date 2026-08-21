#!/usr/bin/env python
# SPDX-License-Identifier: GPL-3.0-or-later
#
# turing-smart-screen-python - a Python system monitor and library for USB-C displays like Turing Smart Screen or XuanFang
# https://github.com/mathoudebine/turing-smart-screen-python/

"""System monitor entry point with safe runtime ownership and shutdown."""

from library.pythoncheck import check_python_version
check_python_version()

import os
import sys

try:
    import atexit
    import locale
    import platform
    import signal
    import subprocess
    import threading
    import time
    from pathlib import Path

    import yaml

    if platform.system() == "Windows":
        import win32api
        import win32con
        import win32gui

    from library.display_shutdown import power_off_and_close_display
    from library.log import logger
    import library.scheduler as scheduler
    from library.runtime import DeviceBusyError, DeviceLock
    from library.tray_icon import load_pystray_image
except Exception as exc:
    print(
        "Import error: %s\n"
        "Please follow the start guide to install required packages: "
        "https://github.com/mathoudebine/turing-smart-screen-python/wiki/"
        "System-monitor-:-how-to-start\n"
        "Or the troubleshooting page: "
        "https://github.com/mathoudebine/turing-smart-screen-python/wiki/"
        "Troubleshooting#all-os-tkinter-dependency-not-installed" % exc,
        file=sys.stderr,
    )
    raise SystemExit(1)

try:
    import pystray
except Exception:
    pystray = None


MAIN_DIRECTORY = Path(__file__).resolve().parent
_DISPLAY = None
_TRAY_ICON = None
_DEVICE_LOCK = None
_RENDERER_CONTROLLER = None
_RENDERER_SELECTION = None
_CLEANUP_LOCK = threading.Lock()
_CLEANUP_STARTED = False


def wait_for_empty_queue(timeout: int = 5) -> None:
    logger.info(
        "Waiting for all pending request to be sent to display (%ds max)..."
        % timeout
    )
    wait_time = 0.0
    while not scheduler.is_queue_empty() and wait_time < timeout:
        time.sleep(0.1)
        wait_time += 0.1
    logger.debug("(Waited %.1fs)" % wait_time)


def perform_cleanup(tray_icon=None) -> None:
    """Release the display exactly once, regardless of the exit path."""
    global _CLEANUP_STARTED

    with _CLEANUP_LOCK:
        if _CLEANUP_STARTED:
            return
        _CLEANUP_STARTED = True

    try:
        scheduler.STOPPING = True
    except Exception:
        pass

    if _RENDERER_CONTROLLER is not None:
        try:
            _RENDERER_CONTROLLER.stop()
        except Exception as exc:
            logger.warning("Could not stop renderer cleanly: %s", exc)

    close_yaml_display()

    icon = tray_icon or _TRAY_ICON
    if icon is not None:
        try:
            icon.visible = False
        except Exception:
            pass

    if _DEVICE_LOCK is not None:
        _DEVICE_LOCK.release()


def close_yaml_display() -> None:
    """Close the legacy renderer transport without touching process ownership."""
    global _DISPLAY
    try:
        scheduler.STOPPING = True
    except Exception:
        pass
    display, _DISPLAY = _DISPLAY, None
    if display is not None:
        lcd = getattr(display, "lcd", None)

        # Final shutdown commands must not remain stranded in the asynchronous
        # update queue. From this point onward, communicate synchronously.
        if lcd is not None:
            try:
                lcd.update_queue = None
            except Exception:
                pass

        try:
            power_off_and_close_display(lcd)
        except Exception as exc:
            logger.warning(
                "Could not turn the display off during shutdown: %s",
                exc,
            )
        # Scheduler callbacks observe STOPPING and leave their loops. Give
        # them a bounded opportunity to finish before reload can reopen serial.
        time.sleep(0.25)



def request_process_exit(exit_code: int = 0) -> None:
    perform_cleanup()
    raise SystemExit(exit_code)


def on_signal_caught(signum, _frame=None) -> None:
    logger.info("Caught signal %d, exiting", signum)
    request_process_exit(0)


def on_clean_exit(*_args) -> None:
    logger.info("Program will now exit")
    perform_cleanup()


def on_configure_tray(tray_icon, _item) -> None:
    logger.info("Configure from tray icon")
    try:
        configure_file = next(MAIN_DIRECTORY.glob("configure.py"))
        subprocess.Popen([sys.executable, str(configure_file)])
    except Exception:
        configure_file = next(MAIN_DIRECTORY.glob("configure*"))
        if platform.system() == "Windows":
            subprocess.Popen([str(configure_file)], shell=True)
        else:
            subprocess.Popen([str(configure_file)])

    perform_cleanup(tray_icon)
    os.kill(os.getpid(), signal.SIGTERM)


def on_exit_tray(tray_icon, _item) -> None:
    logger.info("Exit from tray icon")
    perform_cleanup(tray_icon)
    os.kill(os.getpid(), signal.SIGTERM)


def on_reload_renderer(_tray_icon, _item) -> None:
    if _RENDERER_CONTROLLER is None or _RENDERER_SELECTION is None:
        return
    logger.info("Reloading %s renderer safely", _RENDERER_SELECTION.engine)
    try:
        _RENDERER_CONTROLLER.reload(_RENDERER_SELECTION)
    except Exception as exc:
        logger.error("Renderer reload failed: %s", exc)


def install_signal_handlers() -> None:
    atexit.register(on_clean_exit)
    signal.signal(signal.SIGINT, on_signal_caught)
    signal.signal(signal.SIGTERM, on_signal_caught)
    if os.name == "posix":
        signal.signal(signal.SIGQUIT, on_signal_caught)


def create_tray_icon(renderer_label="YAML"):
    disable_legacy_tray = (
        os.environ.get("TURING_DISABLE_PYSTRAY", "").strip().lower()
        in {"1", "true", "yes", "on"}
    )
    if disable_legacy_tray or pystray is None:
        if disable_legacy_tray:
            logger.debug(
                "Legacy pystray icon disabled; GTK StatusNotifierItem is active"
            )
        return None

    try:
        icon = pystray.Icon(
            name="Turing System Monitor",
            title=f"Turing System Monitor — {renderer_label}",
            icon=load_pystray_image(MAIN_DIRECTORY),
            menu=pystray.Menu(
                pystray.MenuItem(text=f"Renderer: {renderer_label}", action=None, enabled=False),
                pystray.MenuItem(text="Reload renderer", action=on_reload_renderer),
                pystray.MenuItem(text="Configure", action=on_configure_tray),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(text="Exit", action=on_exit_tray),
            ),
        )
        if platform.system() != "Darwin":
            icon.run_detached()
            logger.info("Grayscale tray icon has been displayed")
        return icon
    except Exception as exc:
        logger.warning("Tray icon is not supported on your platform: %s", exc)
        return None


def start_schedulers() -> None:
    logger.info("Starting system monitoring")
    import library.stats as stats

    scheduler.CPUPercentage(); time.sleep(0.25)
    scheduler.CPUFrequency(); time.sleep(0.25)
    scheduler.CPULoad(); time.sleep(0.25)
    scheduler.CPUTemperature(); time.sleep(0.25)
    scheduler.CPUFanSpeed(); time.sleep(0.25)
    if stats.Gpu.is_available():
        scheduler.GpuStats(); time.sleep(0.25)
    scheduler.MemoryStats(); time.sleep(0.25)
    scheduler.DiskStats(); time.sleep(0.25)
    scheduler.NetStats(); time.sleep(0.25)
    scheduler.DateStats(); time.sleep(0.25)
    scheduler.SystemUptimeStats(); time.sleep(0.25)
    scheduler.CustomStats(); time.sleep(0.25)
    scheduler.WeatherStats(); time.sleep(0.25)
    scheduler.PingStats(); time.sleep(0.25)


def run_windows_message_loop() -> None:
    def on_win32_ctrl_event(event):
        if event in (
            win32con.CTRL_C_EVENT,
            win32con.CTRL_BREAK_EVENT,
            win32con.CTRL_CLOSE_EVENT,
        ):
            logger.debug("Caught Windows control event %s, exiting", event)
            perform_cleanup()
        return 0

    def on_win32_wm_event(_hWnd, msg, wParam, _lParam):
        logger.debug("Caught Windows window message event %s", msg)
        if msg == win32con.WM_POWERBROADCAST and _DISPLAY is not None:
            if wParam == win32con.PBT_APMSUSPEND:
                logger.info("Computer is going to sleep, display will turn off")
                _DISPLAY.turn_off()
                return
            if wParam == win32con.PBT_APMRESUMEAUTOMATIC:
                logger.info("Computer is resuming from sleep, display will turn on")
                _DISPLAY.turn_on()
                _DISPLAY.display_static_images()
                _DISPLAY.display_static_text()
                return
        request_process_exit(0)

    win32api.SetConsoleCtrlHandler(on_win32_ctrl_event, True)
    hinst = win32api.GetModuleHandle(None)
    wndclass = win32gui.WNDCLASS()
    wndclass.hInstance = hinst
    wndclass.lpszClassName = "turingEventWndClass"
    wndclass.lpfnWndProc = {
        win32con.WM_QUERYENDSESSION: on_win32_wm_event,
        win32con.WM_ENDSESSION: on_win32_wm_event,
        win32con.WM_QUIT: on_win32_wm_event,
        win32con.WM_DESTROY: on_win32_wm_event,
        win32con.WM_CLOSE: on_win32_wm_event,
        win32con.WM_POWERBROADCAST: on_win32_wm_event,
    }
    window_class = win32gui.RegisterClass(wndclass)
    win32gui.CreateWindowEx(
        win32con.WS_EX_LEFT,
        window_class,
        "turingEventWnd",
        0,
        0,
        0,
        win32con.CW_USEDEFAULT,
        win32con.CW_USEDEFAULT,
        0,
        0,
        hinst,
        None,
    )
    while not scheduler.STOPPING:
        win32gui.PumpWaitingMessages()
        time.sleep(0.5)


def run_forever() -> None:
    if _TRAY_ICON and platform.system() == "Darwin":
        from AppKit import NSApp, NSApplicationActivationPolicyProhibited, NSBundle

        info = NSBundle.mainBundle().infoDictionary()
        info["LSUIElement"] = "1"
        NSApp.setActivationPolicy_(NSApplicationActivationPolicyProhibited)
        _TRAY_ICON.run()
    elif platform.system() == "Windows":
        run_windows_message_loop()
    else:
        while not scheduler.STOPPING:
            time.sleep(0.5)


def main() -> int:
    global _DEVICE_LOCK, _DISPLAY, _TRAY_ICON, _RENDERER_CONTROLLER, _RENDERER_SELECTION

    locale.setlocale(locale.LC_ALL, "")
    logger.debug("Using Python %s", sys.version)

    _DEVICE_LOCK = DeviceLock(role="monitor", root=MAIN_DIRECTORY)
    try:
        _DEVICE_LOCK.acquire()
    except DeviceBusyError as exc:
        logger.error("Display runtime is busy: %s", exc.owner.describe())
        print(str(exc), file=sys.stderr)
        return 3

    try:
        try:
            from library.display_detection import auto_configure

            report = auto_configure(MAIN_DIRECTORY)
            logger.info("Display detection: %s", report.message)
            for warning in report.warnings:
                logger.warning("Display detection: %s", warning)
        except Exception as exc:
            logger.warning(
                "Automatic display detection failed; preserving configuration: %s",
                exc,
            )

        install_signal_handlers()
        from library.monitor_renderers import HtmlWorkerRunner, LegacyYamlRunner
        from library.renderer_lifecycle import (
            RendererConfigurationError,
            RendererController,
            RendererSelection,
            select_renderer,
        )

        raw_config = yaml.safe_load((MAIN_DIRECTORY / "config.yaml").read_text(encoding="utf-8")) or {}
        try:
            selection = select_renderer(raw_config, MAIN_DIRECTORY / "res" / "themes")
        except RendererConfigurationError as exc:
            logger.error("Renderer configuration error: %s", exc)
            # Invalid renderer syntax falls back to the unchanged legacy theme.
            # A malformed explicitly selected HTML package is refused instead,
            # because opening another serial session could hide the real error.
            renderer = raw_config.get("renderer")
            if isinstance(renderer, dict) and str(renderer.get("engine", "")).lower() == "html":
                print(str(exc), file=sys.stderr)
                return 2
            selection = RendererSelection("yaml", str(raw_config.get("config", {}).get("THEME") or ""))

        def start_yaml():
            global _DISPLAY
            scheduler.STOPPING = False
            # Imported lazily: HTML-only installations do not load the YAML
            # display/scheduler renderer or construct its LcdComm.
            from library.display import display
            _DISPLAY = display
            logger.info("Initialize YAML display renderer")
            _DISPLAY.initialize_display()
            scheduler.QueueHandler()
            _DISPLAY.start_theme_video()
            _DISPLAY.display_static_images()
            _DISPLAY.display_static_text()
            wait_for_empty_queue(10)
            start_schedulers()

        def yaml_factory(selected):
            return LegacyYamlRunner(
                selected,
                start_callback=start_yaml,
                stop_callback=close_yaml_display,
                wait_callback=lambda: (run_forever() or 0),
            )

        _RENDERER_CONTROLLER = RendererController({
            "yaml": yaml_factory,
            "html": lambda selected: HtmlWorkerRunner(selected, root=MAIN_DIRECTORY),
        })
        _RENDERER_SELECTION = selection
        _TRAY_ICON = create_tray_icon(f"{selection.engine.upper()} — {selection.theme}")
        _RENDERER_CONTROLLER.start(selection)
        if selection.engine == "html":
            return _RENDERER_CONTROLLER.wait()
        run_forever()
        return 0
    except KeyboardInterrupt:
        return 130
    finally:
        perform_cleanup()


if __name__ == "__main__":
    raise SystemExit(main())
