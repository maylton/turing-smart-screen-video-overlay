# SPDX-License-Identifier: GPL-3.0-or-later
"""Apply the persistent AMD preference to the Python sensor backend."""

from __future__ import annotations

from library.gpu_selection import load_preference, select_amd_gpu_index


_INSTALLED = False


def install() -> None:
    global _INSTALLED
    if _INSTALLED:
        return

    from library.sensors import sensors_python

    gpu_class = sensors_python.GpuAmd
    original_selector = gpu_class.preferred_linux_gpu_index

    def preferred_linux_gpu_index() -> int:
        api = getattr(sensors_python, "pyamdgpuinfo", None)
        if api is None:
            return original_selector()
        try:
            selected = select_amd_gpu_index(api, load_preference())
        except Exception as exc:
            sensors_python.logger.warning(
                "Could not apply the configured AMD GPU preference: %s",
                exc,
            )
            return original_selector()

        if selected >= 0:
            preference = load_preference()
            sensors_python.logger.info(
                "AMD GPU selection mode=%s requested_index=%s selected_index=%d",
                preference.mode,
                preference.amd_index,
                selected,
            )
            return selected
        return original_selector()

    gpu_class.preferred_linux_gpu_index = staticmethod(preferred_linux_gpu_index)
    gpu_class.selected_index = -1
    _INSTALLED = True
