# SPDX-License-Identifier: GPL-3.0-or-later
"""Compatibility wrapper for Theme Gallery card polish.

This script is intentionally tiny so it can be executed from the installed app
folder when Python's automatic sitecustomize import is not triggered by the
launcher/runtime environment.
"""

from __future__ import annotations

import sitecustomize  # noqa: F401
