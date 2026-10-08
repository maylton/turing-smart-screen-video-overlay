# SPDX-License-Identifier: GPL-3.0-or-later
"""Portuguese translation of the main window and tray menu."""

from __future__ import annotations

from typing import Any, Callable, Iterable

from gi.repository import GLib

from library.i18n import t as _, tr


_EXACT_PT_BR = {
    "Installed themes": "Temas instalados",
    "Create an empty theme for the selected display": "Criar um tema vazio para a tela selecionada",
    "Refresh compatible theme list": "Atualizar lista de temas compatíveis",
    "Theme preview": "Prévia do tema",
    "Set active theme": "Definir tema ativo",
    "Open editor": "Abrir editor",
    "Tools": "Ferramentas",
    "Available tools": "Ferramentas disponíveis",
    "Edit components, backgrounds, positions, and sensor templates.": "Edite componentes, fundos, posições e modelos de sensores.",
    "Native video manager": "Gerenciador de vídeos nativos",
    "Manage videos stored on the Turing Smart Screen.": "Gerencie vídeos armazenados na Turing Smart Screen.",
    "Display size could not be detected; showing all installed themes": "Não foi possível detectar o tamanho da tela; mostrando todos os temas instalados",
    "No themes found": "Nenhum tema encontrado",
    "No theme selected": "Nenhum tema selecionado",
    "Select a theme first": "Selecione um tema primeiro",
    "No active theme configured": "Nenhum tema ativo configurado",
    "No saved theme to apply automatically": "Nenhum tema salvo para aplicar automaticamente",
    "main.py was not found": "main.py não foi encontrado",
    "screen-control.py was not found": "screen-control.py não foi encontrado",
    "gtk-checkup.py was not found": "gtk-checkup.py não foi encontrado",
    "Monitor started": "Tela iniciada",
    "Monitor stopped": "Tela parada",
    "Display turned off": "Tela desligada",
    "Detection failed": "Falha na detecção",
    "Detection completed": "Detecção concluída",
    "Scanning USB and serial descriptors…": "Verificando USB e descritores seriais…",
    "Unknown error": "Erro desconhecido",
    "No output": "Sem saída",
    "Select or configure a display before creating an empty theme": "Selecione ou configure uma tela antes de criar um tema vazio",
    "Theme name": "Nome do tema",
    "Create empty theme": "Criar tema vazio",
    "Create": "Criar",
    "Enter a valid theme name": "Digite um nome de tema válido",
    "Open Current": "Abrir atual",
    "Theme list refreshed": "Lista de temas atualizada",
    "Sync is available from the Themes page": "A sincronização está disponível na página Temas",
    "Apply + Sync is available from the Themes page": "Aplicar + Sincronizar está disponível na página Temas",
    "Open Themes once before applying the current theme": "Abra Temas uma vez antes de aplicar o tema atual",
    "Apply + Sync is available from the Themes page": "Aplicar + Sincronizar está disponível na página Temas",
}

_PREFIX_PT_BR = {
    "File not found: ": "Arquivo não encontrado: ",
    "Could not open ": "Não foi possível abrir ",
    "Could not open diagnostics: ": "Não foi possível abrir o diagnóstico: ",
    "Could not open theme editor: ": "Não foi possível abrir o editor de tema: ",
    "Could not open theme folder: ": "Não foi possível abrir a pasta do tema: ",
    "Could not change appearance: ": "Não foi possível alterar a aparência: ",
    "Could not save startup preference: ": "Não foi possível salvar a preferência de inicialização: ",
    "Could not save monitor startup preference: ": "Não foi possível salvar a preferência de inicialização da tela: ",
    "Could not apply saved theme: ": "Não foi possível aplicar o tema salvo: ",
    "Could not start monitor: ": "Não foi possível iniciar a tela: ",
    "Could not turn off display: ": "Não foi possível desligar a tela: ",
    "Could not load preview: ": "Não foi possível carregar a prévia: ",
    "Could not update config.yaml: ": "Não foi possível atualizar config.yaml: ",
    "Could not create empty theme: ": "Não foi possível criar o tema vazio: ",
    "A theme named ": "Um tema chamado ",
    "Active theme changed to ": "Tema ativo alterado para ",
    "Active theme was not found in the gallery: ": "O tema ativo não foi encontrado na galeria: ",
    "Empty theme created: ": "Tema vazio criado: ",
    "Current theme changed: ": "Tema atual alterado: ",
    "Current theme set to ": "Tema atual definido como ",
    "Opening folder for ": "Abrindo pasta de ",
    "Opening ": "Abrindo ",
}

_SUFFIX_PT_BR = {
    " already exists": " já existe",
}


