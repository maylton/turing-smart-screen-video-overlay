# SPDX-License-Identifier: GPL-3.0-or-later
"""Catalog and local runtime for editor-generated HTML sensor widgets."""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Iterable

from library.theme_engine import ThemeValidationError


WIDGET_RUNTIME_FILENAME = "theme-editor-widgets.js"
WIDGET_BLOCK_START = "<!-- turing-html-editor-widgets:start -->"
WIDGET_BLOCK_END = "<!-- turing-html-editor-widgets:end -->"
_WIDGET_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


@dataclass(frozen=True)
class HtmlWidgetComponent:
    key: str
    label: str
    binding: str
    formatter: str
    sample: str
    width: int = 120
    height: int = 38
    kind: str = "text"


HTML_WIDGET_COMPONENTS = (
    HtmlWidgetComponent("cpu-temperature", "Temperatura da CPU", "cpu.temperature", "temperature", "49°C"),
    HtmlWidgetComponent("gpu-temperature", "Temperatura da GPU", "gpu.temperature", "temperature", "58°C"),
    HtmlWidgetComponent("cpu-usage", "Uso da CPU", "cpu.usage", "percent", "62%"),
    HtmlWidgetComponent("gpu-usage", "Uso da GPU", "gpu.usage", "percent", "71%"),
    HtmlWidgetComponent("ram-usage", "Uso da RAM", "memory.usage", "percent", "45%"),
    HtmlWidgetComponent("ram-used", "Memória utilizada", "memory.used", "gigabytes", "14.5 GB", 140, 38),
    HtmlWidgetComponent("cpu-load", "Carga da CPU", "cpu.load.0", "load", "1.25"),
    HtmlWidgetComponent("disk-usage", "Uso do disco", "disk.usage", "percent", "54%"),
    HtmlWidgetComponent("weather-temperature", "Temperatura do clima", "weather.temperature", "text", "24.0°C", 140, 38),
    HtmlWidgetComponent("weather-condition", "Condição do clima", "weather.description", "text", "Parcialmente nublado", 220, 38),
    HtmlWidgetComponent("time", "Hora", "system.time", "time", "10:32", 140, 48),
    HtmlWidgetComponent("date", "Data", "$timestamp", "date", "02/08/2026", 160, 38),
    HtmlWidgetComponent(
        "cpu-usage-bar",
        "Barra · Uso da CPU",
        "cpu.usage",
        "bar-percent",
        "62",
        160,
        12,
        "bar",
    ),
    HtmlWidgetComponent(
        "gpu-usage-bar",
        "Barra · Uso da GPU",
        "gpu.usage",
        "bar-percent",
        "71",
        160,
        12,
        "bar",
    ),
    HtmlWidgetComponent(
        "ram-usage-bar",
        "Barra · Uso da RAM",
        "memory.usage",
        "bar-percent",
        "45",
        160,
        12,
        "bar",
    ),
    HtmlWidgetComponent(
        "disk-usage-bar",
        "Barra · Uso do disco",
        "disk.usage",
        "bar-percent",
        "54",
        160,
        12,
        "bar",
    ),
    HtmlWidgetComponent(
        "cpu-temperature-bar",
        "Barra · Temperatura da CPU",
        "cpu.temperature",
        "bar-percent",
        "49",
        160,
        12,
        "bar",
    ),
    HtmlWidgetComponent(
        "gpu-temperature-bar",
        "Barra · Temperatura da GPU",
        "gpu.temperature",
        "bar-percent",
        "58",
        160,
        12,
        "bar",
    ),
)

_COMPONENTS_BY_KEY = {component.key: component for component in HTML_WIDGET_COMPONENTS}


def html_widget_components() -> tuple[HtmlWidgetComponent, ...]:
    return HTML_WIDGET_COMPONENTS


def get_html_widget_component(key: str) -> HtmlWidgetComponent:
    try:
        return _COMPONENTS_BY_KEY[str(key)]
    except KeyError as exc:
        raise ThemeValidationError(f"unsupported HTML widget component: {key}") from exc


def validate_widget_id(widget_id: str) -> str:
    value = str(widget_id).strip()
    if not _WIDGET_ID.fullmatch(value):
        raise ThemeValidationError(f"invalid generated HTML widget id: {widget_id}")
    return value


