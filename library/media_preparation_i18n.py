# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime i18n integration for the GTK media preparation workflow."""

from __future__ import annotations

from typing import Any, Iterable

from library.i18n import active_language


_PT_BR = {
    "Prepare media": "Preparar mídia",
    "Media preparation": "Preparação de mídia",
    "Crop, rotate, align, style, convert, and upload": "Corte, gire, alinhe, estilize, converta e envie",
    "Source": "Origem",
    "GIF or video": "GIF ou vídeo",
    "Choose GIF, MP4, MKV, WebM, MOV, or AVI": "Escolha GIF, MP4, MKV, WebM, MOV ou AVI",
    "Choose…": "Escolher…",
    "Display profile": "Perfil da tela",
    "Target": "Destino",
    "Loading profiles…": "Carregando perfis…",
    "Target dimensions": "Dimensões de destino",
    "Firmware status": "Status do firmware",
    "Loading…": "Carregando…",
    "Estimated output size": "Tamanho estimado da saída",
    "Choose media to calculate": "Escolha uma mídia para calcular",
    "Source information": "Informações da origem",
    "Codec": "Codec",
    "Dimensions": "Dimensões",
    "Duration": "Duração",
    "Frame rate": "Taxa de quadros",
    "Audio": "Áudio",
    "Framing and size": "Enquadramento e tamanho",
    "Mode": "Modo",
    "Fit": "Ajustar",
    "Fill / Cover": "Preencher / Cobrir",
    "Stretch": "Esticar",
    "Original size": "Tamanho original",
    "Custom size": "Tamanho personalizado",
    "Zoom": "Zoom",
    "Custom width": "Largura personalizada",
    "Custom height": "Altura personalizada",
    "Rotation": "Rotação",
    "Horizontal position": "Posição horizontal",
    "Vertical position": "Posição vertical",
    "Crop source": "Cortar origem",
    "Left": "Esquerda",
    "Right": "Direita",
    "Top": "Superior",
    "Bottom": "Inferior",
    "Reset crop": "Redefinir corte",
    "Background": "Fundo",
    "Solid color": "Cor sólida",
    "Blurred source": "Origem desfocada",
    "Custom image": "Imagem personalizada",
    "Solid RGB color": "Cor RGB sólida",
    "Blur strength": "Intensidade do desfoque",
    "Background image": "Imagem de fundo",
    "No image selected": "Nenhuma imagem selecionada",
    "Timing and output": "Tempo e saída",
    "Trim start (seconds)": "Início do corte (segundos)",
    "Trim end (seconds)": "Fim do corte (segundos)",
    "Playback speed": "Velocidade de reprodução",
    "Extra input loops": "Loops extras da origem",
    "Output frame rate": "Taxa de quadros de saída",
    "Output filename": "Nome do arquivo de saída",
    "Upload destination": "Destino do envio",
    "SD card": "Cartão SD",
    "Internal storage": "Armazenamento interno",
    "Framing preview": "Prévia do enquadramento",
    "Choose media to begin.": "Escolha uma mídia para começar.",
    "Convert": "Converter",
    "Preview output": "Pré-visualizar saída",
    "Upload": "Enviar",
    "Choose GIF or video": "Escolher GIF ou vídeo",
    "GIF and video files": "Arquivos GIF e vídeo",
    "The selected file is not available locally": "O arquivo selecionado não está disponível localmente",
    "Analyzing source…": "Analisando origem…",
    "Unknown": "Desconhecido",
    "Present": "Presente",
    "None": "Nenhum",
    "{duration:.2f} seconds": "{duration:.2f} segundos",
    "Adjust crop, rotation, alignment, background, speed, or loops.": "Ajuste corte, rotação, alinhamento, fundo, velocidade ou loops.",
    "Loading display profiles…": "Carregando perfis da tela…",
    "The media backend returned no display profiles.": "O backend de mídia não retornou perfis de tela.",
    "Active theme": "Tema ativo",
    "Display profiles are still loading.": "Os perfis de tela ainda estão carregando.",
    "Hardware validated": "Hardware validado",
    "Upload enabled — not hardware validated": "Envio ativado — hardware não validado",
    "Preview/conversion only — upload disabled": "Apenas prévia/conversão — envio desativado",
    "Actual converted size: {size}": "Tamanho convertido real: {size}",
    "{low} – {high} for about {duration:.1f} s": "{low} – {high} por cerca de {duration:.1f} s",
    "Choose a background image": "Escolher imagem de fundo",
    "Image files": "Arquivos de imagem",
    "Rendering preview…": "Renderizando prévia…",
    "Converting media…": "Convertendo mídia…",
    "Prepared {name} — {size:.1f} KiB{note}": "Preparado {name} — {size:.1f} KiB{note}",
    " — preview only; upload is disabled for this profile": " — apenas prévia; envio desativado para este perfil",
    "Conversion completed": "Conversão concluída",
    "Convert the media first": "Converta a mídia primeiro",
    "Preview — {name}": "Prévia — {name}",
    "Close": "Fechar",
    "Native upload is disabled for this unvalidated display profile. Conversion and local preview remain available.": "O envio nativo está desativado para este perfil de tela não validado. Conversão e prévia local continuam disponíveis.",
    "Uploading prepared video…": "Enviando vídeo preparado…",
    "Upload complete: {remote}": "Envio concluído: {remote}",
    "Prepared video uploaded": "Vídeo preparado enviado",
    "Another operation is already running": "Outra operação já está em andamento",
    "Required backend was not found: {program}": "Backend obrigatório não encontrado: {program}",
    "Working…": "Trabalhando…",
    "Unknown media error": "Erro de mídia desconhecido",
    "Operation failed": "Operação falhou",
}


