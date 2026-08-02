# SPDX-License-Identifier: GPL-3.0-or-later
"""Budget partial Rev. C updates against the last physically committed frame."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Optional, Sequence, Tuple

from PIL import Image

from library.atomic_regions import AtomicRegion
from library.dirty_region_optimizer import optimize_frame_analysis
from library.frame_pipeline import FrameAnalysis, FramePipeline, FrameRegion


class FrameBudgetError(RuntimeError):
    """Raised when no safe partial plan can be produced."""


def estimate_rev_c_partial_wire_bytes(region: FrameRegion) -> int:
    """Return the exact Rev. C wire size for one BGR partial-region exchange."""
    width = int(region.width)
    height = int(region.height)
    if width <= 0 or height <= 0:
        raise ValueError("partial region dimensions must be positive")

    records_bytes = height * (5 + width * 3)
    if records_bytes > 250:
        chunks = (records_bytes + 248) // 249
        framed_records_bytes = records_bytes + (chunks - 1)
    else:
        framed_records_bytes = records_bytes

    payload_bytes = framed_records_bytes + 2
    payload_wire_bytes = ((payload_bytes + 249) // 250) * 250
    return 250 + payload_wire_bytes + 250


@dataclass(frozen=True)
class BudgetedFramePlan:
    analysis: FrameAnalysis
    candidate_region_count: int
    deferred_regions: Tuple[FrameRegion, ...]
    estimated_wire_bytes: int
    selected_atomic_regions: int

    @property
    def selected_regions(self) -> Tuple[FrameRegion, ...]:
        return self.analysis.regions

    @property
    def deferred_region_count(self) -> int:
        return len(self.deferred_regions)

    @property
    def has_updates(self) -> bool:
        return bool(self.analysis.regions)


class BudgetedFramePlanner:
    """Plan partial updates without forgetting pixels deferred by a wire budget."""

    def __init__(
        self,
        initial_frame: Image.Image,
        *,
        atomic_regions: Sequence[AtomicRegion] = (),
        initial_sequence: int = 1,
        tile_size: int = 16,
        pixel_threshold: int = 0,
        planning_max_regions: int = 512,
    ) -> None:
        frame = initial_frame.convert("RGBA")
        frame.load()
        if frame.width <= 0 or frame.height <= 0:
            raise ValueError("initial frame dimensions must be positive")
        if tile_size <= 0:
            raise ValueError("tile_size must be greater than zero")
        if planning_max_regions <= 0:
            raise ValueError("planning_max_regions must be greater than zero")

        self._physical_frame = frame.copy()
        self._atomic_regions = tuple(atomic_regions)
        self._sequence = int(initial_sequence)
        self.tile_size = int(tile_size)
        self.pixel_threshold = max(0, min(255, int(pixel_threshold)))
        self.planning_max_regions = int(planning_max_regions)
        self._atomic_order: Dict[Tuple[int, int, int, int], int] = {
            (item.x, item.y, item.width, item.height): index
            for index, item in enumerate(self._atomic_regions)
        }
        self._atomic_last_committed: Dict[Tuple[int, int, int, int], int] = {
            coordinates: -1 for coordinates in self._atomic_order
        }

    @property
    def physical_frame(self) -> Image.Image:
        return self._physical_frame.copy()

    @property
    def sequence(self) -> int:
        return self._sequence

    def _candidate_analysis(self, current: Image.Image) -> FrameAnalysis:
        pipeline = FramePipeline(
            tile_size=self.tile_size,
            pixel_threshold=self.pixel_threshold,
            full_refresh_ratio=1.0,
            max_regions=self.planning_max_regions,
        )
        pipeline.process(self._physical_frame)
        previous = pipeline.previous
        analysis = pipeline.process(current)
        analysis = replace(analysis, sequence=self._sequence + 1)
        return optimize_frame_analysis(
            previous,
            current,
            analysis,
            tile_size=self.tile_size,
            pixel_threshold=self.pixel_threshold,
            max_regions=self.planning_max_regions,
            full_refresh_ratio=1.0,
            atomic_regions=self._atomic_regions,
        )

    def _priority(self, region: FrameRegion) -> Tuple[int, int, int, int, int]:
        coordinates = (region.x, region.y, region.width, region.height)
        atomic_index = self._atomic_order.get(coordinates)
        if atomic_index is not None:
            return (
                0,
                self._atomic_last_committed[coordinates],
                atomic_index,
                region.y,
                region.x,
            )
        return (1, 0, region.area, region.y, region.x)

    def plan(
        self,
        current_frame: Image.Image,
        *,
        max_regions: int,
        max_wire_bytes: int,
        max_candidate_regions: Optional[int] = None,
    ) -> BudgetedFramePlan:
        current = current_frame.convert("RGBA")
        current.load()
        if current.size != self._physical_frame.size:
            raise FrameBudgetError(
                f"frame size {current.size} differs from physical framebuffer "
                f"{self._physical_frame.size}"
            )
        region_limit = int(max_regions)
        wire_limit = int(max_wire_bytes)
        candidate_limit = (
            None
            if max_candidate_regions is None
            else int(max_candidate_regions)
        )
        if region_limit <= 0:
            raise ValueError("max_regions must be greater than zero")
        if wire_limit <= 0:
            raise ValueError("max_wire_bytes must be greater than zero")
        if candidate_limit is not None and candidate_limit <= 0:
            raise ValueError("max_candidate_regions must be greater than zero")

        candidate = self._candidate_analysis(current)
        if candidate.full_refresh:
            raise FrameBudgetError(
                "the physical framebuffer diverged too much for partial planning"
            )

        ordered = sorted(candidate.regions, key=self._priority)
        considered = ordered
        deferred = []
        if candidate_limit is not None and len(ordered) > candidate_limit:
            considered = ordered[:candidate_limit]
            deferred.extend(ordered[candidate_limit:])

        selected = []
        wire_bytes = 0
        atomic_selected = 0

        for region in considered:
            cost = estimate_rev_c_partial_wire_bytes(region)
            if len(selected) >= region_limit or wire_bytes + cost > wire_limit:
                deferred.append(region)
                continue
            selected.append(region)
            wire_bytes += cost
            if (
                region.x,
                region.y,
                region.width,
                region.height,
            ) in self._atomic_order:
                atomic_selected += 1

        if ordered and not selected:
            smallest = min(
                estimate_rev_c_partial_wire_bytes(region)
                for region in considered
            )
            raise FrameBudgetError(
                "no changed region fits the physical budget; "
                f"smallest exchange requires {smallest} bytes"
            )

        analysis = replace(
            candidate,
            regions=tuple(selected),
            full_refresh=False,
        )
        return BudgetedFramePlan(
            analysis=analysis,
            candidate_region_count=len(ordered),
            deferred_regions=tuple(deferred),
            estimated_wire_bytes=wire_bytes,
            selected_atomic_regions=atomic_selected,
        )

    def commit(
        self,
        current_frame: Image.Image,
        plan: BudgetedFramePlan,
    ) -> None:
        expected_sequence = self._sequence + 1
        if plan.analysis.sequence != expected_sequence:
            raise FrameBudgetError(
                f"plan sequence {plan.analysis.sequence} does not follow "
                f"committed sequence {self._sequence}"
            )

        current = current_frame.convert("RGBA")
        current.load()
        if current.size != self._physical_frame.size:
            raise FrameBudgetError("committed frame size changed")

        for region in plan.selected_regions:
            crop = current.crop(
                (region.x, region.y, region.right, region.bottom)
            )
            self._physical_frame.paste(crop, (region.x, region.y))
            coordinates = (
                region.x,
                region.y,
                region.width,
                region.height,
            )
            if coordinates in self._atomic_last_committed:
                self._atomic_last_committed[coordinates] = plan.analysis.sequence
        self._sequence = plan.analysis.sequence
