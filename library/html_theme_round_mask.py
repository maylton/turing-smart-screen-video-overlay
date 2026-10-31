# SPDX-License-Identifier: GPL-3.0-or-later
"""Preview mask for round displays in the HTML theme editor.

Square Rev. C panels (2.1" and 2.8") are round: everything outside the
inscribed circle is cut off on the device. The mask dims that area, draws
center guides and outlines overlay elements that reach past the circle.
"""

from __future__ import annotations

import json

# Corners closer than this to the circle are not reported: text boxes are
# usually wider than their glyphs.
OUTSIDE_TOLERANCE_PX = 6


def is_probably_round(width: int, height: int) -> bool:
    return int(width) == int(height)


def round_mask_script(width: int, height: int) -> str:
    """Install ``window.__turingEditorSetRoundMask`` in the preview page."""
    config = json.dumps(
        {
            "width": int(width),
            "height": int(height),
            "tolerance": OUTSIDE_TOLERANCE_PX,
        }
    )
    return f"""
(() => {{
  if (window.__turingEditorSetRoundMask) return;
  const config = {config};
  const cx = config.width / 2;
  const cy = config.height / 2;
  const radius = Math.min(config.width, config.height) / 2;
  let timer = null;
  let flagged = [];

  const mask = document.createElement('div');
  mask.id = '__turing-editor-round-mask';
  const lines = 'linear-gradient(rgba(102,224,255,.35), rgba(102,224,255,.35))';
  Object.entries({{
    position: 'fixed', left: '0', top: '0',
    width: config.width + 'px', height: config.height + 'px',
    pointerEvents: 'none', zIndex: '2147483646', display: 'none',
    background: [
      lines + ' center / 1px 100% no-repeat',
      lines + ' center / 100% 1px no-repeat',
      'radial-gradient(circle ' + radius + 'px at 50% 50%, transparent 99.4%,'
        + ' rgba(102,224,255,.8) 99.6%, rgba(0,0,0,.6) 100%)'
    ].join(', ')
  }}).forEach(([name, value]) => mask.style.setProperty(
    name.replace(/[A-Z]/g, character => '-' + character.toLowerCase()),
    value,
    'important'
  ));
  document.documentElement.appendChild(mask);

  const outside = element => {{
    const rect = element.getBoundingClientRect();
    if (!rect.width || !rect.height) return false;
    const limit = radius + config.tolerance;
    return [[rect.left, rect.top], [rect.right, rect.top],
            [rect.left, rect.bottom], [rect.right, rect.bottom]]
      .some(([x, y]) => Math.hypot(x - cx, y - cy) > limit);
  }};
  // Flags are drawn inside the mask so theme elements are never restyled.
  const clearFlags = () => {{
    mask.replaceChildren();
    flagged = [];
  }};
  const refresh = () => {{
    clearFlags();
    flagged = [...document.querySelectorAll('[data-turing-overlay]')]
      .filter(element => element.id && outside(element));
    for (const element of flagged) {{
      const rect = element.getBoundingClientRect();
      const box = document.createElement('div');
      Object.entries({{
        position: 'absolute', left: rect.left + 'px', top: rect.top + 'px',
        width: rect.width + 'px', height: rect.height + 'px',
        border: '2px dashed #ff9f43', boxSizing: 'border-box'
      }}).forEach(([name, value]) => box.style.setProperty(
        name.replace(/[A-Z]/g, character => '-' + character.toLowerCase()),
        value
      ));
      mask.appendChild(box);
    }}
  }};

  window.__turingEditorSetRoundMask = enabled => {{
    mask.style.setProperty('display', enabled ? 'block' : 'none', 'important');
    if (timer !== null) {{
      clearInterval(timer);
      timer = null;
    }}
    if (enabled) {{
      refresh();
      timer = setInterval(refresh, 400);
    }} else {{
      clearFlags();
    }}
    return flagged.map(element => element.id);
  }};
}})();
"""