def t(message: str) -> str:
    if active_language() == "pt_BR":
        return _PT_BR.get(message, message)
    return message


def tr(message: str, **kwargs) -> str:
    return t(message).format(**kwargs)


def translate_dynamic(message: str) -> str:
    """Translate simple dynamic strings emitted by existing callbacks."""

    if active_language() != "pt_BR":
        return message
    backend_prefix = "Required backend was not found: "
    if message.startswith(backend_prefix):
        return tr(
            "Required backend was not found: {program}",
            program=message.removeprefix(backend_prefix),
        )
    return t(message)


def _iter_widget_children(widget: Any) -> Iterable[Any]:
    child = None
    if hasattr(widget, "get_first_child"):
        try:
            child = widget.get_first_child()
        except Exception:
            child = None

    while child is not None:
        yield child
        try:
            child = child.get_next_sibling()
        except Exception:
            child = None


def _walk_widgets(widget: Any) -> Iterable[Any]:
    yield widget
    for child in _iter_widget_children(widget):
        yield from _walk_widgets(child)


def _translate_widget_text(widget: Any) -> None:
    for getter_name, setter_name in (
        ("get_label", "set_label"),
        ("get_title", "set_title"),
        ("get_subtitle", "set_subtitle"),
        ("get_tooltip_text", "set_tooltip_text"),
    ):
        getter = getattr(widget, getter_name, None)
        setter = getattr(widget, setter_name, None)
        if not callable(getter) or not callable(setter):
            continue
        try:
            current = getter()
        except Exception:
            continue
        if not isinstance(current, str) or not current:
            continue
        translated = translate_dynamic(current)
        if translated != current:
            try:
                setter(translated)
            except Exception:
                pass


def translate_widget_tree(root: Any) -> None:
    for widget in _walk_widgets(root):
        _translate_widget_text(widget)


def _set_string_model(app, row: Any, values: list[str]) -> None:
    selected = 0
    try:
        selected = row.get_selected()
    except Exception:
        pass
    row.set_model(app.Gtk.StringList.new([t(value) for value in values]))
    try:
        row.set_selected(selected)
    except Exception:
        pass


def _translate_static_models(app, window: Any) -> None:
    rows = (
        ("mode_row", ["Fit", "Fill / Cover", "Stretch", "Original size", "Custom size"]),
        ("background_mode_row", ["Solid color", "Blurred source", "Custom image"]),
        ("storage_row", ["SD card", "Internal storage"]),
    )
    for attr, values in rows:
        row = getattr(window, attr, None)
        if row is not None:
            _set_string_model(app, row, values)


