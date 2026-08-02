# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve the dependency-complete Python used by project subprocesses."""

from __future__ import annotations

import builtins
import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from types import MethodType
from urllib.parse import unquote


RUNTIME_PYTHON_ENV = "TURING_SMART_SCREEN_PYTHON"
DOM_INSPECT_TITLE_PREFIX = "turing-editor-inspect:"
_BUILD_CLASS_HOOK_INSTALLED = False
_BUILD_CLASS_HOOK_ORIGINAL = None


def _javascript_json_script(script: str) -> str:
    """Wrap a JavaScript expression so WebKit only returns a string value."""
    expression = str(script or "").strip()
    if expression.endswith(";"):
        expression = expression[:-1].rstrip()
    if not expression:
        raise ValueError("JavaScript expression cannot be empty")
    return f"JSON.stringify(({expression}))"


def _decode_javascript_json(value):
    """Decode a JSON string returned as a JSC.Value-like object."""
    if value is None:
        raise RuntimeError("WebKit returned no JavaScript result")
    text = value.to_string()
    if text is None:
        raise RuntimeError("WebKit returned an empty JavaScript string")
    return json.loads(str(text))


def _evaluate_json_bridge(self, script: str, callback) -> None:
    """Legacy JSON bridge retained for compatibility tests.

    DOM inspection no longer uses this path because some WebKitGTK/PyGObject
    combinations fail while marshalling the JSC.Value returned by
    evaluate_javascript_finish(), before Python can call to_string().
    """
    wrapped_script = _javascript_json_script(script)
    self._turing_json_bridge_calls = (
        int(getattr(self, "_turing_json_bridge_calls", 0)) + 1
    )

    def finished(view, result, _user_data=None):
        try:
            value = view.evaluate_javascript_finish(result)
            callback(_decode_javascript_json(value), None)
        except Exception as exc:
            callback(None, exc)

    self.backend.view.evaluate_javascript(
        wrapped_script,
        -1,
        None,
        None,
        None,
        finished,
        None,
    )


def _patch_html_editor_class(editor_class) -> bool:
    """Install the legacy JSON bridge on an HTML editor class exactly once."""
    if editor_class is None:
        return False
    if getattr(editor_class, "_turing_json_bridge_installed", False):
        return True
    editor_class._evaluate_json = _evaluate_json_bridge
    editor_class._turing_json_bridge_installed = True
    return True


def _patch_html_editor_instance(window) -> bool:
    """Bind the legacy bridge directly to a live window."""
    if window is None:
        return False
    window._evaluate_json = MethodType(_evaluate_json_bridge, window)
    window._turing_json_bridge_instance_installed = True
    return True


def _dom_inspection_script(element_ids) -> str:
    """Build a one-way DOM inspection script using the proven title channel."""
    ids = json.dumps(list(element_ids), ensure_ascii=False)
    prefix = json.dumps(DOM_INSPECT_TITLE_PREFIX)
    return f"""
    (() => {{
      const ids = {ids};
      const payload = ids.map(id => {{
        const element = document.getElementById(id);
        if (!element) return {{id, missing: true}};
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return {{
          id,
          x: Math.round(rect.x),
          y: Math.round(rect.y),
          width: Math.max(1, Math.round(rect.width)),
          height: Math.max(1, Math.round(rect.height)),
          fontSize: Math.max(6, Math.round(parseFloat(style.fontSize) || 16)),
          color: style.color,
          fontWeight: style.fontWeight,
          textAlign: style.textAlign,
          opacity: Math.round((parseFloat(style.opacity) || 0) * 100),
          zIndex: style.zIndex,
          visible: style.display !== 'none',
          componentType: element.dataset.turingComponent || '',
          generatedWidget: element.hasAttribute('data-turing-generated-widget'),
          binding: element.dataset.turingBinding || '',
          formatter: element.dataset.turingFormat || '',
          sample: element.dataset.turingKind === 'bar'
            ? (element.getAttribute('aria-valuenow') || '50')
            : (element.textContent.trim() || '--'),
          elementKind: element.dataset.turingKind || (
            element.textContent.trim() === '' && rect.width >= rect.height * 2
              ? 'bar'
              : 'text'
          )
        }};
      }});
      const message = {{nonce: performance.now(), payload}};
      document.title = {prefix} + encodeURIComponent(JSON.stringify(message));
    }})();
    """


def _install_title_dom_bridge(window) -> bool:
    """Route DOM inspection through document.title, never a JS return value."""
    if window is None:
        return False
    if getattr(window, "_turing_title_dom_bridge_installed", False):
        return True

    view = window.backend.view

    def receive_title(_view, _param) -> None:
        title = str(_view.get_title() or "")
        if not title.startswith(DOM_INSPECT_TITLE_PREFIX):
            return
        encoded = title[len(DOM_INSPECT_TITLE_PREFIX) :]
        try:
            message = json.loads(unquote(encoded))
            payload = message.get("payload") if isinstance(message, dict) else message
            if not isinstance(payload, list):
                raise RuntimeError("DOM inspection returned an invalid payload")
            window._receive_dom_styles(payload, None)
        except Exception as exc:
            window._receive_dom_styles(None, exc)

    def query_dom_styles(self) -> bool:
        self.backend.evaluate(_dom_inspection_script(self.element_ids))
        return False

    view.connect("notify::title", receive_title)
    window._query_dom_styles = MethodType(query_dom_styles, window)
    window._turing_title_dom_bridge_installed = True
    return True


