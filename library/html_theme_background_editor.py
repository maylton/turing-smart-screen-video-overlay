# SPDX-License-Identifier: GPL-3.0-or-later
"""Inject background image/video controls into the HTML visual editor."""

from __future__ import annotations

import json
from pathlib import Path

from library.html_background_video import (
    SUPPORTED_FITS,
    SUPPORTED_POSITIONS,
    load_background_media,
    remove_background_media,
    save_background_media,
)


_INSTALLED = False


def _dropdown_value(dropdown, values: tuple[str, ...]) -> str:
    index = int(dropdown.get_selected())
    return values[index] if 0 <= index < len(values) else values[0]


def _set_dropdown(dropdown, values: tuple[str, ...], value: str) -> None:
    try:
        dropdown.set_selected(values.index(value))
    except ValueError:
        dropdown.set_selected(0)


def _clear_preview_script() -> str:
    return """
    (() => {
      document.getElementById('__turing-background-media')?.remove();
      const body = document.body;
      if (body.dataset.turingBackgroundIsolation !== undefined) {
        const value = body.dataset.turingBackgroundIsolation;
        const priority = body.dataset.turingBackgroundIsolationPriority || '';
        if (value) body.style.setProperty('isolation', value, priority);
        else body.style.removeProperty('isolation');
        delete body.dataset.turingBackgroundIsolation;
        delete body.dataset.turingBackgroundIsolationPriority;
      }
      for (const child of [...body.children]) {
        if (child.dataset.turingBackgroundZIndex === undefined) continue;
        const zIndex = child.dataset.turingBackgroundZIndex;
        const zPriority = child.dataset.turingBackgroundZIndexPriority || '';
        const position = child.dataset.turingBackgroundPosition;
        const positionPriority = child.dataset.turingBackgroundPositionPriority || '';
        if (zIndex) child.style.setProperty('z-index', zIndex, zPriority);
        else child.style.removeProperty('z-index');
        if (position) child.style.setProperty('position', position, positionPriority);
        else child.style.removeProperty('position');
        delete child.dataset.turingBackgroundZIndex;
        delete child.dataset.turingBackgroundZIndexPriority;
        delete child.dataset.turingBackgroundPosition;
        delete child.dataset.turingBackgroundPositionPriority;
      }
      return true;
    })()
    """


def _preview_script(
    source_uri: str,
    kind: str,
    fit: str,
    position: str,
    loop: bool,
    start_time: float,
) -> str:
    payload = json.dumps(
        {
            "source": source_uri,
            "kind": kind,
            "fit": fit,
            "position": position,
            "loop": loop,
            "startTime": start_time,
        },
        ensure_ascii=True,
    )
    return f"""
    (() => {{
      const config = {payload};
      const tag = config.kind === 'image' ? 'img' : 'video';
      let media = document.getElementById('__turing-background-media');
      if (media && media.tagName.toLowerCase() !== tag) {{
        media.remove();
        media = null;
      }}
      if (!media) {{
        media = document.createElement(tag);
        media.id = '__turing-background-media';
        media.setAttribute('aria-hidden', 'true');
        document.body.prepend(media);
      }}
      const positions = {{
        center: '50% 50%', 'top-left': '0% 0%', top: '50% 0%',
        'top-right': '100% 0%', left: '0% 50%', right: '100% 50%',
        'bottom-left': '0% 100%', bottom: '50% 100%',
        'bottom-right': '100% 100%'
      }};
      Object.entries({{
        position: 'fixed', inset: '0', width: '480px', height: '480px',
        objectFit: config.fit === 'stretch' ? 'fill' : config.fit,
        objectPosition: positions[config.position] || '50% 50%',
        pointerEvents: 'none', zIndex: '0', background: '#000'
      }}).forEach(([name, value]) => media.style.setProperty(
        name.replace(/[A-Z]/g, character => '-' + character.toLowerCase()),
        value,
        'important'
      ));
      const body = document.body;
      if (body.dataset.turingBackgroundIsolation === undefined) {{
        body.dataset.turingBackgroundIsolation = body.style.getPropertyValue('isolation');
        body.dataset.turingBackgroundIsolationPriority =
          body.style.getPropertyPriority('isolation');
      }}
      body.style.setProperty('isolation', 'isolate', 'important');
      for (const child of [...body.children]) {{
        if (child === media) continue;
        if (child.dataset.turingBackgroundZIndex === undefined) {{
          child.dataset.turingBackgroundZIndex = child.style.getPropertyValue('z-index');
          child.dataset.turingBackgroundZIndexPriority =
            child.style.getPropertyPriority('z-index');
          child.dataset.turingBackgroundPosition =
            child.style.getPropertyValue('position');
          child.dataset.turingBackgroundPositionPriority =
            child.style.getPropertyPriority('position');
        }}
        if (getComputedStyle(child).position === 'static')
          child.style.setProperty('position', 'relative', 'important');
        child.style.setProperty('z-index', '1', 'important');
      }}
      if (media.src !== config.source) media.src = config.source;
      if (config.kind === 'video') {{
        media.muted = true;
        media.loop = Boolean(config.loop);
        media.autoplay = true;
        media.playsInline = true;
        const seek = () => {{
          if (Number.isFinite(config.startTime) && config.startTime > 0) {{
            try {{ media.currentTime = config.startTime; }} catch (_error) {{}}
          }}
          media.play().catch(() => {{}});
        }};
        if (media.readyState >= 1) seek();
        else media.addEventListener('loadedmetadata', seek, {{once: true}});
      }}
      return true;
    }})()
    """


