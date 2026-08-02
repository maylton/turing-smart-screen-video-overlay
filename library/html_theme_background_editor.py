# SPDX-License-Identifier: GPL-3.0-or-later
"""Background image/video controls for the HTML visual editor.

The editor preview deliberately never creates an HTML media element. Video
sources are represented by one PNG frame extracted with FFmpeg, keeping
GStreamer completely outside WebKitGTK.
"""

from __future__ import annotations

import base64
import json
import os
import tempfile
from pathlib import Path
from typing import Callable

from library.html_background_video import (
    SUPPORTED_FITS,
    SUPPORTED_POSITIONS,
    extract_preview_frame,
    load_background_media,
    remove_background_media,
    save_background_media,
)


_INSTALLED = False
_IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}


def _dropdown_value(dropdown, values: tuple[str, ...]) -> str:
    index = int(dropdown.get_selected())
    return values[index] if 0 <= index < len(values) else values[0]


def _set_dropdown(dropdown, values: tuple[str, ...], value: str) -> None:
    try:
        dropdown.set_selected(values.index(value))
    except ValueError:
        dropdown.set_selected(0)


def _bytes_data_uri(payload: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _preview_data_uri(
    source: Path,
    kind: str,
    *,
    timestamp: float = 0.0,
    extractor: Callable[..., None] | None = None,
) -> str:
    """Return an image data URI for an image or one extracted video frame."""
    source = Path(source).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"arquivo de fundo não encontrado: {source}")

    if kind == "image":
        mime_type = _IMAGE_MIME_TYPES.get(source.suffix.lower())
        if mime_type is None:
            raise ValueError(f"formato de imagem não suportado: {source.suffix}")
        return _bytes_data_uri(source.read_bytes(), mime_type)

    if kind != "video":
        raise ValueError(f"tipo de fundo inválido: {kind}")

    extractor = extract_preview_frame if extractor is None else extractor
    descriptor, filename = tempfile.mkstemp(prefix="turing-bg-preview-", suffix=".png")
    os.close(descriptor)
    destination = Path(filename)
    try:
        extractor(source, destination, timestamp=max(0.0, float(timestamp)))
        if not destination.is_file() or destination.stat().st_size <= 0:
            raise RuntimeError("FFmpeg não produziu o quadro de prévia")
        return _bytes_data_uri(destination.read_bytes(), "image/png")
    finally:
        destination.unlink(missing_ok=True)


def _clear_preview_script() -> str:
    return """
    (() => {
      document.getElementById('__turing-background-preview')?.remove();
      const body = document.body;
      const state = window.__turingBackgroundPreviewState;
      if (state && body) {
        if (state.isolationValue)
          body.style.setProperty('isolation', state.isolationValue, state.isolationPriority);
        else
          body.style.removeProperty('isolation');
      }
      delete window.__turingBackgroundPreviewState;
    })();
    """


def _preview_image_script(
    data_uri: str,
    fit: str,
    position: str,
) -> str:
    """Build a WebKit-safe preview script using only an inert image element."""
    payload = json.dumps(
        {
            "source": data_uri,
            "fit": fit,
            "position": position,
        },
        ensure_ascii=True,
    )
    return f"""
    (() => {{
      const config = {payload};
      const positions = {{
        center: '50% 50%', 'top-left': '0% 0%', top: '50% 0%',
        'top-right': '100% 0%', left: '0% 50%', right: '100% 50%',
        'bottom-left': '0% 100%', bottom: '50% 100%',
        'bottom-right': '100% 100%'
      }};
      const body = document.body;
      if (!body) return;
      if (!window.__turingBackgroundPreviewState) {{
        window.__turingBackgroundPreviewState = {{
          isolationValue: body.style.getPropertyValue('isolation'),
          isolationPriority: body.style.getPropertyPriority('isolation')
        }};
      }}
      body.style.setProperty('isolation', 'isolate', 'important');

      let image = document.getElementById('__turing-background-preview');
      if (!image) {{
        image = document.createElement('img');
        image.id = '__turing-background-preview';
        image.setAttribute('aria-hidden', 'true');
        image.setAttribute('draggable', 'false');
        body.prepend(image);
      }}
      Object.entries({{
        position: 'fixed', inset: '0', width: '480px', height: '480px',
        objectFit: config.fit === 'stretch' ? 'fill' : config.fit,
        objectPosition: positions[config.position] || '50% 50%',
        pointerEvents: 'none', userSelect: 'none', zIndex: '-1'
      }}).forEach(([name, value]) => image.style.setProperty(
        name.replace(/[A-Z]/g, character => '-' + character.toLowerCase()),
        value,
        'important'
      ));
      if (image.src !== config.source) image.src = config.source;
    }})();
    """


