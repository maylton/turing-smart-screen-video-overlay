# SPDX-License-Identifier: GPL-3.0-or-later
"""Translations for Theme Editor catalog/preset labels and property choices."""

from __future__ import annotations

import re

from library.i18n import active_language


_PT_BR = {
    # Catalog groups
    "Content": "Conteúdo",
    "System": "Sistema",
    "System metrics": "Métricas do sistema",
    "Media": "Mídia",
    "Weather": "Clima",
    "Information": "Informações",
    "Network": "Rede",
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
    "Internet upload": "Upload da internet",
    "Internet download": "Download da internet",
    "Ping": "Ping",
    "System uptime": "Tempo ligado do sistema",
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

    # Component preset rows
    "Radial gauge preset": "Preset de medidor radial",
    "Text component preset": "Preset de texto",
    "Text style preset": "Preset de estilo do texto",
    "Choose a preset…": "Escolha um preset…",
    "No gradient configured": "Nenhum degradê configurado",
    "Apply a safe starter layout to this selected component.": "Aplica um layout inicial seguro a este componente selecionado.",
    "Apply values to the current text fields.": "Aplica valores aos campos de texto atuais.",

    # Component preset options
    "Centered label": "Rótulo centralizado",
    "Top-left caption": "Legenda no canto superior esquerdo",
    "Large metric value": "Valor grande da métrica",
    "Centered blue gradient": "Degradê azul centralizado",
    "Warm gradient label": "Rótulo com degradê quente",
    "Neon gradient value": "Valor com degradê neon",
    "Full-screen background": "Fundo em tela cheia",
    "Centered card": "Card centralizado",
    "Small icon": "Ícone pequeno",
    "Horizontal bar with track": "Barra horizontal com trilho",
    "Vertical bar with track": "Barra vertical com trilho",
    "Compact thin bar": "Barra fina compacta",
    "Material warm gradient bar": "Barra Material com degradê quente",
    "Neon glow bar": "Barra neon com brilho",
    "Soft shadow track": "Trilho com sombra suave",
    "Glass blue bar": "Barra azul translúcida",
    "Warning heat bar": "Barra de alerta quente",
    "Clean radial gauge": "Medidor radial limpo",
    "Thick radial gauge": "Medidor radial espesso",
    "Minimal radial arc": "Arco radial minimalista",
    "Dashboard line graph": "Gráfico de linha do painel",
    "Thin sparkline": "Linha fina de tendência",

    # Property keys shown as user-facing rows
    "X": "X",
    "Y": "Y",
    "WIDTH": "Largura",
    "HEIGHT": "Altura",
    "RADIUS": "Raio",
    "FONT": "Fonte",
    "FONT_SIZE": "Tamanho da fonte",
    "FONT_COLOR": "Cor da fonte",
    "BACKGROUND_IMAGE": "Imagem de fundo",
    "BAR_COLOR": "Cor da barra",
    "MIN_VALUE": "Valor mínimo",
    "MAX_VALUE": "Valor máximo",
    "ANGLE_START": "Ângulo inicial",
    "ANGLE_END": "Ângulo final",
    "ANGLE_STEPS": "Etapas do ângulo",
    "ANGLE_SEP": "Separação do ângulo",
    "SHOW": "Mostrar",
    "SHOW_UNIT": "Mostrar unidade",
    "INTERVAL": "Intervalo",
    "PATH": "Caminho",
    "MODE": "Modo",
    "ENABLED": "Ativado",
    "OVERLAY": "Sobreposição",
    "PREVIEW_BACKGROUND": "Fundo da prévia",
    "LOCAL_PATH": "Caminho local",
    "BACKGROUND_FRAME_TIME": "Tempo do frame de fundo",
    "ALIGN": "Alinhamento",
    "ANCHOR": "Âncora",

    # Property descriptions / values
    "Choose a font from res/fonts.": "Escolha uma fonte em res/fonts.",
    "Choose an image from this theme folder.": "Escolha uma imagem da pasta do tema.",
    "Choose horizontal text alignment.": "Escolha o alinhamento horizontal do texto.",
    "Choose the text anchor point used by Pillow.": "Escolha o ponto de âncora do texto usado pelo Pillow.",
    "Choose an image from this theme folder.": "Escolha uma imagem da pasta do tema.",
    "Disabled": "Desativado",
    "Current": "Atual",
    "Top left": "Superior esquerdo",
    "Top center": "Superior central",
    "Top right": "Superior direito",
    "Middle left": "Meio esquerdo",
    "Middle center": "Centro",
    "Middle right": "Meio direito",
    "Bottom left": "Inferior esquerdo",
    "Bottom center": "Inferior central",
    "Bottom right": "Inferior direito",
    "Left": "Esquerda",
    "Center": "Centro",
    "Right": "Direita",
    "native": "nativo",
    "Native": "Nativo",

    # Weather / date-like presets, if present in themes
    "Weather temperature": "Temperatura do clima",
    "Weather condition": "Condição do clima",
    "Weather icon": "Ícone do clima",
    "Date": "Data",
    "Time": "Hora",
    "Clock": "Relógio",
}


def _dynamic_pt(message: str) -> str | None:
    if message.startswith("Current — "):
        return "Atual — " + message.removeprefix("Current — ")

    match = re.fullmatch(r"(\d+) steps", message)
    if match:
        count = int(match.group(1))
        return f"{count} {'passo' if count == 1 else 'passos'}"

    return None


def t(message: str) -> str:
    if active_language() != "pt_BR" or not isinstance(message, str) or not message:
        return message

    dynamic = _dynamic_pt(message)
    if dynamic is not None:
        return dynamic

    if message in _PT_BR:
        return _PT_BR[message]

    if " — " in message:
        parts = message.split(" — ")
        translated = [_PT_BR.get(part, part) for part in parts]
        if translated != parts:
            return " — ".join(translated)

    return message
