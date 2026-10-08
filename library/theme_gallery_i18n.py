# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime i18n integration for the reusable GTK theme gallery."""

from __future__ import annotations

import functools
from typing import Any, Callable, Iterable

from library.i18n import active_language


_PT_BR = {
    "Theme Gallery": "Galeria de temas",
    "Browse compatible themes": "Navegue por temas compatíveis",
    "Reload the theme list": "Recarregar lista de temas",
    "Open Current": "Abrir atual",
    "Open the current theme in the GTK Theme Editor": "Abrir o tema atual no Editor de Tema GTK",
    "Theme list refreshed": "Lista de temas atualizada",
    "No current theme": "Nenhum tema atual",
    "config.yaml does not point to a compatible theme that exists in res/themes.": "O config.yaml não aponta para um tema compatível que exista em res/themes.",
    "Could not open theme editor": "Não foi possível abrir o editor de tema",
    "Search compatible themes by name, path, or status": "Pesquisar temas compatíveis por nome, caminho ou status",
    "Import": "Importar",
    "Import a .theme package, folder, or legacy .zip archive": "Importar um pacote .theme, pasta ou arquivo .zip legado",
    "/path/to/theme.theme, theme.zip, or theme-folder": "/caminho/para/tema.theme, tema.zip ou pasta-do-tema",
    "No compatible themes": "Nenhum tema compatível",
    "No matching compatible themes": "Nenhum tema compatível encontrado",
    "No compatible themes found": "Nenhum tema compatível encontrado",
    "No compatible theme matches “{query}”.": "Nenhum tema compatível corresponde a “{query}”",
    "No installed theme declares DISPLAY_SIZE {size}\".": "Nenhum tema instalado declara DISPLAY_SIZE {size}\".",
    "Could not detect a display size, so no compatibility filter could be applied.": "Não foi possível detectar o tamanho da tela; nenhum filtro de compatibilidade foi aplicado.",
    "compatible theme": "tema compatível",
    "compatible themes": "temas compatíveis",
    "Current": "Atual",
    "Current theme": "Tema atual",
    "Ready": "Pronto",
    "Unknown display size": "Tamanho de tela desconhecido",
    "display": "display",
    "Missing theme.yaml": "theme.yaml ausente",
    "Missing DISPLAY_SIZE": "DISPLAY_SIZE ausente",
    "No preview": "Sem prévia",
    "Use": "Usar",
    "Set this theme as current": "Definir este tema como atual",
    "Edit": "Editar",
    "Sync video": "Sincronizar vídeo",
    "Sync this theme video to the display": "Sincronizar o vídeo deste tema com a tela",
    "Duplicate theme": "Duplicar tema",
    "Rename theme": "Renomear tema",
    "Export theme": "Exportar tema",
    "Delete theme": "Excluir tema",
    "Show theme diagnostics": "Mostrar diagnóstico do tema",
    "Open theme folder": "Abrir pasta do tema",
    "Diagnostics — {theme}": "Diagnóstico — {theme}",
    "Review the gallery-level theme report below.": "Revise abaixo o relatório do tema no nível da galeria.",
    "Copy Report": "Copiar relatório",
    "Diagnostics report copied": "Relatório de diagnóstico copiado",
    "Use {theme}?": "Usar {theme}?",
    "This will update config.yaml so this theme becomes the current theme used by the app.": "Isso atualizará o config.yaml para que este tema se torne o tema atual usado pelo app.",
    "Use Theme": "Usar tema",
    "Duplicate {theme}": "Duplicar {theme}",
    "Create a non-destructive copy of this theme. The copy will not become the current theme automatically.": "Cria uma cópia não destrutiva deste tema. A cópia não se tornará o tema atual automaticamente.",
    "Rename {theme}": "Renomear {theme}",
    "Rename the theme folder. If this is the current theme, config.yaml will be updated automatically.": "Renomeia a pasta do tema. Se este for o tema atual, o config.yaml será atualizado automaticamente.",
    "Delete {theme}?": "Excluir {theme}?",
    "This will move the theme folder to Trash. To confirm, type the theme name exactly.": "Isso moverá a pasta do tema para a Lixeira. Para confirmar, digite o nome do tema exatamente.",
    "Theme name did not match": "O nome do tema não confere",
    "Type {theme} exactly to delete this theme.": "Digite {theme} exatamente para excluir este tema.",
    "Import Theme": "Importar tema",
    "Import a theme from a .theme package, folder, or legacy .zip archive. Existing themes are never overwritten.": "Importa um tema de um pacote .theme, pasta ou arquivo .zip legado. Temas existentes nunca são sobrescritos.",
    "Export {theme}": "Exportar {theme}",
    "Export this theme as one portable .theme file. Existing files are never overwritten.": "Exporta este tema como um único arquivo .theme portátil. Arquivos existentes nunca são sobrescritos.",
    "/path/to/theme.theme or /path/to/folder": "/caminho/para/tema.theme ou /caminho/para/pasta",
    "Cancel": "Cancelar",
    "OK": "OK",
    "Duplicate": "Duplicar",
    "Rename": "Renomear",
    "Delete": "Excluir",
    "Export": "Exportar",
    "Close": "Fechar",
    "Copied": "Copiado",
    "Error": "Erro",
    "Theme Gallery Diagnostics": "Diagnóstico da Galeria de Temas",
    "Theme": "Tema",
    "Status": "Status",
    "Target display": "Tela alvo",
    "Theme display": "Tela do tema",
    "Theme folder": "Pasta do tema",
    "Theme YAML": "YAML do tema",
    "Theme YAML size": "Tamanho do YAML do tema",
    "Theme YAML lines": "Linhas do YAML do tema",
    "Theme YAML status": "Status do YAML do tema",
    "Preview": "Prévia",
    "Preview size": "Tamanho da prévia",
    "Preview status": "Status da prévia",
    "Top-level files": "Arquivos no nível principal",
    "Top-level folders": "Pastas no nível principal",
    "Gallery checks": "Verificações da galeria",
    "Compatible with target display": "Compatível com a tela alvo",
    "Editable in GTK Theme Editor": "Editável no Editor de Tema GTK",
    "Has preview image": "Tem imagem de prévia",
    "Has theme.yaml/theme.yml": "Tem theme.yaml/theme.yml",
    "Blocking issue": "Problema bloqueante",
    "yes": "sim",
    "no": "não",
    "unknown": "desconhecido",
    "missing": "ausente",
}