def translate_main_app_text(message: str) -> str:
    """Translate exact and common dynamic strings used by the main GTK app."""

    if not isinstance(message, str) or not message:
        return message

    from library.i18n import active_language, t as _

    translated = _(message)
    if translated != message or active_language() != "pt_BR":
        return translated

    if message in _EXACT_PT_BR:
        return _EXACT_PT_BR[message]

    if message.startswith("Showing themes compatible with the selected ") and message.endswith('" display'):
        size = message.removeprefix("Showing themes compatible with the selected ").removesuffix('" display')
        return f'Mostrando temas compatíveis com a tela de {size}"'

    if message.startswith("No compatible themes found for the ") and message.endswith('" display'):
        size = message.removeprefix("No compatible themes found for the ").removesuffix('" display')
        return f'Nenhum tema compatível encontrado para a tela de {size}"'

    if message.startswith("Expected folder:\n"):
        return "Pasta esperada:\n" + message.removeprefix("Expected folder:\n")

    if message.startswith("A clean theme will be created for the selected ") and message.endswith('" display.'):
        size = message.removeprefix("A clean theme will be created for the selected ").removesuffix('" display.')
        return f'Um tema limpo será criado para a tela de {size}".'

    for prefix, replacement in _PREFIX_PT_BR.items():
        if message.startswith(prefix):
            tail = message.removeprefix(prefix)
            for suffix, translated_suffix in _SUFFIX_PT_BR.items():
                if tail.endswith(suffix):
                    tail = tail.removesuffix(suffix) + translated_suffix
                    break
            return replacement + tail

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


def _translate_widget_text(widget: Any, translate: Callable[[str], str]) -> None:
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
        translated = translate(current)
        if translated != current:
            try:
                setter(translated)
            except Exception:
                pass


def translate_widget_tree(root: Any) -> None:
    """Translate exact and common dynamic English strings in a GTK tree."""

    for widget in _walk_widgets(root):
        _translate_widget_text(widget, translate_main_app_text)


def _translate_after(method_name: str):
    """Build a method that runs the parent implementation, then translates."""

    def method(self, *args, **kwargs):
        result = getattr(super(I18nMixin, self), method_name)(*args, **kwargs)
        translate_widget_tree(self)
        return result

    method.__name__ = method_name
    return method


class I18nMixin:
    """Translate the main window after each UI build or refresh."""

    def __init__(self, application):
        super().__init__(application)
        translate_widget_tree(self)

        # Mixins listed before this one may append widgets after the
        # immediate translation; translate again once the GTK loop is idle.
        def translate_after_integrations():
            translate_widget_tree(self)
            return False

        GLib.idle_add(translate_after_integrations)

    def build_settings_page(self):
        page = super().build_settings_page()
        translate_widget_tree(page)
        return page

    def refresh_overview(self):
        result = super().refresh_overview()
        translate_widget_tree(self)
        return result

    def toast(self, message: str, *args, **kwargs):
        return super().toast(translate_main_app_text(str(message)), *args, **kwargs)

    build_themes_page = _translate_after("build_themes_page")
    refresh_theme_list = _translate_after("refresh_theme_list")
    on_theme_selected = _translate_after("on_theme_selected")
    finish_display_detection = _translate_after("finish_display_detection")
    finish_turn_off_display = _translate_after("finish_turn_off_display")
    show_checkup_result = _translate_after("show_checkup_result")


class TrayMenuI18nMixin:
    def menu_label(self, action: str) -> str:
        labels = {
            "show-hide-window": _("Hide window") if self.window_visible() else _("Show window"),
            "start-screen": _("Start screen"),
            "turn-off-screen": _("Turn off screen"),
            "open-theme-editor": _("Open theme editor"),
            "open-video-manager": _("Open video manager"),
            "quit": _("Quit"),
        }
        return labels.get(action, action)


class TrayItemI18nMixin:
    def _on_get_property(self, _connection, _sender, _object_path, _interface_name, property_name):
        from library import main_app_base as app

        theme = app.read_current_theme() or _("not selected")
        values = {
            "Category": GLib.Variant("s", "Hardware"),
            "Id": GLib.Variant("s", app.APP_ID),
            "Title": GLib.Variant("s", app.APP_NAME),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("u", 0),
            "IconName": GLib.Variant("s", app.APP_ID),
            "IconThemePath": GLib.Variant("s", ""),
            "OverlayIconName": GLib.Variant("s", ""),
            "AttentionIconName": GLib.Variant("s", ""),
            "ToolTip": GLib.Variant(
                "(sa(iiay)ss)",
                (app.APP_ID, [], app.APP_NAME, tr("Theme: {theme}", theme=theme)),
            ),
            "ItemIsMenu": GLib.Variant("b", False),
            "Menu": GLib.Variant("o", app.DBUSMENU_OBJECT_PATH),
        }
        return values.get(property_name)
