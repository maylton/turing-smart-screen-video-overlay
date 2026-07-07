from pathlib import Path
import ast
import unittest


class ProgressBarVisualEffectsContractTests(unittest.TestCase):
    def test_display_progress_bar_accepts_effects_parameter(self):
        source = Path("library/lcd/lcd_comm.py").read_text(encoding="utf-8")
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "DisplayProgressBar":
                arg_names = [arg.arg for arg in node.args.args + node.args.kwonlyargs]
                self.assertIn("effects", arg_names)
                return

        self.fail("DisplayProgressBar was not found")

    def test_stats_passes_theme_effects_to_progress_bar(self):
        source = Path("library/stats.py").read_text(encoding="utf-8")
        self.assertIn('effects=theme_data.get("EFFECTS", {})', source)


if __name__ == "__main__":
    unittest.main()