def _localize_estimate(window: Any) -> None:
    if active_language() != "pt_BR":
        return
    if window.exact_output_size:
        window.estimate_row.set_subtitle(
            tr(
                "Actual converted size: {size}",
                size=window.format_bytes(window.exact_output_size),
            )
        )
        return
    if not window.source_duration:
        window.estimate_row.set_subtitle(t("Choose media to calculate"))
        return

    profile = window.selected_profile()
    width = int(profile.get("width") or 480)
    height = int(profile.get("height") or 480)
    bpp = float(profile.get("estimate_bpp") or 0.075)
    available = window.source_duration * (int(window.loop_count.get_value()) + 1)
    start = min(window.trim_start.get_value(), available)
    end = min(max(window.trim_end.get_value(), start), available)
    selected = max(0.0, end - start)
    duration = selected / max(0.25, window.speed.get_value())
    fps = window.selected_fps()
    middle = width * height * fps * duration * bpp / 8
    middle += max(32768, middle * 0.02)
    low = max(1, round(middle * 0.60))
    high = max(low, round(middle * 1.55))
    window.estimate_row.set_subtitle(
        tr(
            "{low} – {high} for about {duration:.1f} s",
            low=window.format_bytes(low),
            high=window.format_bytes(high),
            duration=duration,
        )
    )


def install_media_preparation_i18n(app) -> None:
    """Translate the GTK media preparation workflow after widgets are created."""

    window_class = getattr(app, "MediaPreparationWindow", None)
    if window_class is None or getattr(window_class, "_media_preparation_i18n_installed", False):
        return

    original_init = window_class.__init__
    original_run_json = window_class.run_json
    original_show_error = window_class.show_error
    original_toast = window_class.toast
    original_on_probe_complete = window_class.on_probe_complete
    original_update_profile_ui = window_class.update_profile_ui
    original_update_estimate = window_class.update_estimate
    original_on_conversion_complete = window_class.on_conversion_complete
    original_on_upload_complete = window_class.on_upload_complete

    def init_with_i18n(self, application):
        original_init(self, application)
        _translate_static_models(app, self)
        translate_widget_tree(self)

    def run_json_with_i18n(self, program, arguments, title, on_success, *args, **kwargs):
        return original_run_json(self, program, arguments, t(title), on_success, *args, **kwargs)

    def show_error_with_i18n(self, message):
        return original_show_error(self, translate_dynamic(str(message)))

    def toast_with_i18n(self, text):
        return original_toast(self, translate_dynamic(str(text)))

    def on_probe_complete_with_i18n(self, data):
        result = original_on_probe_complete(self, data)
        self.duration_row.set_subtitle(
            tr("{duration:.2f} seconds", duration=self.source_duration)
        )
        translate_widget_tree(self)
        return result

    def update_profile_ui_with_i18n(self):
        result = original_update_profile_ui(self)
        subtitle = self.profile_support_row.get_subtitle()
        for key in (
            "Hardware validated",
            "Upload enabled — not hardware validated",
            "Preview/conversion only — upload disabled",
        ):
            if subtitle.startswith(key):
                self.profile_support_row.set_subtitle(subtitle.replace(key, t(key), 1))
                break
        translate_widget_tree(self)
        return result

    def update_estimate_with_i18n(self):
        result = original_update_estimate(self)
        _localize_estimate(self)
        translate_widget_tree(self)
        return result

    def on_conversion_complete_with_i18n(self, data):
        result = original_on_conversion_complete(self, data)
        profile = data.get("profile") or self.selected_profile()
        output = data.get("output") or {}
        size = int(output.get("size_bytes") or 0)
        note = (
            ""
            if profile.get("upload_supported")
            else t(" — preview only; upload is disabled for this profile")
        )
        if self.converted_path is not None:
            self.status.set_label(
                tr(
                    "Prepared {name} — {size:.1f} KiB{note}",
                    name=self.converted_path.name,
                    size=size / 1024,
                    note=note,
                )
            )
        _localize_estimate(self)
        translate_widget_tree(self)
        return result

    def on_upload_complete_with_i18n(self, remote):
        result = original_on_upload_complete(self, remote)
        self.status.set_label(tr("Upload complete: {remote}", remote=remote))
        return result

    window_class.__init__ = init_with_i18n
    window_class.run_json = run_json_with_i18n
    window_class.show_error = show_error_with_i18n
    window_class.toast = toast_with_i18n
    window_class.on_probe_complete = on_probe_complete_with_i18n
    window_class.update_profile_ui = update_profile_ui_with_i18n
    window_class.update_estimate = update_estimate_with_i18n
    window_class.on_conversion_complete = on_conversion_complete_with_i18n
    window_class.on_upload_complete = on_upload_complete_with_i18n
    window_class._media_preparation_i18n_installed = True
