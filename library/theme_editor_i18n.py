# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime i18n integration for the GTK Theme Editor.

The editor is currently a large script executed as ``__main__``. To keep this
phase small and avoid editing the whole file, usercustomize installs a class
creation hook before theme-editor-gtk.py defines ThemeEditorWindow. This module
then wraps the window lifecycle and translates already-created GTK widgets.
"""

from __future__ import annotations

import builtins
import sys
from typing import Any, Iterable

from library.i18n import active_language


_PT_BR = {
    # Header and global actions
    "Theme editor": "Editor de tema",
    "Undo the last change": "Desfazer a última alteração",
    "Redo the last undone change": "Refazer a última alteração desfeita",
    "Render and refresh the theme preview": "Renderizar e atualizar a prévia do tema",
    "Save": "Salvar",
    "Save the current theme YAML": "Salvar o YAML atual do tema",
    "Tools": "Ferramentas",
    "Open theme editing tools": "Abrir ferramentas de edição do tema",
    "More theme actions": "Mais ações do tema",

    # Tools popover
    "Media": "Mídia",
    "Video Inspector": "Inspetor de vídeo",
    "Video and Background": "Vídeo e fundo",
    "Generated Media": "Mídia gerada",
    "Windows themes": "Temas do Windows",
    "Extract Windows Theme Assets…": "Extrair assets de tema do Windows…",
    "Save As…": "Salvar como…",
    "Rename Theme…": "Renomear tema…",
    "Copy Theme Folder Path": "Copiar caminho da pasta do tema",
    "Copy Theme YAML Path": "Copiar caminho do YAML do tema",
    "Open Theme Folder": "Abrir pasta do tema",
    "Open Theme Folder in Terminal": "Abrir pasta do tema no terminal",
    "Open Theme YAML": "Abrir YAML do tema",
    "Reload Theme From Disk": "Recarregar tema do disco",
    "Theme Diagnostics": "Diagnóstico do tema",
    "Advanced / Legacy Editor…": "Editor avançado / legado…",

    # Elements panel
    "Theme elements": "Elementos do tema",
    "Add": "Adicionar",
    "Add or select the chosen catalog element": "Adicionar ou selecionar o elemento escolhido do catálogo",
    "Search elements": "Pesquisar elementos",
    "All elements": "Todos os elementos",
    "Visible": "Visíveis",
    "Hidden": "Ocultos",
    "Mixed": "Misturados",
    "Structure": "Estrutura",
    "Expand all": "Expandir tudo",
    "Expand every group in the component tree": "Expandir todos os grupos da árvore de componentes",
    "Collapse all": "Recolher tudo",
    "Collapse every group in the component tree": "Recolher todos os grupos da árvore de componentes",
    "Actions": "Ações",
    "Show / Enable": "Mostrar / Ativar",
    "Show static elements or enable sensor/video components": "Mostra elementos estáticos ou ativa componentes de sensor/vídeo",
    "Hide / Disable": "Ocultar / Desativar",
    "Hide static elements or disable sensor/video components": "Oculta elementos estáticos ou desativa componentes de sensor/vídeo",
    "Adjust image layout…": "Ajustar layout da imagem…",
    "Open the non-destructive static image layout inspector": "Abre o inspetor não destrutivo de layout da imagem estática",
    "Layer order": "Ordem das camadas",
    "Move backward": "Mover para trás",
    "Move this layer one position toward the start of its group, drawing below its previous neighbor": "Move esta camada uma posição para o início do grupo, desenhando abaixo da vizinha anterior",
    "Move forward": "Mover para frente",
    "Move this layer one position toward the end of its group, drawing above its next neighbor": "Move esta camada uma posição para o fim do grupo, desenhando acima da próxima vizinha",
    "Send to back": "Enviar para trás",
    "Move this layer to the first position of its text or image group": "Move esta camada para a primeira posição do grupo de texto ou imagem",
    "Bring to front": "Trazer para frente",
    "Move this layer to the last position of its text or image group": "Move esta camada para a última posição do grupo de texto ou imagem",
    "Duplicate": "Duplicar",
    "Duplicate the selected custom text or static image": "Duplica o texto personalizado ou a imagem estática selecionada",
    "Delete": "Excluir",
    "Delete custom elements; sensors are disabled after confirmation": "Exclui elementos personalizados; sensores são desativados após confirmação",
    "Legacy editor access moved to More theme actions → Advanced / Legacy Editor…": "O acesso ao editor legado foi movido para Mais ações do tema → Editor avançado / legado…",

    # Preview and properties
    "Live preview": "Prévia ao vivo",
    "Select an element with X/Y, then drag it directly on the preview.": "Selecione um elemento com X/Y e arraste-o diretamente na prévia.",
    "Properties": "Propriedades",
    "Select an element": "Selecione um elemento",
    "Apply property changes": "Aplicar alterações de propriedade",
    "Save the edited values and refresh the preview": "Salva os valores editados e atualiza a prévia",
    "Reset selected element": "Redefinir elemento selecionado",
    "Restore this element to its state when the editor was opened": "Restaura este elemento ao estado em que estava quando o editor foi aberto",
    "Video and background…": "Vídeo e fundo…",
    "Choose a local/display video or generate a preview background": "Escolha um vídeo local/da tela ou gere um fundo de prévia",
    "Text effects…": "Efeitos de texto…",
    "Configure shadow, glow, and outline": "Configurar sombra, brilho e contorno",
    "Video tools": "Ferramentas de vídeo",
    "Preview, prepare, or manage the theme video.": "Pré-visualize, prepare ou gerencie o vídeo do tema.",
    "Inspector": "Inspetor",
    "Background": "Fundo",

    # Gradient / style dialogs
    "Gradient effect": "Efeito de degradê",
    "Gradient": "Degradê",
    "Gradient fill": "Preenchimento em degradê",
    "Customize the gradient used by this text or graph bar.": "Personalize o degradê usado por este texto ou barra de gráfico.",
    "Enabled": "Ativado",
    "Render this element with a gradient fill.": "Renderiza este elemento com preenchimento em degradê.",
    "Start color": "Cor inicial",
    "End color": "Cor final",
    "Direction": "Direção",
    "Choose how the gradient flows.": "Escolha como o degradê flui.",
    "Apply gradient": "Aplicar degradê",
    "Save these gradient settings to the selected element.": "Salva estas configurações de degradê no elemento selecionado.",
    "Apply": "Aplicar",
    "Auto": "Automático",
    "Horizontal": "Horizontal",
    "Vertical": "Vertical",
    "Right to left": "Direita para esquerda",
    "Bottom to top": "Baixo para cima",
    "No gradient changes": "Nenhuma alteração no degradê",
    "Gradient updated": "Degradê atualizado",
    "This element does not support gradient effects": "Este elemento não suporta efeitos de degradê",
    "Selected element is no longer available": "O elemento selecionado não está mais disponível",

    # Video/background preparation dialogs embedded in the editor
    "Mode": "Modo",
    "Fit": "Ajustar",
    "Fill": "Preencher",
    "Stretch": "Esticar",
    "Original": "Original",
    "Custom": "Personalizado",
    "Zoom": "Zoom",
    "Custom width": "Largura personalizada",
    "Custom height": "Altura personalizada",
    "Horizontal alignment": "Alinhamento horizontal",
    "Vertical alignment": "Alinhamento vertical",
    "Left": "Esquerda",
    "Center": "Centro",
    "Right": "Direita",
    "Top": "Superior",
    "Bottom": "Inferior",
    "Rotation": "Rotação",
    "Mirror horizontally": "Espelhar horizontalmente",
    "Flip the foreground video left-to-right before scaling.": "Espelha o vídeo em primeiro plano da esquerda para a direita antes do redimensionamento.",
    "Mirror vertically": "Espelhar verticalmente",
    "Flip the foreground video top-to-bottom before scaling.": "Espelha o vídeo em primeiro plano de cima para baixo antes do redimensionamento.",
    "Crop left": "Cortar à esquerda",
    "Crop right": "Cortar à direita",
    "Crop top": "Cortar acima",
    "Crop bottom": "Cortar abaixo",
    "Trim start (seconds)": "Início do corte (segundos)",
    "Trim end (0 = full source)": "Fim do corte (0 = origem completa)",
    "Playback speed": "Velocidade de reprodução",
    "Loop count": "Quantidade de loops",
    "Background mode": "Modo do fundo",
    "Solid color": "Cor sólida",
    "Blurred source": "Origem desfocada",
    "Image": "Imagem",
    "Solid background RGB": "RGB sólido do fundo",
    "Blur strength": "Intensidade do desfoque",
    "Background image": "Imagem de fundo",
    "Choose image…": "Escolher imagem…",
    "Image file": "Arquivo de imagem",
    "Output FPS": "FPS de saída",
    "Quality (CRF)": "Qualidade (CRF)",

    # Common dialogs / file actions
    "Close": "Fechar",
    "Cancel": "Cancelar",
    "Open Folder": "Abrir pasta",
    "Copy Manifest Path": "Copiar caminho do manifesto",
    "Open Extracted Theme": "Abrir tema extraído",
    "Choose a Windows .turtheme file": "Escolher um arquivo .turtheme do Windows",
    "Windows Turing theme files": "Arquivos de tema Turing do Windows",
    "All files": "Todos os arquivos",
    "No Windows theme file selected": "Nenhum arquivo de tema do Windows selecionado",
    "Windows theme not found": "Tema do Windows não encontrado",
    "Extracting Windows theme assets…": "Extraindo assets do tema do Windows…",
    "Could not extract Windows theme assets": "Não foi possível extrair assets do tema do Windows",
    "Windows theme assets extracted": "Assets do tema do Windows extraídos",
    "No assets found": "Nenhum asset encontrado",
    "Windows theme asset manifest path": "Caminho do manifesto de assets do tema do Windows",
    "Open theme.yaml externally?": "Abrir theme.yaml externamente?",
    "Open YAML": "Abrir YAML",
    "Could not open theme.yaml": "Não foi possível abrir theme.yaml",
    "Could not reload theme": "Não foi possível recarregar o tema",

    # Toasts / runtime hints
    "Select a static image first": "Selecione uma imagem estática primeiro",
    "Static image unavailable": "Imagem estática indisponível",
    "Select an element with X and Y first": "Selecione primeiro um elemento com X e Y",
}


_STATE_FILTER_KEYS = [
    "All elements",
    "Visible",
    "Hidden",
    "Mixed",
    "Structure",
]


_THEME_EDITOR_HOOK_INSTALLED = False
_ORIGINAL_BUILD_CLASS = None


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
        translated = t(current)
        if translated != current:
            try:
                setter(translated)
            except Exception:
                pass


def translate_widget_tree(root: Any) -> None:
    for widget in _walk_widgets(root):
        _translate_widget_text(widget)


def _set_string_model(app_module: Any, row: Any, values: list[str]) -> None:
    selected = 0
    try:
        selected = row.get_selected()
    except Exception:
        pass
    row.set_model(app_module.Gtk.StringList.new([t(value) for value in values]))
    try:
        row.set_selected(selected)
    except Exception:
        pass


def _translate_static_models(window: Any) -> None:
    app_module = __import__(window.__class__.__module__)
    row = getattr(window, "state_filter_dropdown", None)
    if row is not None:
        _set_string_model(app_module, row, _STATE_FILTER_KEYS)


def _translate_dialog_title(dialog: Any) -> None:
    for getter_name, setter_name in (("get_title", "set_title"),):
        getter = getattr(dialog, getter_name, None)
        setter = getattr(dialog, setter_name, None)
        if not callable(getter) or not callable(setter):
            continue
        try:
            current = getter()
        except Exception:
            continue
        if isinstance(current, str) and current:
            try:
                setter(t(current))
            except Exception:
                pass


def install_theme_editor_dialog_i18n(app_module: Any) -> None:
    """Translate dialogs/popovers that are constructed after window startup."""

    Adw = getattr(app_module, "Adw", None)
    Gtk = getattr(app_module, "Gtk", None)
    if Adw is None:
        return

    dialog_classes = []
    for name in ("AlertDialog", "PreferencesDialog"):
        cls = getattr(Adw, name, None)
        if cls is not None:
            dialog_classes.append(cls)

    for cls in dialog_classes:
        if not getattr(cls, "_theme_editor_i18n_present_installed", False):
            original_present = getattr(cls, "present", None)
            if callable(original_present):
                def present_with_i18n(self, *args, __original_present=original_present, **kwargs):
                    _translate_dialog_title(self)
                    translate_widget_tree(self)
                    return __original_present(self, *args, **kwargs)

                try:
                    cls.present = present_with_i18n
                    cls._theme_editor_i18n_present_installed = True
                except Exception:
                    pass

        if not getattr(cls, "_theme_editor_i18n_response_installed", False):
            original_add_response = getattr(cls, "add_response", None)
            if callable(original_add_response):
                def add_response_with_i18n(self, response_id, label, __original_add_response=original_add_response):
                    return __original_add_response(self, response_id, t(str(label)))

                try:
                    cls.add_response = add_response_with_i18n
                    cls._theme_editor_i18n_response_installed = True
                except Exception:
                    pass

    if Gtk is not None:
        window_class = getattr(Gtk, "Window", None)
        if window_class is not None and not getattr(window_class, "_theme_editor_i18n_present_installed", False):
            original_present = getattr(window_class, "present", None)
            if callable(original_present):
                def gtk_window_present_with_i18n(self, *args, __original_present=original_present, **kwargs):
                    translate_widget_tree(self)
                    return __original_present(self, *args, **kwargs)

                try:
                    window_class.present = gtk_window_present_with_i18n
                    window_class._theme_editor_i18n_present_installed = True
                except Exception:
                    pass


def _wrap_method(window_class: type, method_name: str, translator) -> None:
    original = getattr(window_class, method_name, None)
    if not callable(original):
        return
    if getattr(original, "_theme_editor_i18n_wrapper", False):
        return

    def wrapper(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        translator(self, result)
        return result

    wrapper._theme_editor_i18n_wrapper = True
    setattr(window_class, method_name, wrapper)


def install_theme_editor_i18n(window_class: type) -> None:
    """Patch ThemeEditorWindow methods once the class has been created."""

    if getattr(window_class, "_theme_editor_i18n_installed", False):
        return

    app_module = sys.modules.get(window_class.__module__)
    if app_module is not None:
        install_theme_editor_dialog_i18n(app_module)

    original_init = window_class.__init__

    def init_with_i18n(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _translate_static_models(self)
        translate_widget_tree(self)

    init_with_i18n._theme_editor_i18n_wrapper = True
    window_class.__init__ = init_with_i18n

    def translate_result(self, result):
        if result is not None:
            translate_widget_tree(result)
        _translate_static_models(self)
        translate_widget_tree(self)

    for method_name in (
        "build_elements_panel",
        "build_preview_panel",
        "build_properties_panel",
        "build_property_rows",
        "populate_elements",
        "update_elements_summary",
        "update_actions_sensitivity",
        "refresh_preview",
        "open_gradient_effect_editor",
        "open_video_tools",
        "open_video_inspector",
        "open_generated_media_manager",
        "confirm_open_theme_yaml",
    ):
        _wrap_method(window_class, method_name, translate_result)

    original_toast = getattr(window_class, "toast", None)
    if callable(original_toast):
        def toast_with_i18n(self, text, *args, **kwargs):
            return original_toast(self, t(str(text)), *args, **kwargs)

        toast_with_i18n._theme_editor_i18n_wrapper = True
        window_class.toast = toast_with_i18n

    original_error_dialog = getattr(window_class, "error_dialog", None)
    if callable(original_error_dialog):
        def error_dialog_with_i18n(self, heading, body="", *args, **kwargs):
            return original_error_dialog(self, t(str(heading)), body, *args, **kwargs)

        error_dialog_with_i18n._theme_editor_i18n_wrapper = True
        window_class.error_dialog = error_dialog_with_i18n

    window_class._theme_editor_i18n_installed = True


def install_theme_editor_i18n_class_hook() -> None:
    """Install an early hook for theme-editor-gtk.py class creation."""

    global _THEME_EDITOR_HOOK_INSTALLED, _ORIGINAL_BUILD_CLASS
    if _THEME_EDITOR_HOOK_INSTALLED:
        return

    _ORIGINAL_BUILD_CLASS = builtins.__build_class__

    def build_class_with_theme_editor_i18n(func, name, *bases, **kwargs):
        cls = _ORIGINAL_BUILD_CLASS(func, name, *bases, **kwargs)
        if name == "ThemeEditorWindow":
            install_theme_editor_i18n(cls)
        return cls

    builtins.__build_class__ = build_class_with_theme_editor_i18n
    _THEME_EDITOR_HOOK_INSTALLED = True
