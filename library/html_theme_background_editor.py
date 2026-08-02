# SPDX-License-Identifier: GPL-3.0-or-later
"""Inject background-video controls into the existing HTML visual editor."""

from __future__ import annotations

import json
from pathlib import Path

from library.html_background_video import (
    SUPPORTED_FITS,
    SUPPORTED_POSITIONS,
    load_background_video,
    remove_background_video,
    save_background_video,
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


def _preview_script(source_uri: str, fit: str, position: str) -> str:
    payload = json.dumps(
        {"source": source_uri, "fit": fit, "position": position},
        ensure_ascii=True,
    )
    return f"""
    (() => {{
      const config = {payload};
      let video = document.getElementById('__turing-background-video');
      if (!video) {{
        video = document.createElement('video');
        video.id = '__turing-background-video';
        video.muted = true;
        video.loop = true;
        video.autoplay = true;
        video.playsInline = true;
        video.setAttribute('aria-hidden', 'true');
        document.body.prepend(video);
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
        pointerEvents: 'none', zIndex: '-2147483647',
        background: '#000'
      }}).forEach(([name, value]) => video.style.setProperty(
        name.replace(/[A-Z]/g, character => '-' + character.toLowerCase()),
        value,
        'important'
      ));
      if (video.src !== config.source) video.src = config.source;
      video.play().catch(() => {{}});
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
            "O vídeo escolhido é mantido como fonte em assets/. Ao gerar o vídeo "
            "nativo, ele é mesclado com imagens e animações do HTML. Somente os "
            "elementos data-turing-overlay ficam para o aplicativo renderizar."
        ),
        xalign=0,
        wrap=True,
    )
    description.add_css_class("dim-label")
    page.append(description)

    file_label = Gtk.Label(label="Nenhum vídeo selecionado", xalign=0, wrap=True)
    file_label.set_selectable(True)
    page.append(file_label)

    choose_button = Gtk.Button(label="Selecionar vídeo de fundo…")
    page.append(choose_button)

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
    page.append(Gtk.Label(label="Início do vídeo (segundos)", xalign=0))
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
            return load_background_video(window.manifest, require_file=False)
        except Exception:
            return None

    def update_controls() -> None:
        config = current_config()
        if config is None:
            file_label.set_text("Nenhum vídeo selecionado")
            _set_dropdown(fit_dropdown, fit_values, "cover")
            _set_dropdown(position_dropdown, position_values, "center")
            loop_check.set_active(True)
            start_spin.set_value(0.0)
            return
        file_label.set_text(config.source_path)
        _set_dropdown(fit_dropdown, fit_values, config.fit)
        _set_dropdown(position_dropdown, position_values, config.position)
        loop_check.set_active(config.loop)
        start_spin.set_value(config.start_time)

    def refresh_preview(*_args) -> None:
        config = current_config()
        if config is None:
            backend = getattr(window, "backend", None)
            if backend is not None:
                backend.evaluate(
                    "document.getElementById('__turing-background-video')?.remove();"
                )
            return
        try:
            source = config.source_file(window.manifest.root)
        except Exception:
            return
        backend = getattr(window, "backend", None)
        if backend is not None and source.is_file():
            backend.evaluate(
                _preview_script(source.as_uri(), config.fit, config.position)
            )

    def select_response(dialog, response) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            selected = dialog.get_file()
            path = Path(selected.get_path()) if selected and selected.get_path() else None
            if path is not None:
                window._turing_background_selected_source = path
                file_label.set_text(f"Selecionado: {path.name}")
        dialog.destroy()

    def choose_source(*_args) -> None:
        dialog = Gtk.FileChooserNative.new(
            "Selecionar vídeo de fundo",
            window,
            Gtk.FileChooserAction.OPEN,
            "Selecionar",
            "Cancelar",
        )
        media_filter = Gtk.FileFilter()
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
        dialog.connect("response", select_response)
        dialog.show()

    def persist(*_args, build: bool = False) -> None:
        try:
            window.manifest = save_background_video(
                window.manifest,
                source=window._turing_background_selected_source,
                fit=_dropdown_value(fit_dropdown, fit_values),
                position=_dropdown_value(position_dropdown, position_values),
                loop=loop_check.get_active(),
                start_time=start_spin.get_value(),
            )
            window._turing_background_selected_source = None
            update_controls()
            refresh_preview()
            status = getattr(window, "status_label", None)
            if status is not None:
                status.set_text("Fundo salvo; o vídeo nativo precisa ser reconstruído")
            editor_build = getattr(window, "build_button", None)
            if editor_build is not None:
                editor_build.set_sensitive(True)
            toast("Vídeo de fundo salvo")
            if build:
                starter = getattr(window, "_start_build", None)
                if callable(starter):
                    starter()
        except Exception as exc:
            status = getattr(window, "status_label", None)
            if status is not None:
                status.set_text(f"Não foi possível salvar o fundo: {exc}")
            toast("Falha ao salvar o vídeo de fundo")

    def remove(*_args) -> None:
        try:
            window.manifest = remove_background_video(window.manifest)
            window._turing_background_selected_source = None
            update_controls()
            refresh_preview()
            status = getattr(window, "status_label", None)
            if status is not None:
                status.set_text("Vídeo de fundo removido; reconstrua o vídeo nativo")
            toast("Vídeo de fundo removido")
        except Exception as exc:
            status = getattr(window, "status_label", None)
            if status is not None:
                status.set_text(f"Não foi possível remover o fundo: {exc}")

    choose_button.connect("clicked", choose_source)
    save_button.connect("clicked", lambda *_args: persist(build=False))
    build_button.connect("clicked", lambda *_args: persist(build=True))
    remove_button.connect("clicked", remove)
    fit_dropdown.connect("notify::selected", refresh_preview)
    position_dropdown.connect("notify::selected", refresh_preview)

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