def t(message: str) -> str:
    if active_language() == "pt_BR":
        return _PT_BR.get(message, message)
    return message


def tr(message: str, **kwargs) -> str:
    return t(message).format(**kwargs)


def translate_dynamic(message: str) -> str:
    if active_language() != "pt_BR":
        return message

    patterns = (
        ("Diagnostics — ", "Diagnostics — {theme}"),
        ("Use ", "Use {theme}?"),
        ("Duplicate ", "Duplicate {theme}"),
        ("Rename ", "Rename {theme}"),
        ("Delete ", "Delete {theme}?"),
        ("Export ", "Export {theme}"),
        ("Type ", "Type {theme} exactly to delete this theme."),
    )
    for prefix, template in patterns:
        if not message.startswith(prefix):
            continue
        if template.endswith("?") and not message.endswith("?"):
            continue
        if template == "Type {theme} exactly to delete this theme.":
            suffix = " exactly to delete this theme."
            if message.endswith(suffix):
                return tr(
                    template,
                    theme=message.removeprefix(prefix).removesuffix(suffix),
                )
            continue
        theme = message.removeprefix(prefix).removesuffix("?")
        return tr(template, theme=theme)

    if message.startswith("No compatible theme matches “") and message.endswith("”."):
        query = message.removeprefix("No compatible theme matches “").removesuffix("”.")
        return tr("No compatible theme matches “{query}”.", query=query)

    if message.startswith("No installed theme declares DISPLAY_SIZE ") and message.endswith("\"."):
        size = message.removeprefix("No installed theme declares DISPLAY_SIZE ").removesuffix("\".")
        return tr("No installed theme declares DISPLAY_SIZE {size}\".", size=size)

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
        ("get_placeholder_text", "set_placeholder_text"),
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


def _dialog_heading(dialog: Any) -> str:
    getter = getattr(dialog, "get_heading", None)
    if callable(getter):
        try:
            return str(getter() or "")
        except Exception:
            pass
    return ""


def _dialog_body(dialog: Any) -> str:
    getter = getattr(dialog, "get_body", None)
    if callable(getter):
        try:
            return str(getter() or "")
        except Exception:
            pass
    return ""


def _translate_dialog(dialog: Any) -> None:
    heading = _dialog_heading(dialog)
    setter = getattr(dialog, "set_heading", None)
    if callable(setter) and heading:
        try:
            setter(translate_dynamic(heading))
        except Exception:
            pass

    body = _dialog_body(dialog)
    setter = getattr(dialog, "set_body", None)
    if callable(setter) and body:
        try:
            setter(translate_dynamic(body))
        except Exception:
            pass

    translate_widget_tree(dialog)