def _attach_background_page(window, Gtk, Gio) -> None:
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
            "Use uma imagem estática ou um vídeo como fundo. A fonte é copiada "
            "para assets/ e mesclada com imagens e animações do HTML ao gerar o "
            "MP4. Somente os elementos data-turing-overlay ficam ao vivo."
        ),
        xalign=0,
        wrap=True,
    )
    description.add_css_class("dim-label")
    page.append(description)

    file_label = Gtk.Label(label="Nenhum fundo selecionado", xalign=0, wrap=True)
    file_label.set_selectable(True)
    page.append(file_label)

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
    start_label = Gtk.Label(label="Início do vídeo (segundos)", xalign=0)
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

    def refresh_preview(*_args) -> None:
        config = current_config()
        backend = getattr(window, "backend", None)
        if backend is None:
            return
        if config is None:
            backend.evaluate(_clear_preview_script())
            return
        try:
            source = config.source_file(window.manifest.root)
        except Exception:
            return
        if source.is_file():
            backend.evaluate(
                _preview_script(
                    source.as_uri(),
                    config.kind,
                    _dropdown_value(fit_dropdown, fit_values),
                    _dropdown_value(position_dropdown, position_values),
                    loop_check.get_active(),
                    start_spin.get_value(),
                )
            )

    def select_response(dialog, response, kind: str) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            selected = dialog.get_file()
            path = Path(selected.get_path()) if selected and selected.get_path() else None
            if path is not None:
                window._turing_background_selected_source = path
                window._turing_background_selected_kind = kind
                label = "imagem" if kind == "image" else "vídeo"
                file_label.set_text(f"Nova {label}: {path.name}")
                sync_video_controls(kind)
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
            for mime in (
                "image/png",
                "image/jpeg",
                "image/webp",
                "image/bmp",
            ):
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
        dialog.connect("response", lambda item, response: select_response(item, response, kind))
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
            update_controls()
            refresh_preview()
            status = getattr(window, "status_label", None)
            if status is not None:
                status.set_text("Fundo salvo; o vídeo nativo precisa ser reconstruído")
            editor_build = getattr(window, "build_button", None)
            if editor_build is not None:
                editor_build.set_sensitive(True)
            toast("Fundo do tema salvo")
            if build:
                saver = getattr(window, "_save", None)
                if callable(saver):
                    saver(True)
                else:
                    starter = getattr(window, "_start_build", None)
                    if callable(starter):
                        starter()
        except Exception as exc:
            status = getattr(window, "status_label", None)
            if status is not None:
                status.set_text(f"Não foi possível salvar o fundo: {exc}")
            toast("Falha ao salvar o fundo")

    def remove(*_args) -> None:
        try:
            window.manifest = remove_background_media(window.manifest)
            window._turing_background_selected_source = None
            window._turing_background_selected_kind = None
            update_controls()
            refresh_preview()
            status = getattr(window, "status_label", None)
            if status is not None:
                status.set_text("Fundo removido; reconstrua o vídeo nativo")
            toast("Fundo do tema removido")
        except Exception as exc:
            status = getattr(window, "status_label", None)
            if status is not None:
                status.set_text(f"Não foi possível remover o fundo: {exc}")
            toast("Falha ao remover o fundo")

    choose_image_button.connect("clicked", lambda *_args: choose_source("image"))
    choose_video_button.connect("clicked", lambda *_args: choose_source("video"))
    save_button.connect("clicked", lambda *_args: persist(build=False))
    build_button.connect("clicked", lambda *_args: persist(build=True))
    remove_button.connect("clicked", remove)
    fit_dropdown.connect("notify::selected", refresh_preview)
    position_dropdown.connect("notify::selected", refresh_preview)
    loop_check.connect("toggled", refresh_preview)
    start_spin.connect("value-changed", refresh_preview)

    backend = getattr(window, "backend", None)
    if backend is not None:
        def loaded(_view, event) -> None:
            finished = getattr(backend.WebKit.LoadEvent, "FINISHED", None)
            if finished is None or event == finished:
                refresh_preview()
        backend.view.connect("load-changed", loaded)

    update_controls()
    refresh_preview()


def install_background_editor_hook() -> None:
    """Attach the page after the existing editor window enters the GTK loop."""
    global _INSTALLED
    if _INSTALLED:
        return
    _INSTALLED = True
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gio, GLib, Gtk
    except Exception:
        return

    def attach_when_ready() -> bool:
        try:
            model = Gtk.Window.get_toplevels()
            for index in range(model.get_n_items()):
                window = model.get_item(index)
                if window.__class__.__name__ == "HtmlThemeEditorWindow":
                    _attach_background_page(window, Gtk, Gio)
        except Exception:
            return True
        return True

    GLib.timeout_add(120, attach_when_ready)
