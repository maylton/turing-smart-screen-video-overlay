# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime translation helpers for GTK frontends.

The active language is selected automatically from the system locale.
For manual testing only, TURING_SMART_SCREEN_LANG can override it, e.g.:

    TURING_SMART_SCREEN_LANG=pt_BR turing-smart-screen
"""

from __future__ import annotations

import locale
import os


def _locale_candidates() -> list[str]:
    values: list[str] = []

    override = os.environ.get("TURING_SMART_SCREEN_LANG")
    if override:
        values.append(override)

    for key in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(key)
        if value:
            values.extend(part for part in value.split(":") if part)

    try:
        current = locale.getlocale()[0]
    except Exception:
        current = None
    if current:
        values.append(current)

    return values


def _normalize_locale(value: str) -> str:
    value = str(value or "").strip()
    value = value.split(".", 1)[0]
    value = value.replace("-", "_")
    return value


def active_language() -> str:
    for candidate in _locale_candidates():
        normalized = _normalize_locale(candidate).lower()
        if normalized.startswith("pt"):
            return "pt_BR"
    return "en"


def active_language_label() -> str:
    return {
        "pt_BR": "Português (Brasil)",
        "en": "English",
    }.get(active_language(), "English")


GTK_SHELL_MESSAGES = (
    "Linux configuration center",
    "Main menu",
    "Open classic interface",
    "About",
    "Navigation",
    "Overview",
    "Themes",
    "Settings",
    "Configuration app",
    "Manage your display, active theme, videos, and monitor process.",
    "Status",
    "Active theme",
    "Monitor process",
    "Connected display",
    "Detection has not run yet",
    "Detect now",
    "Edit theme",
    "Refresh",
    "Turn off display",
    "Stop the monitor process and switch off the LCD backlight",
    "Quick actions",
    "Theme editor",
    "Edit the active theme layout and components.",
    "Video manager",
    "Upload, delete, and play native videos.",
    "Start monitor",
    "Run main.py using the project environment.",
    "Stop monitor",
    "Stop the process started from this window.",
    "Classic configuration",
    "Open the original Tkinter configuration window.",
    "Appearance",
    "Choose the application appearance. The selection is saved for the next session.",
    "Color scheme",
    "Follow system",
    "Light",
    "Dark",
    "Start minimized to tray",
    "Open in the background and keep only the system tray icon visible",
    "Language",
    "Automatic from system locale: {language}",
    "Maintenance",
    "Verify GTK, Python dependencies, project files, and theme YAML files.",
    "Program check",
    "Verify dependencies, project files, themes, and Python syntax",
    "Could not change appearance: {error}",
    "Following system appearance",
    "Light appearance enabled",
    "Dark appearance enabled",
    "Could not save startup preference: {error}",
    "Application will start minimized to tray",
    "Application will open normally",
    "Running program check…",
    "Program check completed",
    "Program check found problems",
    "Close",
    "No active theme",
    "Running",
    "Stopped",
)


TRAY_MESSAGES = (
    "Show window",
    "Hide window",
    "Start screen",
    "Turn off screen",
    "Open theme editor",
    "Open video manager",
    "Quit",
    "Theme: {theme}",
    "not selected",
)


_PT_BR = {
    # App shell / header
    "Linux configuration center": "Central de configuração Linux",
    "Main menu": "Menu principal",
    "Open classic interface": "Abrir interface clássica",
    "About": "Sobre",

    # Navigation
    "Navigation": "Navegação",
    "Overview": "Visão geral",
    "Themes": "Temas",
    "Settings": "Configurações",
    "Configuration app": "Aplicativo de configuração",

    # Overview
    "Manage your display, active theme, videos, and monitor process.": (
        "Gerencie sua tela, tema ativo, vídeos e processo de atualização."
    ),
    "Status": "Status",
    "Active theme": "Tema ativo",
    "Monitor process": "Processo da tela",
    "Connected display": "Tela conectada",
    "Detection has not run yet": "A detecção ainda não foi executada",
    "Detect now": "Detectar agora",
    "Edit theme": "Editar tema",
    "Refresh": "Atualizar",
    "Turn off display": "Desligar tela",
    "Stop the monitor process and switch off the LCD backlight": (
        "Para a atualização e desliga a iluminação da tela"
    ),
    "Quick actions": "Ações rápidas",
    "Theme editor": "Editor de tema",
    "Edit the active theme layout and components.": (
        "Edite o layout e os componentes do tema ativo."
    ),
    "Video manager": "Gerenciador de vídeos",
    "Upload, delete, and play native videos.": (
        "Envie, exclua e reproduza vídeos nativos."
    ),
    "Start monitor": "Iniciar tela",
    "Run main.py using the project environment.": (
        "Executa a tela usando o ambiente do projeto."
    ),
    "Stop monitor": "Parar tela",
    "Stop the process started from this window.": (
        "Para o processo iniciado por esta janela."
    ),
    "Classic configuration": "Configuração clássica",
    "Open the original Tkinter configuration window.": (
        "Abre a janela de configuração original em Tkinter."
    ),

    # Settings
    "Appearance": "Aparência",
    "Choose the application appearance. The selection is saved for the next session.": (
        "Escolha a aparência do aplicativo. A seleção será salva para a próxima sessão."
    ),
    "Color scheme": "Esquema de cores",
    "Follow system": "Seguir sistema",
    "Light": "Claro",
    "Dark": "Escuro",
    "Start minimized to tray": "Iniciar minimizado na bandeja",
    "Open in the background and keep only the system tray icon visible": (
        "Abre em segundo plano e mantém apenas o ícone da bandeja visível"
    ),
    "Language": "Idioma",
    "Automatic from system locale: {language}": (
        "Automático pelo locale do sistema: {language}"
    ),
    "Maintenance": "Manutenção",
    "Verify GTK, Python dependencies, project files, and theme YAML files.": (
        "Verifique GTK, dependências Python, arquivos do projeto e arquivos YAML dos temas."
    ),
    "Program check": "Verificação do programa",
    "Verify dependencies, project files, themes, and Python syntax": (
        "Verifica dependências, arquivos do projeto, temas e sintaxe Python"
    ),

    # Toasts and dialogs
    "Could not change appearance: {error}": "Não foi possível alterar a aparência: {error}",
    "Following system appearance": "Seguindo a aparência do sistema",
    "Light appearance enabled": "Aparência clara ativada",
    "Dark appearance enabled": "Aparência escura ativada",
    "Could not save startup preference: {error}": (
        "Não foi possível salvar a preferência de inicialização: {error}"
    ),
    "Application will start minimized to tray": (
        "O aplicativo iniciará minimizado na bandeja"
    ),
    "Application will open normally": "O aplicativo abrirá normalmente",
    "Running program check…": "Executando verificação do programa…",
    "Program check completed": "Verificação concluída",
    "Program check found problems": "A verificação encontrou problemas",
    "Close": "Fechar",

    # State labels
    "No active theme": "Nenhum tema ativo",
    "Running": "Em execução",
    "Stopped": "Parado",

    # Tray menu
    "Show window": "Mostrar janela",
    "Hide window": "Ocultar janela",
    "Start screen": "Iniciar tela",
    "Turn off screen": "Desligar tela",
    "Open theme editor": "Abrir editor de tema",
    "Open video manager": "Abrir gerenciador de vídeos",
    "Quit": "Sair",
    "Theme: {theme}": "Tema: {theme}",
    "not selected": "não selecionado",
}


_TRANSLATIONS = {
    "pt_BR": _PT_BR,
}


def translation_catalog(language: str = "pt_BR") -> dict[str, str]:
    """Return a copy of the catalog for tests and diagnostics."""
    return dict(_TRANSLATIONS.get(language, {}))


def missing_translations(
    messages: tuple[str, ...] | list[str],
    language: str = "pt_BR",
) -> list[str]:
    """Return stable message keys missing from a translation catalog."""
    catalog = _TRANSLATIONS.get(language, {})
    return [message for message in messages if message not in catalog]


def t(message: str) -> str:
    """Translate a stable English message key for the active runtime language."""
    return _TRANSLATIONS.get(active_language(), {}).get(message, message)


def tr(message: str, **kwargs) -> str:
    """Translate and format a stable English message key."""
    return t(message).format(**kwargs)