def _install_dialog_i18n(gallery: Any) -> None:
    Adw = getattr(gallery, "Adw", None)
    if Adw is None:
        return
    cls = getattr(Adw, "AlertDialog", None)
    if cls is None:
        return

    if not getattr(cls, "_theme_gallery_i18n_present_installed", False):
        original_present = getattr(cls, "present", None)
        if callable(original_present):
            def present_with_i18n(self, *args, __original_present=original_present, **kwargs):
                _translate_dialog(self)
                return __original_present(self, *args, **kwargs)

            try:
                cls.present = present_with_i18n
                cls._theme_gallery_i18n_present_installed = True
            except Exception:
                pass

    if not getattr(cls, "_theme_gallery_i18n_response_installed", False):
        original_add_response = getattr(cls, "add_response", None)
        if callable(original_add_response):
            def add_response_with_i18n(
                self,
                response_id,
                label,
                __original_add_response=original_add_response,
            ):
                return __original_add_response(
                    self,
                    response_id,
                    translate_dynamic(str(label)),
                )

            try:
                cls.add_response = add_response_with_i18n
                cls._theme_gallery_i18n_response_installed = True
            except Exception:
                pass


def localize_report(report: str) -> str:
    if active_language() != "pt_BR":
        return report

    label_replacements = {
        "Theme Gallery Diagnostics": t("Theme Gallery Diagnostics"),
        "Theme:": f"{t('Theme')}:",
        "Status:": f"{t('Status')}:",
        "Current theme:": f"{t('Current theme')}:",
        "Target display:": f"{t('Target display')}:",
        "Theme display:": f"{t('Theme display')}:",
        "Theme folder:": f"{t('Theme folder')}:",
        "Theme YAML:": f"{t('Theme YAML')}:",
        "Theme YAML size:": f"{t('Theme YAML size')}:",
        "Theme YAML lines:": f"{t('Theme YAML lines')}:",
        "Theme YAML status:": f"{t('Theme YAML status')}:",
        "Preview:": f"{t('Preview')}:",
        "Preview size:": f"{t('Preview size')}:",
        "Preview status:": f"{t('Preview status')}:",
        "Top-level files:": f"{t('Top-level files')}:",
        "Top-level folders:": f"{t('Top-level folders')}:",
        "Gallery checks:": f"{t('Gallery checks')}:",
        "Compatible with target display:": f"{t('Compatible with target display')}:",
        "Editable in GTK Theme Editor:": f"{t('Editable in GTK Theme Editor')}:",
        "Has preview image:": f"{t('Has preview image')}:",
        "Has theme.yaml/theme.yml:": f"{t('Has theme.yaml/theme.yml')}:",
        "Blocking issue:": f"{t('Blocking issue')}:",
    }
    value_replacements = {
        "yes": t("yes"),
        "no": t("no"),
        "unknown": t("unknown"),
        "missing": t("missing"),
        "Current theme": t("Current theme"),
        "Ready": t("Ready"),
        "Missing theme.yaml": t("Missing theme.yaml"),
        "Missing DISPLAY_SIZE": t("Missing DISPLAY_SIZE"),
    }

    localized_lines: list[str] = []
    for original_line in report.splitlines():
        line = original_line
        for source, target in label_replacements.items():
            if line.startswith(source):
                line = target + line[len(source):]
                break
            bullet = f"- {source}"
            if line.startswith(bullet):
                line = f"- {target}" + line[len(bullet):]
                break
        for source, target in value_replacements.items():
            line = line.replace(f": {source}", f": {target}")
            line = line.replace(f" {source}", f" {target}")
        localized_lines.append(line)
    return "\n".join(localized_lines)


def translated_widget(method: Callable[..., Any]) -> Callable[..., Any]:
    """Translate the widget tree a builder method returns."""

    @functools.wraps(method)
    def wrapper(*args, **kwargs):
        widget = method(*args, **kwargs)
        translate_widget_tree(widget)
        return widget

    return wrapper


def install_theme_gallery_i18n(app: Any | None = None) -> None:
    """Translate every Adw.AlertDialog heading, body and response label.

    This is a deliberate application-wide hook: dialogs are built in many
    modules, and translating them when presented keeps those call sites plain.
    """
    del app
    from library import theme_gallery as gallery

    _install_dialog_i18n(gallery)
