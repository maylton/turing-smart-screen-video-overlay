# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed-coordinate visual regions that must update as indivisible widgets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence, Tuple


@dataclass(frozen=True)
class AtomicRegion:
    """Named screen rectangle that must be transmitted as one visual unit."""

    name: str
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def area(self) -> int:
        return max(0, self.width) * max(0, self.height)

    def as_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


def _atomic_int(value: Any, field: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc


def parse_atomic_regions(
    raw_regions: Any,
    *,
    display_width: int,
    display_height: int,
    field: str = "atomicRegions",
) -> Tuple[AtomicRegion, ...]:
    """Validate named fixed-coordinate regions from a manifest or artifact."""
    if raw_regions is None:
        return ()
    if not isinstance(raw_regions, Sequence) or isinstance(
        raw_regions, (str, bytes, bytearray)
    ):
        raise ValueError(f"{field} must be an array")
    if display_width <= 0 or display_height <= 0:
        raise ValueError("display dimensions must be positive")

    parsed = []
    names = set()
    for index, item in enumerate(raw_regions):
        item_field = f"{field}[{index}]"
        if isinstance(item, AtomicRegion):
            region = item
        else:
            if not isinstance(item, Mapping):
                raise ValueError(f"{item_field} must be an object")
            name = str(item.get("name", "")).strip()
            if not name:
                raise ValueError(f"{item_field}.name cannot be empty")
            region = AtomicRegion(
                name=name,
                x=_atomic_int(item.get("x"), f"{item_field}.x"),
                y=_atomic_int(item.get("y"), f"{item_field}.y"),
                width=_atomic_int(item.get("width"), f"{item_field}.width"),
                height=_atomic_int(item.get("height"), f"{item_field}.height"),
            )

        if region.name in names:
            raise ValueError(f"{field} contains duplicate name {region.name!r}")
        if region.x < 0 or region.y < 0:
            raise ValueError(f"{item_field} coordinates must not be negative")
        if region.width <= 0 or region.height <= 0:
            raise ValueError(f"{item_field} width and height must be positive")
        if region.right > display_width or region.bottom > display_height:
            raise ValueError(
                f"{item_field} exceeds the {display_width}x{display_height} display"
            )
        names.add(region.name)
        parsed.append(region)
    return tuple(parsed)
