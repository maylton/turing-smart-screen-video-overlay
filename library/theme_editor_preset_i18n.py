# SPDX-License-Identifier: GPL-3.0-or-later
"""Translations for Theme Editor catalog/preset labels."""

from __future__ import annotations

from library.i18n import active_language


_PT_BR = {
    # Catalog groups
    "Content": "Conteúdo",
    "System": "Sistema",
    "System metrics": "Métricas do sistema",
    "Media": "Mídia",
    "Weather": "Clima",
    "Display": "Tela",
    "Configuration": "Configuração",

    # Content presets
    "Custom text": "Texto personalizado",
    "Static image": "Imagem estática",
    "Custom image": "Imagem personalizada",
    "Background image": "Imagem de fundo",

    # System presets
    "CPU usage": "Uso da CPU",
    "CPU usage % bar + text": "Uso da CPU — barra % + texto",
    "CPU temperature": "Temperatura da CPU",
    "CPU frequency": "Frequência da CPU",
    "RAM usage": "Uso de RAM",
    "RAM usage % bar + text": "Uso de RAM — barra % + texto",
    "Memory usage": "Uso de memória",
    "GPU usage": "Uso da GPU",
    "GPU usage % bar + text": "Uso da GPU — barra % + texto",
    "GPU temperature": "Temperatura da GPU",
    "GPU memory usage": "Uso da memória da GPU",
    "Disk usage": "Uso do disco",
    "Disk used": "Disco usado",
    "Disk free": "Disco livre",
    "Network upload": "Upload da rede",
    "Network download": "Download da rede",
    "Network speed": "Velocidade da rede",
    "Fan speed": "Velocidade da ventoinha",
    "Temperature": "Temperatura",
    "Load": "Carga",
    "Frequency": "Frequência",

    # Element names / variants
    "Percentage": "Percentual",
    "Text": "Texto",
    "Graph": "Gráfico",
    "Radial": "Radial",
    "Line graph": "Gráfico de linha",
    "Video and background": "Vídeo e fundo",
    "Video background": "Fundo de vídeo",
    "Theme preview": "Prévia do tema",

    # Weather / date-like presets, if present in themes
    "Weather temperature": "Temperatura do clima",
    "Weather condition": "Condição do clima",
    "Weather icon": "Ícone do clima",
    "Date": "Data",
    "Time": "Hora",
    "Clock": "Relógio",
}


def t(message: str) -> str:
    if active_language() != "pt_BR" or not isinstance(message, str) or not message:
        return message

    if message in _PT_BR:
        return _PT_BR[message]

    if " — " in message:
        parts = message.split(" — ")
        translated = [_PT_BR.get(part, part) for part in parts]
        if translated != parts:
            return " — ".join(translated)

    return message
