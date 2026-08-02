# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-field sensor update cadence for renderer-neutral snapshots."""

from __future__ import annotations

import copy
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, MutableMapping, Optional, Tuple

from library.sensor_snapshot import SensorSnapshot


_PATH_SEGMENT = r"[A-Za-z0-9_-]+"
_DATA_PATH_RE = re.compile(rf"^{_PATH_SEGMENT}(?:\.{_PATH_SEGMENT})*(?:\.\*)?$")
_METADATA_PATHS = {"$sequence", "$timestamp"}


@dataclass(frozen=True)
class SensorUpdatePolicy:
    """Default and path-specific minimum update intervals in seconds."""

    default_interval: float
    overrides: Tuple[Tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if self.default_interval <= 0:
            raise ValueError("default sensor update interval must be greater than zero")
        seen = set()
        for path, interval in self.overrides:
            validate_update_path(path)
            if path in seen:
                raise ValueError(f"duplicate sensor update path: {path}")
            if interval <= 0:
                raise ValueError(
                    f"sensor update interval for {path!r} must be greater than zero"
                )
            seen.add(path)

    @property
    def interval_map(self) -> Dict[str, float]:
        return dict(self.overrides)

    def interval_for(self, path: str) -> float:
        normalized = str(path).strip()
        intervals = self.interval_map
        if normalized in intervals:
            return intervals[normalized]
        if normalized.startswith("$"):
            return self.default_interval

        parts = normalized.split(".")
        for length in range(len(parts) - 1, 0, -1):
            wildcard = ".".join(parts[:length]) + ".*"
            if wildcard in intervals:
                return intervals[wildcard]
        return self.default_interval


def validate_update_path(path: str) -> str:
    normalized = str(path or "").strip()
    if normalized in _METADATA_PATHS:
        return normalized
    if not _DATA_PATH_RE.fullmatch(normalized):
        raise ValueError(
            "sensor update paths must be dot-separated data fields, a trailing "
            "wildcard such as 'gpu.*', or one of '$sequence'/'$timestamp'"
        )
    return normalized


def parse_sensor_update_policy(
    raw: Any,
    *,
    fallback_interval: float,
) -> SensorUpdatePolicy:
    """Parse ``dataUpdateIntervals`` from a theme manifest."""
    fallback = float(fallback_interval)
    if fallback <= 0:
        raise ValueError("fallback sensor update interval must be greater than zero")
    if raw is None:
        return SensorUpdatePolicy(default_interval=fallback)
    if not isinstance(raw, Mapping):
        raise ValueError("dataUpdateIntervals must be an object")

    default = raw.get("default", fallback)
    try:
        default_interval = float(default)
    except (TypeError, ValueError) as exc:
        raise ValueError("dataUpdateIntervals.default must be a number") from exc
    if default_interval <= 0:
        raise ValueError(
            "dataUpdateIntervals.default must be greater than zero"
        )

    overrides = []
    for raw_path, raw_interval in raw.items():
        path = str(raw_path).strip()
        if path == "default":
            continue
        validate_update_path(path)
        try:
            interval = float(raw_interval)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"dataUpdateIntervals.{path} must be a number"
            ) from exc
        if interval <= 0:
            raise ValueError(
                f"dataUpdateIntervals.{path} must be greater than zero"
            )
        overrides.append((path, interval))

    return SensorUpdatePolicy(
        default_interval=default_interval,
        overrides=tuple(sorted(overrides)),
    )


def _flatten_data(value: Any, prefix: str = ""):
    if isinstance(value, Mapping) and value:
        for key in sorted(value, key=lambda item: str(item)):
            child = f"{prefix}.{key}" if prefix else str(key)
            yield from _flatten_data(value[key], child)
        return
    if prefix:
        yield prefix, copy.deepcopy(value)


def _set_path(root: MutableMapping[str, Any], path: str, value: Any) -> None:
    parts = path.split(".")
    cursor: MutableMapping[str, Any] = root
    for part in parts[:-1]:
        existing = cursor.get(part)
        if not isinstance(existing, MutableMapping):
            existing = {}
            cursor[part] = existing
        cursor = existing
    cursor[parts[-1]] = copy.deepcopy(value)


class SensorUpdateScheduler:
    """Retain values until their manifest-defined update interval expires."""

    def __init__(
        self,
        policy: SensorUpdatePolicy,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.policy = policy
        self._clock = clock
        self.reset()

    def reset(self) -> None:
        self._cached_data: Dict[str, Any] = {}
        self._last_updated: Dict[str, float] = {}
        self._cached_sequence: Optional[int] = None
        self._cached_timestamp: Optional[float] = None
        self._schema_version = 1
        self._errors: Dict[str, str] = {}

    def _is_due(self, path: str, now: float) -> bool:
        previous = self._last_updated.get(path)
        if previous is None:
            return True
        return now - previous >= self.policy.interval_for(path)

    def apply(self, snapshot: SensorSnapshot) -> SensorSnapshot:
        now = float(self._clock())
        self._schema_version = int(snapshot.schema_version)
        self._errors = dict(snapshot.errors)

        for path, value in _flatten_data(snapshot.data):
            if self._is_due(path, now):
                _set_path(self._cached_data, path, value)
                self._last_updated[path] = now

        if self._is_due("$sequence", now):
            self._cached_sequence = int(snapshot.sequence)
            self._last_updated["$sequence"] = now
        if self._is_due("$timestamp", now):
            self._cached_timestamp = float(snapshot.timestamp)
            self._last_updated["$timestamp"] = now

        if self._cached_sequence is None:
            self._cached_sequence = int(snapshot.sequence)
        if self._cached_timestamp is None:
            self._cached_timestamp = float(snapshot.timestamp)

        return SensorSnapshot(
            schema_version=self._schema_version,
            timestamp=self._cached_timestamp,
            sequence=self._cached_sequence,
            data=copy.deepcopy(self._cached_data),
            errors=dict(self._errors),
        )