def next_widget_id(component_key: str, existing_ids: Iterable[str]) -> str:
    component = get_html_widget_component(component_key)
    existing = {str(value) for value in existing_ids}
    prefix = f"turing-{component.key}"
    for number in range(1, 10_000):
        candidate = f"{prefix}-{number}"
        if candidate not in existing:
            return candidate
    raise ThemeValidationError(f"too many generated widgets for {component.label}")


def generated_widget_markup(widget_id: str, component_key: str) -> str:
    widget_id = validate_widget_id(widget_id)
    component = get_html_widget_component(component_key)
    attributes = {
        "id": widget_id,
        "class": "turing-editor-widget",
        "data-turing-overlay": "",
        "data-turing-generated-widget": "",
        "data-turing-component": component.key,
        "data-turing-binding": component.binding,
        "data-turing-format": component.formatter,
        "data-turing-kind": component.kind,
    }
    if component.kind == "bar":
        attributes.update(
            {
                "role": "progressbar",
                "aria-valuemin": "0",
                "aria-valuemax": "100",
                "aria-valuenow": component.sample,
            }
        )
    rendered = " ".join(
        name if value == "" else f'{name}="{html.escape(value, quote=True)}"'
        for name, value in attributes.items()
    )
    content = (
        '<div data-turing-bar-fill aria-hidden="true"></div>'
        if component.kind == "bar"
        else html.escape(component.sample)
    )
    return f"    <div {rendered}>{content}</div>"


def render_generated_widget_block(
    widgets: Iterable[tuple[str, str]],
) -> str:
    values = tuple(widgets)
    if not values:
        return ""
    lines = [WIDGET_BLOCK_START, '  <div id="turing-editor-widgets">']
    lines.extend(generated_widget_markup(widget_id, key) for widget_id, key in values)
    lines.extend(
        [
            "  </div>",
            f'  <script src="{WIDGET_RUNTIME_FILENAME}"></script>',
            WIDGET_BLOCK_END,
        ]
    )
    return "\n".join(lines)


_WIDGET_BLOCK_RE = re.compile(
    r"\s*" + re.escape(WIDGET_BLOCK_START) + r".*?" + re.escape(WIDGET_BLOCK_END) + r"\s*",
    re.DOTALL,
)


def update_generated_widget_block(
    source: str,
    widgets: Iterable[tuple[str, str]],
) -> str:
    cleaned = _WIDGET_BLOCK_RE.sub("", str(source))
    block = render_generated_widget_block(widgets)
    if not block:
        return cleaned
    closing_body = re.search(r"</body\s*>", cleaned, re.IGNORECASE)
    if closing_body is None:
        raise ThemeValidationError("HTML theme entrypoint must contain </body>")
    prefix = cleaned[: closing_body.start()].rstrip()
    suffix = cleaned[closing_body.start() :]
    return f"{prefix}\n{block}\n{suffix}"


class _GeneratedWidgetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []

    def handle_starttag(self, _tag, attrs) -> None:
        values = {str(name).lower(): value for name, value in attrs}
        if "data-turing-generated-widget" not in values:
            return
        widget_id = str(values.get("id") or "").strip()
        if _WIDGET_ID.fullmatch(widget_id):
            self.ids.append(widget_id)


def generated_widget_ids(source: str) -> tuple[str, ...]:
    parser = _GeneratedWidgetParser()
    parser.feed(str(source))
    return tuple(parser.ids)


