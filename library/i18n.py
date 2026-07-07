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


def _language_for_locale(value: str) -> str:
    normalized = _normalize_locale(value).lower()
    if normalized.startswith("pt"):
        return "pt_BR"
    return "en"


def active_language() -> str:
    override = os.environ.get("TURING_SMART_SCREEN_LANG")
    if override:
        return _language_for_locale(override)

    for candidate in _locale_candidates():
        if _language_for_locale(candidate) == "pt_BR":
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
    "Start application minimized to tray",
    "Controls only the GTK window. It does not start the display monitor.",
    "Open in the background and keep only the system tray icon visible",
    "Language",
    "Automatic from system locale: {language}",
    "Runtime",
    "The monitor owns the display connection exclusively while it is running.",
    "Start monitor automatically",
    "Start main.py when this application opens. Keep this disabled to start the monitor manually.",
    "Maintenance",
    "Verify GTK, Python dependencies, project files, and theme YAML files.",
    "Program check",
    "Verify dependencies, project files, themes, and Python syntax",
    "Could not change appearance: {error}",
    "Following system appearance",
    "Light appearance enabled",
    "Dark appearance enabled",
    "Could not save startup preference: {error}",
    "Could not save monitor startup preference: {error}",
    "Application will start minimized to tray",
    "Application will open normally",
    "Monitor will start with the application",
    "Monitor will be started manually",
    "No saved theme to start automatically",
    "Monitor is already running",
    "Monitor is starting",
    "Monitor is not running",
    "Monitor stop is already in progress",
    "Stopping monitor…",
    "Turning off display…",
    "Another runtime operation is already in progress",
    "Running program check…",
    "Program check completed",
    "Program check found problems",
    "Close",
    "No active theme",
    "Running",
    "Stopped",
)


MAIN_APP_POLISH_MESSAGES = (
    "Control the active theme, display state, video overlay, and monitor process from one place.",
    "Refresh status and preview",
    "Theme",
    "Monitor",
    "Display",
    "Edit theme",
    "Open the active theme in the Theme Editor.",
    "Sync video",
    "Sync the active theme video to the display",
    "Apply + Start",
    "Apply, sync video, then start the monitor",
    "Gallery",
    "Open the theme gallery to browse, import, edit, or manage themes.",
    "Videos",
    "Open the video manager to upload, delete, or inspect display videos.",
    "Turn off",
    "Stop the monitor and turn off the physical display safely.",
    "Choose a compatible theme from the gallery to begin.",
    "CURRENT",
    "NO THEME",
    "VIDEO",
    "STATIC",
    "DISPLAY",
    "TURZX import hints detected",
    "Native video configured",
    "Ready",
    "Busy",
    "Starting",
    "Monitor owns the display",
    "Display lock is owned",
    "Process launched from this window",
    "Display is free",
    "Unknown",
    "display",
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
    "Start application minimized to tray": "Iniciar aplicativo minimizado na bandeja",
    "Controls only the GTK window. It does not start the display monitor.": (
        "Controla apenas a janela GTK. Não inicia a atualização da tela."
    ),
    "Open in the background and keep only the system tray icon visible": (
        "Abre em segundo plano e mantém apenas o ícone da bandeja visível"
    ),
    "Language": "Idioma",
    "Automatic from system locale: {language}": (
        "Automático pelo locale do sistema: {language}"
    ),
    "Runtime": "Execução",
    "The monitor owns the display connection exclusively while it is running.": (
        "Enquanto está em execução, o monitor usa a conexão da tela com exclusividade."
    ),
    "Start monitor automatically": "Iniciar tela automaticamente",
    "Start main.py when this application opens. Keep this disabled to start the monitor manually.": (
        "Inicia o main.py quando este aplicativo abre. Mantenha desativado para iniciar manualmente."
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
    "Could not save monitor startup preference: {error}": (
        "Não foi possível salvar a preferência de inicialização da tela: {error}"
    ),
    "Application will start minimized to tray": (
        "O aplicativo iniciará minimizado na bandeja"
    ),
    "Application will open normally": "O aplicativo abrirá normalmente",
    "Monitor will start with the application": "A tela iniciará junto com o aplicativo",
    "Monitor will be started manually": "A tela será iniciada manualmente",
    "No saved theme to start automatically": "Nenhum tema salvo para iniciar automaticamente",
    "Monitor is already running": "A tela já está em execução",
    "Monitor is starting": "A tela está iniciando",
    "Monitor is not running": "A tela não está em execução",
    "Monitor stop is already in progress": "A parada da tela já está em andamento",
    "Stopping monitor…": "Parando tela…",
    "Turning off display…": "Desligando tela…",
    "Another runtime operation is already in progress": "Outra operação de execução já está em andamento",
    "Running program check…": "Executando verificação do programa…",
    "Program check completed": "Verificação concluída",
    "Program check found problems": "A verificação encontrou problemas",
    "Close": "Fechar",

    # State labels
    "No active theme": "Nenhum tema ativo",
    "Running": "Em execução",
    "Stopped": "Parado",

    # Dashboard polish
    "Control the active theme, display state, video overlay, and monitor process from one place.": (
        "Controle tema ativo, estado da tela, vídeo e processo de atualização em um só lugar."
    ),
    "Refresh status and preview": "Atualizar status e prévia",
    "Theme": "Tema",
    "Monitor": "Tela",
    "Display": "Display",
    "Open the active theme in the Theme Editor.": "Abre o tema ativo no Editor de Tema.",
    "Sync video": "Sincronizar vídeo",
    "Sync the active theme video to the display": "Sincroniza o vídeo do tema ativo com a tela",
    "Apply + Start": "Aplicar + Iniciar",
    "Apply, sync video, then start the monitor": "Aplica, sincroniza o vídeo e inicia a tela",
    "Gallery": "Galeria",
    "Open the theme gallery to browse, import, edit, or manage themes.": (
        "Abre a galeria para navegar, importar, editar ou gerenciar temas."
    ),
    "Videos": "Vídeos",
    "Open the video manager to upload, delete, or inspect display videos.": (
        "Abre o gerenciador para enviar, excluir ou inspecionar vídeos da tela."
    ),
    "Turn off": "Desligar",
    "Stop the monitor and turn off the physical display safely.": (
        "Para a atualização e desliga a tela física com segurança."
    ),
    "Choose a compatible theme from the gallery to begin.": (
        "Escolha um tema compatível na galeria para começar."
    ),
    "CURRENT": "ATUAL",
    "NO THEME": "SEM TEMA",
    "VIDEO": "VÍDEO",
    "STATIC": "ESTÁTICO",
    "DISPLAY": "DISPLAY",
    "TURZX import hints detected": "Dicas de importação TURZX detectadas",
    "Native video configured": "Vídeo nativo configurado",
    "Ready": "Pronto",
    "Busy": "Ocupado",
    "Starting": "Iniciando",
    "Monitor owns the display": "A tela está em uso pelo monitor",
    "Display lock is owned": "A conexão da tela está em uso",
    "Process launched from this window": "Processo iniciado por esta janela",
    "Display is free": "A tela está livre",
    "Unknown": "Desconhecido",
    "display": "display",

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
