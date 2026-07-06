# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility shim for the old dashboard-polish module name.

The implementation moved to ``library.main_app_ui_integration``. Keep this thin
bridge temporarily so installed/test loaders that still import the old module do
not break while the Main App PR is being consolidated.
"""

from __future__ import annotations

from library.main_app_ui_integration import install_main_app_dashboard_polish

__all__ = ["install_main_app_dashboard_polish"]
