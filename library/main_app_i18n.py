# SPDX-License-Identifier: GPL-3.0-or-later
"""Main GTK application i18n integration hooks."""

from __future__ import annotations

from typing import Any, Callable, Iterable


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
    "Open the original Tkinter configuration window.": "Abre a janela de configuração original em Tkinter.",
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


def _wrap_translate_after(window_class: type, method_name: str) -> None:
    original = getattr(window_class, method_name, None)
    if not callable(original) or getattr(original, "_main_app_i18n_wrapper", False):
        return

    def wrapper(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        translate_widget_tree(self)
        return result

    wrapper._main_app_i18n_wrapper = True
    setattr(window_class, method_name, wrapper)


def install_theme_gallery_i18n(app) -> None:
    """Localize theme gallery cards, dialogs, and standalone surfaces."""

    try:
        from library.theme_gallery_i18n import install_theme_gallery_i18n as install

        install(app)
    except Exception:
        return


def install_main_app_tray_i18n(app) -> None:
    """Localize the StatusNotifier tray menu without changing tray behavior."""

    from library.i18n import t as _, tr

    StatusNotifierMenu = getattr(app, "StatusNotifierMenu", None)
    StatusNotifierItem = getattr(app, "StatusNotifierItem", None)
    if StatusNotifierMenu is None or StatusNotifierItem is None:
        return

    def menu_label(self, action: str) -> str:
        labels = {
            "show-hide-window": (
                _("Hide window") if self.window_visible() else _("Show window")
            ),
            "start-screen": _("Start screen"),
            "turn-off-screen": _("Turn off screen"),
            "open-theme-editor": _("Open theme editor"),
            "open-video-manager": _("Open video manager"),
            "quit": _("Quit"),
        }
        return labels.get(action, action)

    def status_notifier_get_property(
        self,
        _connection,
        _sender,
        _object_path,
        _interface_name,
        property_name,
    ):
        theme = app.read_current_theme() or _("not selected")
        values = {
            "Category": app.GLib.Variant("s", "Hardware"),
            "Id": app.GLib.Variant("s", app.APP_ID),
            "Title": app.GLib.Variant("s", app.APP_NAME),
            "Status": app.GLib.Variant("s", "Active"),
            "WindowId": app.GLib.Variant("u", 0),
            "IconName": app.GLib.Variant("s", app.APP_ID),
            "IconThemePath": app.GLib.Variant("s", ""),
            "OverlayIconName": app.GLib.Variant("s", ""),
            "AttentionIconName": app.GLib.Variant("s", ""),
            "ToolTip": app.GLib.Variant(
                "(sa(iiay)ss)",
                (
                    app.APP_ID,
                    [],
                    app.APP_NAME,
                    tr("Theme: {theme}", theme=theme),
                ),
            ),
            "ItemIsMenu": app.GLib.Variant("b", False),
            "Menu": app.GLib.Variant("o", app.DBUSMENU_OBJECT_PATH),
        }
        return values.get(property_name)

    StatusNotifierMenu.menu_label = menu_label
    StatusNotifierItem._on_get_property = status_notifier_get_property
    setattr(app, "_tray_i18n_installed", True)


def install_main_app_shell_i18n(app) -> None:
    """Localize the main GTK shell after each affected UI build/refresh."""

    install_main_app_tray_i18n(app)
    install_theme_gallery_i18n(app)

    window_class = getattr(app, "SmartScreenWindow", None)
    if window_class is None or getattr(window_class, "_main_app_shell_i18n_installed", False):
        return

    original_init = window_class.__init__
    original_build_settings_page = window_class.build_settings_page
    original_refresh_overview = window_class.refresh_overview
    original_toast = getattr(window_class, "toast", None)

    def init_with_i18n(self, application):
        original_init(self, application)
        translate_widget_tree(self)

    def build_settings_page_with_i18n(self):
        page = original_build_settings_page(self)
        translate_widget_tree(page)
        return page

    def refresh_overview_with_i18n(self):
        result = original_refresh_overview(self)
        translate_widget_tree(self)
        return result

    if callable(original_toast):
        def toast_with_i18n(self, message: str, *args, **kwargs):
            return original_toast(
                self,
                translate_main_app_text(str(message)),
                *args,
                **kwargs,
            )

        toast_with_i18n._main_app_shell_i18n_wrapper = True
        window_class.toast = toast_with_i18n

    init_with_i18n._main_app_shell_i18n_wrapper = True
    build_settings_page_with_i18n._main_app_shell_i18n_wrapper = True
    refresh_overview_with_i18n._main_app_shell_i18n_wrapper = True

    window_class.__init__ = init_with_i18n
    window_class.build_settings_page = build_settings_page_with_i18n
    window_class.refresh_overview = refresh_overview_with_i18n

    for method_name in (
        "build_themes_page",
        "build_tools_page",
        "refresh_theme_list",
        "on_theme_selected",
        "finish_display_detection",
        "finish_turn_off_display",
        "show_checkup_result",
    ):
        _wrap_translate_after(window_class, method_name)

    window_class._main_app_shell_i18n_installed = True
