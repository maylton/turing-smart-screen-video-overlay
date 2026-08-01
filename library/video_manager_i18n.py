# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime i18n integration for the GTK video manager."""

from __future__ import annotations

from typing import Any, Iterable

from library.i18n import active_language


_PT_BR = {
    "Turing Video Manager": "Gerenciador de vídeos Turing",
    "Video Manager": "Gerenciador de vídeos",
    "Refresh video list": "Atualizar lista de vídeos",
    "Stop current video": "Parar vídeo atual",
    "Storage": "Armazenamento",
    "SD card": "Cartão SD",
    "Internal storage": "Armazenamento interno",
    "Videos on display": "Vídeos na tela",
    "Import and prepare media…": "Importar e preparar mídia…",
    "Upload compatible MP4…": "Enviar MP4 compatível…",
    "Select a video": "Selecione um vídeo",
    "Choose a file from the list to play or remove it.": "Escolha um arquivo da lista para reproduzir ou remover.",
    "Actions": "Ações",
    "Play video": "Reproduzir vídeo",
    "Start playback on the display": "Inicia a reprodução na tela",
    "Delete video": "Excluir vídeo",
    "Remove the selected file from storage": "Remove o arquivo selecionado do armazenamento",
    "File size": "Tamanho do arquivo",
    "Stop main.py before uploads to avoid two processes using the display.": "Pare o main.py antes de enviar vídeos para evitar dois processos usando a tela.",
    "Working…": "Trabalhando…",
    "Please wait": "Aguarde",
    "Return to video list": "Voltar para a lista de vídeos",
    "No videos found": "Nenhum vídeo encontrado",
    "Upload a compatible MP4 video to start native playback.": "Envie um vídeo MP4 compatível para iniciar a reprodução nativa.",
    "Unknown": "Desconhecido",
    "Unavailable": "Indisponível",
    "Another operation is already running": "Outra operação já está em andamento",
    "video_manager.py was not found": "video_manager.py não foi encontrado",
    "Communicating with the display…": "Comunicando com a tela…",
    "Working…": "Trabalhando…",
    "Operation failed": "Operação falhou",
    "Close": "Fechar",
}


def t(message: str) -> str:
    if active_language() == "pt_BR":
        return _PT_BR.get(message, message)
    return message


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
        translated = t(current)
        if translated != current:
            try:
                setter(translated)
            except Exception:
                pass


def translate_widget_tree(root: Any) -> None:
    for widget in _walk_widgets(root):
        _translate_widget_text(widget)


def install_video_manager_i18n(app) -> None:
    """Translate the standalone GTK video manager after widgets are created."""

    window_class = getattr(app, "VideoManagerWindow", None)
    if window_class is None or getattr(window_class, "_video_manager_i18n_installed", False):
        return

    original_init = window_class.__init__
    original_populate = getattr(window_class, "populate_from_list_output", None)
    original_run_backend = getattr(window_class, "run_backend", None)
    original_update_size = getattr(window_class, "update_size", None)

    def init_with_i18n(self, application):
        original_init(self, application)
        translate_widget_tree(self)

    window_class.__init__ = init_with_i18n

    if callable(original_populate):
        def populate_from_list_output_with_i18n(self, *args, **kwargs):
            result = original_populate(self, *args, **kwargs)
            translate_widget_tree(self)
            return result

        window_class.populate_from_list_output = populate_from_list_output_with_i18n

    if callable(original_run_backend):
        def run_backend_with_i18n(self, arguments, title, on_success, *args, **kwargs):
            return original_run_backend(self, arguments, t(title), on_success, *args, **kwargs)

        window_class.run_backend = run_backend_with_i18n

    if callable(original_update_size):
        def update_size_with_i18n(self, *args, **kwargs):
            result = original_update_size(self, *args, **kwargs)
            translate_widget_tree(self)
            return result

        window_class.update_size = update_size_with_i18n

    window_class._video_manager_i18n_installed = True
