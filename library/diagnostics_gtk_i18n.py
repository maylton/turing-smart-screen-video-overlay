# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime i18n helper for diagnostics GTK surfaces."""

from __future__ import annotations

from library.i18n import active_language


_PT_BR = {
    "Turing Smart Screen Diagnostics": "Diagnóstico da Turing Smart Screen",
    "Diagnostics": "Diagnóstico",
    "Safe display, theme, runtime, and serial report": "Relatório seguro da tela, tema, execução e serial",
    "Refresh diagnostics": "Atualizar diagnóstico",
    "Copy text diagnostics report": "Copiar relatório de diagnóstico em texto",
    "Copy machine-readable diagnostics JSON": "Copiar JSON de diagnóstico legível por máquina",
    "This page reads configuration, theme metadata, monitor process state, and USB descriptors without opening the display serial port.": (
        "Esta página lê configuração, metadados do tema, estado do processo da tela e descritores USB sem abrir a porta serial da tela."
    ),
    "Theme": "Tema",
    "Video": "Vídeo",
    "Runtime": "Execução",
    "Serial": "Serial",
    "Full report": "Relatório completo",
    "Copy this report when filing bugs or comparing display states.": "Copie este relatório ao relatar bugs ou comparar estados da tela.",
    "OK": "OK",
    "Needs attention": "Requer atenção",
    "Diagnostics refreshed": "Diagnóstico atualizado",
    "Diagnostics failed: {error}": "Falha no diagnóstico: {error}",
    "No theme": "Nenhum tema",
    "preview OK": "prévia OK",
    "preview missing": "prévia ausente",
    "Configured": "Configurado",
    "Not configured": "Não configurado",
    "local file OK": "arquivo local OK",
    "local file missing": "arquivo local ausente",
    "video block missing or disabled": "bloco de vídeo ausente ou desativado",
    "Running": "Em execução",
    "Stopped": "Parado",
    "PID {pids}": "PID {pids}",
    "No monitor process detected": "Nenhum processo da tela detectado",
    "UsbMonitor only": "Apenas UsbMonitor",
    "No ttyACM display": "Nenhuma tela ttyACM",
    "UsbMonitor: {devices}": "UsbMonitor: {devices}",
    "none": "nenhum",
    "Clipboard is not available": "A área de transferência não está disponível",
    "Diagnostics copied": "Diagnóstico copiado",
    "Diagnostics JSON copied": "JSON de diagnóstico copiado",
}


def t(message: str) -> str:
    if active_language() == "pt_BR":
        return _PT_BR.get(message, message)
    return message


def tr(message: str, **kwargs) -> str:
    return t(message).format(**kwargs)


def status_text(ok: bool, good: str = "OK", bad: str = "Needs attention") -> str:
    return t(good if ok else bad)
