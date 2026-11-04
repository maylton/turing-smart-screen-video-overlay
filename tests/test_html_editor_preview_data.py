from __future__ import annotations

import unittest

from library.html_editor_preview_data import (
    CUSTOM_FIELDS,
    binding_value,
    custom_data,
    format_field_value,
    parse_field_value,
    preset_data,
)


class PreviewDataTests(unittest.TestCase):
    def test_every_custom_field_has_a_value_in_the_normal_preset(self):
        normal = preset_data("normal")
        for field in CUSTOM_FIELDS:
            with self.subTest(binding=field.binding):
                self.assertIsNotNone(binding_value(normal, field.binding))

    def test_parse_numbers_text_and_empty(self):
        self.assertEqual(parse_field_value("95"), 95)
        self.assertEqual(parse_field_value("4,7"), 4.7)
        self.assertEqual(parse_field_value(" 18.40 "), 18.4)
        self.assertEqual(parse_field_value("49.9°C"), "49.9°C")
        self.assertIsNone(parse_field_value("   "))

    def test_custom_overrides_do_not_touch_the_base(self):
        base = preset_data("normal")
        data = custom_data(base, {"cpu.temperature": "95", "system.hostname": "um-host-muito-longo"})
        self.assertEqual(data["cpu"]["temperature"], 95)
        self.assertEqual(data["system"]["hostname"], "um-host-muito-longo")
        self.assertEqual(base["cpu"]["temperature"], 49)
        self.assertEqual(data["gpu"], base["gpu"])

    def test_empty_field_makes_the_sensor_unavailable(self):
        data = custom_data(preset_data("normal"), {"gpu.temperature": ""})
        self.assertNotIn("temperature", data["gpu"])

    def test_field_formatting_round_trips(self):
        for value in (62, 4.7, 18.4, "24.0°C"):
            self.assertEqual(parse_field_value(format_field_value(value)), value)
        self.assertEqual(format_field_value(None), "")
        self.assertEqual(format_field_value(128.0), "128")


if __name__ == "__main__":
    unittest.main()
