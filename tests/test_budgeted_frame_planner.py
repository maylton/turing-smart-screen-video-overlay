# SPDX-License-Identifier: GPL-3.0-or-later
import unittest

from PIL import Image, ImageDraw

from library.atomic_regions import AtomicRegion
from library.budgeted_frame_planner import (
    BudgetedFramePlanner,
    estimate_rev_c_partial_wire_bytes,
)
from library.frame_pipeline import FrameAnalysis, FrameRegion
from library.rev_c_protocol_simulator import RevCProtocolSimulator
from library.simulated_display_transport import (
    SimulatedDisplayTransport,
    get_transport_profile,
)


class BudgetedFramePlannerTests(unittest.TestCase):
    def test_wire_estimator_matches_protocol_simulator(self):
        frame = Image.new("RGBA", (480, 480), (10, 20, 30, 255))
        regions = (
            FrameRegion(0, 0, 20, 20),
            FrameRegion(26, 42, 160, 42),
            FrameRegion(66, 144, 112, 96),
            FrameRegion(80, 180, 400, 300),
        )

        for sequence, region in enumerate(regions, start=2):
            transport_engine = SimulatedDisplayTransport(
                get_transport_profile("rev-c-2inch"),
                size=frame.size,
            )
            analysis = FrameAnalysis(
                sequence=sequence,
                width=480,
                height=480,
                changed_pixels=region.area,
                total_pixels=480 * 480,
                change_ratio=region.area / (480 * 480),
                regions=(region,),
                full_refresh=False,
            )
            transport = transport_engine.submit(frame, analysis)
            protocol = RevCProtocolSimulator(
                display_stride=480
            ).submit(transport)

            self.assertEqual(
                estimate_rev_c_partial_wire_bytes(region),
                protocol.wire_bytes,
            )

    def test_atomic_widget_is_selected_before_large_animation(self):
        initial = Image.new("RGBA", (480, 480), (0, 0, 0, 255))
        current = initial.copy()
        draw = ImageDraw.Draw(current)
        draw.rectangle((0, 0, 19, 19), fill=(255, 255, 255, 255))
        draw.rectangle((80, 180, 479, 479), fill=(80, 40, 120, 255))
        atomic = AtomicRegion("cpu-value", 0, 0, 20, 20)
        planner = BudgetedFramePlanner(
            initial,
            atomic_regions=(atomic,),
            initial_sequence=1,
            tile_size=4,
        )

        plan = planner.plan(
            current,
            max_regions=32,
            max_wire_bytes=300_000,
        )

        self.assertEqual(
            [region.as_dict() for region in plan.selected_regions],
            [{"x": 0, "y": 0, "width": 20, "height": 20}],
        )
        self.assertEqual(plan.selected_atomic_regions, 1)
        self.assertGreater(plan.deferred_region_count, 0)
        self.assertLessEqual(plan.estimated_wire_bytes, 300_000)

    def test_commit_updates_only_regions_that_reached_the_display(self):
        initial = Image.new("RGBA", (480, 480), (0, 0, 0, 255))
        current = initial.copy()
        draw = ImageDraw.Draw(current)
        draw.rectangle((0, 0, 19, 19), fill=(255, 255, 255, 255))
        draw.rectangle((80, 180, 479, 479), fill=(80, 40, 120, 255))
        planner = BudgetedFramePlanner(
            initial,
            atomic_regions=(AtomicRegion("clock", 0, 0, 20, 20),),
            initial_sequence=1,
            tile_size=4,
        )
        plan = planner.plan(
            current,
            max_regions=32,
            max_wire_bytes=300_000,
        )

        planner.commit(current, plan)
        physical = planner.physical_frame

        self.assertEqual(physical.getpixel((5, 5)), (255, 255, 255, 255))
        self.assertEqual(physical.getpixel((200, 300)), (0, 0, 0, 255))
        self.assertEqual(planner.sequence, 2)

    def test_deferred_pixels_are_considered_again_on_next_source_frame(self):
        initial = Image.new("RGBA", (480, 480), (0, 0, 0, 255))
        first = initial.copy()
        draw = ImageDraw.Draw(first)
        draw.rectangle((0, 0, 19, 19), fill=(255, 255, 255, 255))
        draw.rectangle((80, 180, 479, 479), fill=(80, 40, 120, 255))
        atomic = AtomicRegion("cpu-value", 0, 0, 20, 20)
        planner = BudgetedFramePlanner(
            initial,
            atomic_regions=(atomic,),
            initial_sequence=1,
            tile_size=4,
        )
        first_plan = planner.plan(
            first,
            max_regions=32,
            max_wire_bytes=300_000,
        )
        planner.commit(first, first_plan)

        second = first.copy()
        ImageDraw.Draw(second).rectangle(
            (0, 0, 19, 19),
            fill=(220, 220, 220, 255),
        )
        second_plan = planner.plan(
            second,
            max_regions=32,
            max_wire_bytes=300_000,
        )

        self.assertEqual(second_plan.selected_atomic_regions, 1)
        self.assertGreater(second_plan.deferred_region_count, 0)
        self.assertEqual(second_plan.analysis.sequence, 3)


if __name__ == "__main__":
    unittest.main()
