from __future__ import annotations

import unittest

from library.html_theme_components import (
    HtmlGeneratedWidget,
    WIDGET_RUNTIME_FILENAME,
    generated_widget_markup,
    generated_widget_ids,
    get_html_widget_component,
    html_widget_components,
    next_widget_id,
    render_widget_runtime_script,
    update_generated_widget_block,
)
from library.theme_engine import ThemeValidationError


class HtmlThemeComponentTests(unittest.TestCase):
    def test_catalog_covers_requested_sensor_and_information_widgets(self):
        keys = {component.key for component in html_widget_components()}
        self.assertTrue(
            {
                "cpu-temperature",
                "gpu-temperature",
                "cpu-usage",
                "gpu-usage",
                "ram-usage",
                "cpu-load",
                "weather-temperature",
                "weather-condition",
                "time",
                "date",
                "cpu-usage-bar",
                "gpu-usage-bar",
                "ram-usage-bar",
                "disk-usage-bar",
                "cpu-temperature-bar",
                "gpu-temperature-bar",
            }.issubset(keys)
        )
        self.assertTrue(
            all(
                get_html_widget_component(key).kind == "bar"
                for key in {
                    "cpu-usage-bar",
                    "gpu-usage-bar",
                    "ram-usage-bar",
                    "disk-usage-bar",
                    "cpu-temperature-bar",
                    "gpu-temperature-bar",
                }
            )
        )

    def test_ids_are_unique_and_component_keys_are_validated(self):
        self.assertEqual(
            next_widget_id("cpu-usage", {"turing-cpu-usage-1"}),
            "turing-cpu-usage-2",
        )
        with self.assertRaises(ThemeValidationError):
            get_html_widget_component("shell-command")

    def test_generated_block_is_replaced_and_removed_atomically_in_text(self):
        original = "<html><body><main></main></body></html>"
        first = update_generated_widget_block(
            original,
            (("turing-cpu-usage-1", "cpu-usage"),),
        )
        self.assertIn(WIDGET_RUNTIME_FILENAME, first)
        self.assertEqual(generated_widget_ids(first), ("turing-cpu-usage-1",))

        second = update_generated_widget_block(
            first,
            (("turing-date-1", "date"),),
        )
        self.assertNotIn("turing-cpu-usage-1", second)
        self.assertEqual(generated_widget_ids(second), ("turing-date-1",))
        self.assertEqual(update_generated_widget_block(second, ()), original)

    def test_runtime_chains_existing_theme_bridge_without_network_access(self):
        source = render_widget_runtime_script()
        self.assertIn("originalUpdate", source)
        self.assertIn("__turingUpdateGeneratedWidgets", source)
        self.assertIn("toLocaleDateString('pt-BR')", source)
        self.assertIn("data-turing-bar-fill", source)
        self.assertIn("aria-valuenow", source)
        self.assertIn("__turingPositionEditorElement", source)
        self.assertIn("getBoundingClientRect", source)
        self.assertIn("--turing-editor-x", source)
        self.assertNotIn("fetch(", source)
        self.assertNotIn("XMLHttpRequest", source)

    def test_bar_markup_has_a_local_accessible_fill_element(self):
        markup = generated_widget_markup(
            "turing-cpu-usage-bar-1",
            "cpu-usage-bar",
        )
        self.assertIn('data-turing-kind="bar"', markup)
        self.assertIn('role="progressbar"', markup)
        self.assertIn("data-turing-bar-fill", markup)

    def test_custom_binding_markup_does_not_require_a_catalog_component(self):
        markup = generated_widget_markup(
            "turing-network-download-1",
            binding="network.download",
            formatter="megabytes-per-second",
            sample="12.5 MB/s",
            kind="text",
        )
        self.assertIn('data-turing-binding="network.download"', markup)
        self.assertIn('data-turing-format="megabytes-per-second"', markup)
        self.assertNotIn("data-turing-component", markup)
        self.assertIn("12.5 MB/s", markup)

        block = update_generated_widget_block(
            "<html><body></body></html>",
            (
                HtmlGeneratedWidget(
                    element_id="turing-network-download-1",
                    binding="network.download",
                    formatter="megabytes-per-second",
                    sample="12.5 MB/s",
                ),
            ),
        )
        self.assertIn('data-turing-binding="network.download"', block)

    def test_custom_bindings_and_formatters_are_strictly_validated(self):
        numeric_segment = generated_widget_markup(
            "turing-cpu-load-1",
            binding="cpu.load.0",
            formatter="load",
            sample="1.25",
        )
        self.assertIn('data-turing-binding="cpu.load.0"', numeric_segment)
        with self.assertRaisesRegex(ThemeValidationError, "binding"):
            generated_widget_markup(
                "turing-invalid-1",
                binding="cpu.usage;alert(1)",
            )
        with self.assertRaisesRegex(ThemeValidationError, "formatter"):
            generated_widget_markup(
                "turing-invalid-1",
                binding="cpu.usage",
                formatter="javascript",
            )


if __name__ == "__main__":
    unittest.main()
