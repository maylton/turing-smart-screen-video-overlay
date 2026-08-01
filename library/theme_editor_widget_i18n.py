# SPDX-License-Identifier: GPL-3.0-or-later
"""Disabled Theme Editor widget monkeypatch entry point.

The inline Theme Editor is still localized by explicit post-build widget-tree
translation. This module intentionally does not monkeypatch GTK/Libadwaita
classes anymore because global constructor/dropdown patches can corrupt complex
Theme Editor surfaces.
"""

from __future__ import annotations


def install() -> None:
    """Keep the historical startup call safe and side-effect free."""

    return None