def _restore_build_class_hook() -> None:
    global _BUILD_CLASS_HOOK_INSTALLED, _BUILD_CLASS_HOOK_ORIGINAL
    original = _BUILD_CLASS_HOOK_ORIGINAL
    if original is not None:
        builtins.__build_class__ = original
    _BUILD_CLASS_HOOK_ORIGINAL = None
    _BUILD_CLASS_HOOK_INSTALLED = False


def _install_html_editor_build_class_hook(*, target_module: str = "__main__") -> bool:
    """Patch HtmlThemeEditorWindow synchronously when Python creates the class."""
    global _BUILD_CLASS_HOOK_INSTALLED, _BUILD_CLASS_HOOK_ORIGINAL
    if _BUILD_CLASS_HOOK_INSTALLED:
        return True

    original = builtins.__build_class__
    _BUILD_CLASS_HOOK_ORIGINAL = original

    def guarded_build_class(func, name, *bases, **kwargs):
        editor_class = original(func, name, *bases, **kwargs)
        if (
            name == "HtmlThemeEditorWindow"
            and getattr(editor_class, "__module__", "") == target_module
        ):
            try:
                _patch_html_editor_class(editor_class)
            finally:
                _restore_build_class_hook()
        return editor_class

    builtins.__build_class__ = guarded_build_class
    _BUILD_CLASS_HOOK_INSTALLED = True
    return True


def _install_html_editor_class_patch() -> bool:
    """Fallback patch for launchers that import the editor as a module."""
    for module_name in ("__main__", "html_theme_editor_gtk"):
        module = sys.modules.get(module_name)
        editor_class = getattr(module, "HtmlThemeEditorWindow", None)
        if editor_class is not None:
            _patch_html_editor_class(editor_class)
            return False
    return True


def _install_html_editor_extensions() -> None:
    """Attach editor extensions after the HTML editor window is fully built."""
    if Path(sys.argv[0]).name != "html-theme-editor-gtk.py":
        return

    _install_html_editor_build_class_hook()

    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gio, GLib, Gtk
        from library.html_theme_background_editor import _attach_background_page
    except Exception as exc:
        print(f"Erro ao preparar extensões do editor HTML: {exc}", file=sys.stderr)
        return

    GLib.idle_add(_install_html_editor_class_patch)

    attempts = 0

    def attach_when_ready() -> bool:
        nonlocal attempts
        attempts += 1
        try:
            _install_html_editor_class_patch()
            application = Gtk.Application.get_default()
            if application is None:
                return attempts < 150
            for window in application.get_windows():
                if window.__class__.__name__ != "HtmlThemeEditorWindow":
                    continue
                if getattr(window, "inspector_stack", None) is None:
                    return attempts < 150

                _patch_html_editor_class(window.__class__)
                _patch_html_editor_instance(window)
                _install_title_dom_bridge(window)
                _attach_background_page(window, Gtk, Gio)
                if not getattr(window, "_turing_background_page_attached", False):
                    raise RuntimeError("a página Fundo não foi anexada ao inspector_stack")

                if not getattr(window, "_turing_title_dom_retry_scheduled", False):
                    window._turing_title_dom_retry_scheduled = True

                    def retry_dom_inspection() -> bool:
                        try:
                            _install_title_dom_bridge(window)
                            status = getattr(window, "status_label", None)
                            if status is not None:
                                status.set_text("Reinspecionando elementos…")
                            window._query_dom_styles()
                            print(
                                "Inspeção DOM via document.title instalada; "
                                "nova inspeção solicitada.",
                                file=sys.stderr,
                                flush=True,
                            )
                        except Exception as exc:
                            print(
                                f"Erro ao repetir inspeção do editor HTML: {exc}",
                                file=sys.stderr,
                                flush=True,
                            )
                        return False

                    GLib.idle_add(retry_dom_inspection)
                return False
        except Exception as exc:
            print(f"Erro ao carregar extensões do editor HTML: {exc}", file=sys.stderr)
            return False
        return attempts < 150

    GLib.timeout_add(25, attach_when_ready)


def _executable(path: Path) -> bool:
    return path.is_file() and os.access(path, os.X_OK)


def resolve_project_python(
    root: Path | str,
    *,
    current: str | None = None,
    environment: Mapping[str, str] | None = None,
    user_data_home: Path | str | None = None,
) -> str:
    """Prefer project or installed venvs before the current Python.

    GTK launchers normally run with the system interpreter so PyGObject is
    available. Monitor and editor subprocesses still need the application's
    pip dependencies, which live in a venv. Source-tree runs may reuse the
    per-user installation venv when no local development venv exists.
    """
    root = Path(root).expanduser()
    environment = os.environ if environment is None else environment
    current = sys.executable if current is None else current

    override = str(environment.get(RUNTIME_PYTHON_ENV, "")).strip()
    if override:
        candidate = Path(override).expanduser()
        if _executable(candidate):
            return str(candidate)

    if user_data_home is None:
        configured_data_home = str(environment.get("XDG_DATA_HOME", "")).strip()
        user_data_home = (
            Path(configured_data_home).expanduser()
            if configured_data_home
            else Path.home() / ".local" / "share"
        )
    else:
        user_data_home = Path(user_data_home).expanduser()

    candidates = (
        root / "venv" / "bin" / "python3",
        root / ".venv" / "bin" / "python3",
        root / "venv" / "Scripts" / "python.exe",
        root / ".venv" / "Scripts" / "python.exe",
        user_data_home / "turing-smart-screen" / "venv" / "bin" / "python3",
    )
    for candidate in candidates:
        if _executable(candidate):
            return str(candidate)
    return current


_install_html_editor_extensions()
