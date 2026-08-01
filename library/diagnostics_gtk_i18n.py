# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime i18n helper for diagnostics GTK surfaces."""

from __future__ import annotations

from library.i18n import active_language


_PT_BR = {
    "Turing Smart Screen Diagnostics": "Diagnóstico da Turing Smart Screen",
    "Diagnostics": "Diagnóstico",
    "Safe display, theme, runtime, and serial report": "Relatório seguro da tela, tema, execução e serial",
    "Safe display, theme, runtime, and serial report. This page does not open the display serial port.": (
        "Relatório seguro da tela, tema, execução e serial. Esta página não abre a porta serial da tela."
    ),
    "Back to Settings": "Voltar para Configurações",
    "Return to Settings": "Retornar para Configurações",
    "Refresh diagnostics": "Atualizar diagnóstico",
    "Copy text diagnostics report": "Copiar relatório de diagnóstico em texto",
    "Copy machine-readable diagnostics JSON": "Copiar JSON de diagnóstico legível por máquina",
    "Copy diagnostics report": "Copiar relatório de diagnóstico",
    "Copy diagnostics JSON": "Copiar JSON de diagnóstico",
    "This page reads configuration, theme metadata, monitor process state, and USB descriptors without opening the display serial port.": (
        "Esta página lê configuração, metadados do tema, estado do processo da tela e descritores USB sem abrir a porta serial da tela."
    ),
    "Display state": "Estado da tela",
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
    "Busy": "Ocupada",
    "Ready": "Pronta",
    "Starting": "Iniciando",
    "Disconnected": "Desconectada",
    "Unknown": "Desconhecido",
    "PID {pids}": "PID {pids}",
    "Device(s): {devices}": "Dispositivo(s): {devices}",
    "Owner PID(s): {pids}": "PID(s) proprietário(s): {pids}",
    "No monitor process detected": "Nenhum processo da tela detectado",
    "UsbMonitor only": "Apenas UsbMonitor",
    "No ttyACM display": "Nenhuma tela ttyACM",
    "UsbMonitor: {devices}": "UsbMonitor: {devices}",
    "none": "nenhum",
    "The monitor owns the display channel.": "O monitor controla o canal da tela.",
    "The display channel is owned by another application operation.": (
        "O canal da tela está sendo usado por outra operação do aplicativo."
    ),
    "A monitor process was found without current lock metadata.": (
        "Um processo do monitor foi encontrado sem metadados atuais de bloqueio."
    ),
    "The serial device is open outside the application runtime lock.": (
        "O dispositivo serial está aberto fora do bloqueio de execução do aplicativo."
    ),
    "The display serial device is ready.": "O dispositivo serial da tela está pronto.",
    "UsbMonitor is present while the ttyACM display device is still appearing.": (
        "O UsbMonitor está presente enquanto o dispositivo ttyACM da tela ainda está sendo criado."
    ),
    "Serial enumeration failed, so the display state is unknown.": (
        "A enumeração serial falhou; portanto, o estado da tela é desconhecido."
    ),
    "No supported display serial descriptor was found.": (
        "Nenhum descritor serial de tela compatível foi encontrado."
    ),
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
