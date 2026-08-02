# SPDX-License-Identifier: GPL-3.0-or-later
"""Stable, renderer-neutral sensor snapshots.

This module deliberately has no dependency on GTK, PIL, the display transport,
or a concrete sensor backend. Existing sensor implementations can be adapted by
supplying small reader callables, while theme engines consume one predictable
JSON-safe payload.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, MutableMapping, Optional


SCHEMA_VERSION = 1
DEFAULT_SECTIONS = (
    "cpu",
    "gpu",
    "memory",
    "disk",
    "network",
    "system",
    "weather",
)


Reader = Callable[[], Any]


def _json_safe(value: Any) -> Any:
    """Convert backend values into deterministic JSON-compatible data."""
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


@dataclass(frozen=True)
class SensorSnapshot:
    """Immutable snapshot delivered to a renderer."""

    schema_version: int
    timestamp: float
    sequence: int
    data: Mapping[str, Any]
    errors: Mapping[str, str]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "data": _json_safe(self.data),
            "errors": dict(self.errors),
        }

    def to_json(self) -> str:
        return json.dumps(
            self.as_dict(),
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        )


class SensorSnapshotCollector:
    """Collect independent sections without allowing one failure to abort all."""

    def __init__(
        self,
        readers: Optional[Mapping[str, Reader]] = None,
        *,
        clock: Callable[[], float] = time.time,
        include_empty_defaults: bool = True,
    ) -> None:
        self._readers: MutableMapping[str, Reader] = dict(readers or {})
        self._clock = clock
        self._sequence = 0
        self._include_empty_defaults = include_empty_defaults

    def register(self, section: str, reader: Reader) -> None:
        normalized = str(section).strip().lower()
        if not normalized:
            raise ValueError("Snapshot section name cannot be empty")
        if not callable(reader):
            raise TypeError("Snapshot reader must be callable")
        self._readers[normalized] = reader

    def unregister(self, section: str) -> None:
        self._readers.pop(str(section).strip().lower(), None)

    def collect(self) -> SensorSnapshot:
        self._sequence += 1
        data: Dict[str, Any] = {}
        errors: Dict[str, str] = {}

        if self._include_empty_defaults:
            data.update({section: {} for section in DEFAULT_SECTIONS})

        for section in sorted(self._readers):
            reader = self._readers[section]
            try:
                result = reader()
                data[section] = _json_safe(result if result is not None else {})
            except Exception as exc:  # isolate backend failures by design
                data.setdefault(section, {})
                errors[section] = f"{type(exc).__name__}: {exc}"

        return SensorSnapshot(
            schema_version=SCHEMA_VERSION,
            timestamp=float(self._clock()),
            sequence=self._sequence,
            data=data,
            errors=errors,
        )


class StaticSnapshotSource:
    """Deterministic source used by previews and tests, never by hardware code."""

    def __init__(self, data: Mapping[str, Any]) -> None:
        self._data = dict(data)

    def readers(self) -> Dict[str, Reader]:
        return {
            section: (lambda value=value: value)
            for section, value in self._data.items()
        }