def render_widget_runtime_script() -> str:
    """Return a standalone local script that chains the theme update bridge."""

    return r"""(() => {
  if (window.__turingGeneratedWidgetsInstalled) return;
  window.__turingGeneratedWidgetsInstalled = true;

  const valueAt = (snapshot, path) => {
    if (path === '$timestamp') return snapshot.timestamp;
    let value = snapshot.data || {};
    for (const part of String(path || '').split('.')) {
      if (value === null || value === undefined) return null;
      value = value[part];
    }
    return value;
  };
  const finite = value => {
    if (value === null || value === undefined || value === '') return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };
  const cssNumber = value => {
    const number = Number.parseFloat(String(value ?? ''));
    return Number.isFinite(number) ? number : null;
  };
  const positionInViewport = (element, targetX, targetY) => {
    if (!element) return;
    const x = finite(targetX);
    const y = finite(targetY);
    if (x === null || y === null) return;
    element.style.setProperty('--turing-editor-x', `${x}px`, 'important');
    element.style.setProperty('--turing-editor-y', `${y}px`, 'important');
    element.style.setProperty('left', `${x}px`, 'important');
    element.style.setProperty('top', `${y}px`, 'important');
    // A transformed ancestor becomes the containing block even for fixed
    // descendants. Correct its viewport offset without changing the theme's
    // surrounding layout.
    for (let attempt = 0; attempt < 3; attempt += 1) {
      const rect = element.getBoundingClientRect();
      const dx = x - rect.left;
      const dy = y - rect.top;
      if (Math.abs(dx) < 0.1 && Math.abs(dy) < 0.1) break;
      const style = getComputedStyle(element);
      const left = cssNumber(style.left) || 0;
      const top = cssNumber(style.top) || 0;
      element.style.setProperty('left', `${left + dx}px`, 'important');
      element.style.setProperty('top', `${top + dy}px`, 'important');
    }
  };
  const normalizeLayout = () => {
    document.querySelectorAll('[data-turing-overlay]').forEach(element => {
      const style = getComputedStyle(element);
      const x = cssNumber(style.getPropertyValue('--turing-editor-x'));
      const y = cssNumber(style.getPropertyValue('--turing-editor-y'));
      if (x !== null && y !== null) positionInViewport(element, x, y);
    });
  };
  window.__turingPositionEditorElement = positionInViewport;
  window.__turingNormalizeEditorLayout = normalizeLayout;
  const formatted = (value, format, snapshot) => {
    const number = finite(value);
    if (format === 'temperature') return number === null ? '--°C' : `${Math.round(number)}°C`;
    if (format === 'percent') return number === null ? '--%' : `${Math.round(Math.max(0, Math.min(100, number)))}%`;
    if (format === 'gigabytes') return number === null ? '-- GB' : `${number.toFixed(1)} GB`;
    if (format === 'load') return number === null ? '--' : number.toFixed(2);
    if (format === 'time') {
      const supplied = String(value || '').trim();
      if (supplied) return supplied.slice(0, 5);
      const date = new Date((finite(snapshot.timestamp) || Date.now() / 1000) * 1000);
      return date.toLocaleTimeString('pt-BR', {hour: '2-digit', minute: '2-digit', hour12: false});
    }
    if (format === 'date') {
      const date = new Date((number || Date.now() / 1000) * 1000);
      return date.toLocaleDateString('pt-BR');
    }
    const text = String(value === null || value === undefined ? '' : value).trim();
    return text || '--';
  };
  const updateGenerated = snapshot => {
    document.querySelectorAll('[data-turing-generated-widget]').forEach(element => {
      const value = valueAt(snapshot, element.dataset.turingBinding);
      if (element.dataset.turingKind === 'bar') {
        const number = finite(value);
        const percentage = number === null ? 0 : Math.max(0, Math.min(100, number));
        let fill = element.querySelector('[data-turing-bar-fill]');
        if (!fill) {
          fill = document.createElement('div');
          fill.setAttribute('data-turing-bar-fill', '');
          fill.setAttribute('aria-hidden', 'true');
          element.replaceChildren(fill);
        }
        fill.style.setProperty('width', `${percentage}%`, 'important');
        if (number === null) {
          element.removeAttribute('aria-valuenow');
          element.setAttribute('aria-valuetext', 'indisponível');
        } else {
          element.setAttribute('aria-valuenow', String(Math.round(percentage)));
          element.removeAttribute('aria-valuetext');
        }
        return;
      }
      element.textContent = formatted(value, element.dataset.turingFormat, snapshot);
    });
  };
  window.__turingUpdateGeneratedWidgets = updateGenerated;

  window.TuringTheme = window.TuringTheme || {};
  const originalUpdate = typeof window.TuringTheme.update === 'function'
    ? window.TuringTheme.update.bind(window.TuringTheme)
    : null;
  window.TuringTheme.update = snapshot => {
    if (originalUpdate) originalUpdate(snapshot);
    normalizeLayout();
    updateGenerated(snapshot || {});
  };
  normalizeLayout();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', normalizeLayout, {once: true});
  }
})();
"""