def _attach_background_page(window, Gtk, GLib) -> None:
    if getattr(window, "_turing_background_page_attached", False):
        return
    stack = getattr(window, "inspector_stack", None)
    manifest = getattr(window, "manifest", None)
    if stack is None or manifest is None:
        return

    window._turing_background_page_attached = True
    window._turing_background_selected_source = None
    window._turing_background_selected_kind = None

    scroll = Gtk.ScrolledWindow()
    scroll.set_hexpand(True)
    scroll.set_vexpand(True)
    scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    page = Gtk.Box(
        orientation=Gtk.Orientation.VERTICAL,
        spacing=14,
        margin_top=8,
        margin_bottom=8,
        margin_start=4,
        margin_end=4,
    )
    scroll.set_child(page)
    stack.add_titled(scroll, "background", "Fundo")

    description = Gtk.Label(
        label=(
            "Use uma imagem ou vídeo como fundo do MP4 compilado. Vídeos são "
            "mostrados nesta tela por um quadro estático para manter o WebKit "
            "independente do GStreamer."
        ),
        xalign=0,
        wrap=True,
    )
    description.add_css_class("dim-label")
    page.append(description)

    file_label = Gtk.Label(label="Nenhum fundo selecionado", xalign=0, wrap=True)
    file_label.set_selectable(True)
    page.append(file_label)

    preview_label = Gtk.Label(label="Sem prévia de fundo", xalign=0, wrap=True)
    preview_label.add_css_class("dim-label")
    page.append(preview_label)

    source_actions = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
    choose_image_button = Gtk.Button(label="Adicionar ou substituir imagem…")
    choose_video_button = Gtk.Button(label="Adicionar ou substituir vídeo…")
    source_actions.append(choose_image_button)
    source_actions.append(choose_video_button)
    page.append(source_actions)

    fit_values = tuple(SUPPORTED_FITS)
    fit_dropdown = Gtk.DropDown.new_from_strings(
        ("Preencher (cover)", "Conter", "Esticar")
    )
    page.append(Gtk.Label(label="Ajuste", xalign=0))
    page.append(fit_dropdown)

    position_values = tuple(SUPPORTED_POSITIONS)
    position_dropdown = Gtk.DropDown.new_from_strings(
        (
            "Centro",
            "Superior esquerdo",
            "Superior",
            "Superior direito",
            "Esquerda",
            "Direita",
            "Inferior esquerdo",
            "Inferior",
            "Inferior direito",
        )
    )
    page.append(Gtk.Label(label="Posição", xalign=0))
    page.append(position_dropdown)

    loop_check = Gtk.CheckButton(label="Repetir o vídeo até o fim do tema")
    loop_check.set_active(True)
    page.append(loop_check)

    adjustment = Gtk.Adjustment(
        value=0.0,
        lower=0.0,
        upper=3600.0,
        step_increment=0.1,
        page_increment=1.0,
        page_size=0.0,
    )
    start_spin = Gtk.SpinButton(adjustment=adjustment, digits=1)
    start_label = Gtk.Label(label="Quadro inicial do vídeo (segundos)", xalign=0)
    page.append(start_label)
    page.append(start_spin)

    actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
    save_button = Gtk.Button(label="Salvar fundo")
    build_button = Gtk.Button(label="Salvar fundo e gerar vídeo")
    build_button.add_css_class("suggested-action")
    remove_button = Gtk.Button(label="Remover fundo")
    remove_button.add_css_class("destructive-action")
    actions.append(save_button)
    actions.append(build_button)
    page.append(actions)
    page.append(remove_button)

    state = {
        "updating": False,
        "preview_key": None,
        "preview_uri": None,
        "timer": 0,
        "force": False,
    }

    def toast(message: str) -> None:
        callback = getattr(window, "_toast", None)
        if callable(callback):
            callback(message)

    def current_config():
        try:
            return load_background_media(window.manifest, require_file=False)
        except Exception:
            return None

    def selected_kind() -> str | None:
        value = getattr(window, "_turing_background_selected_kind", None)
        if value in {"image", "video"}:
            return value
        config = current_config()
        return config.kind if config is not None else None

    def sync_video_controls(kind: str | None) -> None:
        enabled = kind == "video"
        loop_check.set_sensitive(enabled)
        start_spin.set_sensitive(enabled)
        start_label.set_sensitive(enabled)

    def update_controls() -> None:
        state["updating"] = True
        try:
            config = current_config()
            if config is None:
                file_label.set_text("Nenhum fundo selecionado")
                _set_dropdown(fit_dropdown, fit_values, "cover")
                _set_dropdown(position_dropdown, position_values, "center")
                loop_check.set_active(True)
                start_spin.set_value(0.0)
                sync_video_controls(selected_kind())
                return
            label = "Imagem" if config.is_image else "Vídeo"
            file_label.set_text(f"{label}: {config.source_path}")
            _set_dropdown(fit_dropdown, fit_values, config.fit)
            _set_dropdown(position_dropdown, position_values, config.position)
            loop_check.set_active(config.loop)
            start_spin.set_value(config.start_time)
            sync_video_controls(config.kind)
        finally:
            state["updating"] = False

    def preview_source() -> tuple[Path, str] | None:
        selected = getattr(window, "_turing_background_selected_source", None)
        kind = getattr(window, "_turing_background_selected_kind", None)
        if selected is not None and kind in {"image", "video"}:
            return Path(selected), kind
        config = current_config()
        if config is None:
            return None
        return config.source_file(window.manifest.root), config.kind

    def refresh_preview(*, force: bool = False) -> None:
        backend = getattr(window, "backend", None)
        if backend is None:
            return
        source_info = preview_source()
        if source_info is None:
            state["preview_key"] = None
            state["preview_uri"] = None
            backend.evaluate(_clear_preview_script())
            preview_label.set_text("Sem prévia de fundo")
            return

        source, kind = source_info
        try:
            modified = source.stat().st_mtime_ns
            timestamp = start_spin.get_value() if kind == "video" else 0.0
            key = (str(source.resolve()), modified, kind, round(timestamp, 3))
            if force or state["preview_key"] != key or not state["preview_uri"]:
                state["preview_uri"] = _preview_data_uri(
                    source,
                    kind,
                    timestamp=timestamp,
                )
                state["preview_key"] = key
            backend.evaluate(
                _preview_image_script(
                    str(state["preview_uri"]),
                    _dropdown_value(fit_dropdown, fit_values),
                    _dropdown_value(position_dropdown, position_values),
                )
            )
            preview_label.set_text(
                "Prévia estática do vídeo" if kind == "video" else "Prévia da imagem"
            )
        except Exception as exc:
            backend.evaluate(_clear_preview_script())
            preview_label.set_text(f"Não foi possível gerar a prévia: {exc}")

    def run_scheduled_preview() -> bool:
        force = bool(state["force"])
        state["force"] = False
        state["timer"] = 0
        refresh_preview(force=force)
        return False

    def schedule_preview(*_args, force: bool = False) -> None:
        if state["updating"]:
            return
        state["force"] = bool(state["force"] or force)
        timer = int(state["timer"] or 0)
        if timer:
            GLib.source_remove(timer)
        state["timer"] = GLib.timeout_add(180, run_scheduled_preview)

    def select_response(dialog, response, kind: str) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            selected = dialog.get_file()
            path = Path(selected.get_path()) if selected and selected.get_path() else None
            if path is not None:
                window._turing_background_selected_source = path
                window._turing_background_selected_kind = kind
                state["preview_key"] = None
                state["preview_uri"] = None
                label = "imagem" if kind == "image" else "vídeo"
                file_label.set_text(f"Nova {label}: {path.name}")
                sync_video_controls(kind)
                schedule_preview(force=True)
        dialog.destroy()

    def choose_source(kind: str) -> None:
        label = "imagem" if kind == "image" else "vídeo"
        dialog = Gtk.FileChooserNative.new(
            f"Selecionar {label} de fundo",
            window,
            Gtk.FileChooserAction.OPEN,
            "Selecionar",
            "Cancelar",
        )
        media_filter = Gtk.FileFilter()
        if kind == "image":
            media_filter.set_name("Imagens")
            for mime in ("image/png", "image/jpeg", "image/webp", "image/bmp"):
                media_filter.add_mime_type(mime)
        else:
            media_filter.set_name("Vídeos e GIFs")
            for mime in (
                "video/mp4",
                "video/quicktime",
                "video/x-matroska",
                "video/webm",
                "video/x-msvideo",
                "image/gif",
            ):
                media_filter.add_mime_type(mime)
        dialog.add_filter(media_filter)
        dialog.connect(
            "response",
            lambda item, response: select_response(item, response, kind),
        )
        dialog.show()

    def persist(*_args, build: bool = False) -> None:
        try:
            kind = selected_kind()
            window.manifest = save_background_media(
                window.manifest,
                source=window._turing_background_selected_source,
                media_kind=kind,
                fit=_dropdown_value(fit_dropdown, fit_values),
                position=_dropdown_value(position_dropdown, position_values),
                loop=loop_check.get_active(),
                start_time=start_spin.get_value(),
            )
            window._turing_background_selected_source = None
            window._turing_background_selected_kind = None
            state["preview_key"] = None
            state["preview_uri"] = None
            update_controls()
            schedule_preview(force=True)
            window.status_label.set_text(
                "Fundo salvo; o vídeo nativo precisa ser reconstruído"
            )
            window.build_button.set_sensitive(True)
            toast("Fundo do tema salvo")
            if build:
                window._save(True)
        except Exception as exc:
            window.status_label.set_text(f"Não foi possível salvar o fundo: {exc}")
            toast("Falha ao salvar o fundo")

    def remove(*_args) -> None:
        try:
            window.manifest = remove_background_media(window.manifest)
            window._turing_background_selected_source = None
            window._turing_background_selected_kind = None
            state["preview_key"] = None
            state["preview_uri"] = None
            update_controls()
            refresh_preview(force=True)
            window.status_label.set_text("Fundo removido; reconstrua o vídeo nativo")
            toast("Fundo do tema removido")
        except Exception as exc:
            window.status_label.set_text(f"Não foi possível remover o fundo: {exc}")
            toast("Falha ao remover o fundo")

    choose_image_button.connect("clicked", lambda *_args: choose_source("image"))
    choose_video_button.connect("clicked", lambda *_args: choose_source("video"))
    save_button.connect("clicked", lambda *_args: persist(build=False))
    build_button.connect("clicked", lambda *_args: persist(build=True))
    remove_button.connect("clicked", remove)
    fit_dropdown.connect("notify::selected", schedule_preview)
    position_dropdown.connect("notify::selected", schedule_preview)
    start_spin.connect("value-changed", schedule_preview)

    update_controls()
    schedule_preview(force=True)


def install_background_editor_hook() -> None:
    """Attach the page only after the original editor is fully operational."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import GLib, Gtk
    except Exception as exc:
        print(f"A aba Fundo não pôde carregar GTK: {exc}")
        return

    attempts = 0

    def attach_when_ready() -> bool:
        nonlocal attempts
        attempts += 1
        application = Gtk.Application.get_default()
        if application is not None:
            for window in application.get_windows():
                if window.__class__.__name__ != "HtmlThemeEditorWindow":
                    continue
                if not getattr(window, "_loaded_once", False):
                    continue
                _attach_background_page(window, Gtk, GLib)
                if getattr(window, "_turing_background_page_attached", False):
                    print(
                        "Aba Fundo anexada após o carregamento completo do editor.",
                        flush=True,
                    )
                    return False
        if attempts >= 600:
            print(
                "A aba Fundo não foi anexada porque o editor não concluiu o carregamento.",
                flush=True,
            )
            return False
        return True

    GLib.timeout_add(50, attach_when_ready)
