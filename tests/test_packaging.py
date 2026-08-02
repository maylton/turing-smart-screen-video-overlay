from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_FILTER = ROOT / "packaging" / "runtime-rsync-filter.txt"
CORE_FONT_FILTER = ROOT / "packaging" / "core-fonts-rsync-filter.txt"


class PackagingContractTests(unittest.TestCase):
    def test_installer_uses_an_explicit_runtime_payload(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn('RUNTIME_FILTER="$SOURCE_DIR/packaging/runtime-rsync-filter.txt"', text)
        self.assertIn(
            'CORE_FONT_FILTER="$SOURCE_DIR/packaging/core-fonts-rsync-filter.txt"',
            text,
        )
        self.assertIn('--filter "merge $RUNTIME_FILTER"', text)
        self.assertIn('--filter "merge $CORE_FONT_FILTER"', text)
        self.assertIn("--delete-excluded", text)
        self.assertIn("--exclude='--Theme examples/'", text)
        self.assertIn(".gtk-ui-backups .theme-editor-backups", text)
        self.assertIn("--full-fonts", text)
        self.assertTrue(RUNTIME_FILTER.is_file())
        self.assertTrue(CORE_FONT_FILTER.is_file())

    @unittest.skipUnless(shutil.which("rsync"), "rsync is required for payload filtering")
    def test_runtime_payload_excludes_development_and_optional_content(self):
        with tempfile.TemporaryDirectory(prefix="turing-payload-test-") as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "destination"

            included = (
                "main.py",
                "theme-migrate.py",
                "library/runtime.py",
                "res/themes/core/theme.yaml",
                "res/docs/no-preview.png",
                "res/fonts/roboto/Roboto-Regular.ttf",
                "tools/render_theme_preview.py",
                "packaging/core-fonts-rsync-filter.txt",
                "packaging/runtime-rsync-filter.txt",
            )
            excluded = (
                "main.py.video-working",
                "simple-program.py",
                "docs/ROADMAP.md",
                "tests/test_runtime.py",
                "external/windows-only.dll",
                "tools/compare-images.py",
                "res/docs/device-photo.png",
                "res/fonts/BoutiqueBitmap9x9/Optional.ttf",
                "res/themes/--Theme examples/large.png",
                "res/themes/core/theme.yaml.editor-backup",
            )

            for relative in (*included, *excluded):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative, encoding="utf-8")

            completed = subprocess.run(
                [
                    "rsync",
                    "-a",
                    "--delete",
                    "--delete-excluded",
                    "--filter",
                    f"merge {CORE_FONT_FILTER}",
                    "--filter",
                    f"merge {RUNTIME_FILTER}",
                    f"{source}/",
                    f"{destination}/",
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

            for relative in included:
                with self.subTest(included=relative):
                    self.assertTrue((destination / relative).is_file())
            for relative in excluded:
                with self.subTest(excluded=relative):
                    self.assertFalse((destination / relative).exists())

    @unittest.skipUnless(shutil.which("rsync"), "rsync is required for payload filtering")
    def test_full_font_profile_keeps_optional_fonts(self):
        with tempfile.TemporaryDirectory(prefix="turing-full-font-test-") as directory:
            root = Path(directory)
            source = root / "source"
            destination = root / "destination"
            optional_font = source / "res" / "fonts" / "optional" / "Custom.ttf"
            optional_font.parent.mkdir(parents=True)
            optional_font.write_bytes(b"optional")

            completed = subprocess.run(
                [
                    "rsync",
                    "-a",
                    "--filter",
                    f"merge {RUNTIME_FILTER}",
                    f"{source}/",
                    f"{destination}/",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                (destination / "res" / "fonts" / "optional" / "Custom.ttf").read_bytes(),
                b"optional",
            )

    def test_installer_exposes_system_gtk_to_the_venv(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("-m venv --system-site-packages"), 2)
        self.assertIn('"$PREFIX/venv/bin/python3" -m pip', text)
        self.assertIn("System GTK4 and Libadwaita imports OK", text)
        self.assertIn(
            "Project venv GTK, Pillow, pyserial, Babel and ruamel.yaml imports OK",
            text,
        )

    def test_installer_includes_visible_and_offscreen_webkit_backends(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn("webkitgtk-6.0", text)
        self.assertIn("webkit2gtk-4.1", text)
        checkup = (ROOT / "gtk-checkup.py").read_text(encoding="utf-8")
        self.assertIn("Background HTML renderer dependencies", checkup)
        self.assertIn("gi.require_version('WebKit2', '4.1')", checkup)

    def test_installer_runs_the_installed_checkup(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertIn('"$PREFIX/venv/bin/python3" "$PREFIX/gtk-checkup.py" "$PREFIX"', text)

    def test_installer_keeps_translation_runtime_files(self):
        installer = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertNotIn("--exclude 'usercustomize.py'", installer)
        self.assertNotIn("--exclude 'library/*i18n.py'", installer)

        required_i18n_files = (
            "usercustomize.py",
            "library/i18n.py",
            "library/main_app_i18n.py",
            "library/diagnostics_gtk_i18n.py",
            "library/media_preparation_i18n.py",
            "library/theme_editor_i18n.py",
            "library/theme_editor_safe_i18n.py",
            "library/theme_editor_widget_i18n.py",
            "library/theme_gallery_i18n.py",
            "library/video_manager_i18n.py",
        )
        for relative in required_i18n_files:
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_translation_entry_points_are_connected(self):
        startup = (ROOT / "usercustomize.py").read_text(encoding="utf-8")
        self.assertIn('"configure-gtk.py"', startup)
        self.assertIn('"theme-editor-gtk.py"', startup)
        self.assertIn("install_main_app_tray_i18n", startup)
        self.assertIn("install_theme_editor_widget_i18n", startup)

        integrations = (
            ROOT / "library" / "main_app_diagnostics_integration.py"
        ).read_text(encoding="utf-8")
        self.assertIn("install_main_app_shell_i18n", integrations)
        self.assertIn("build_inline_diagnostics_page", integrations)
        self.assertIn("build_inline_theme_editor_page", integrations)

    def test_stability_stack_runtime_files_are_packaged(self):
        installer = (ROOT / "install.sh").read_text(encoding="utf-8")
        for excluded in (
            "VERSION",
            "library/release_info.py",
            "library/theme_editor_backups.py",
            "library/display_lifecycle.py",
            "library/gpu_selection.py",
            "gpu-selection-gtk.py",
        ):
            with self.subTest(excluded=excluded):
                self.assertNotIn(f"--exclude '{excluded}'", installer)

        required_files = (
            "VERSION",
            "install-checked.sh",
            "scripts/installation-report.py",
            "library/release_info.py",
            "library/theme_editor_backups.py",
            "library/theme_editor_backup_runtime.py",
            "theme-backups.py",
            "library/display_lifecycle.py",
            "library/gpu_selection.py",
            "library/gpu_selection_runtime.py",
            "library/gpu_diagnostics.py",
            "gpu-selection.py",
            "gpu-selection-gtk.py",
        )
        for relative in required_files:
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_gpu_selection_is_connected_to_monitor_and_diagnostics(self):
        startup = (ROOT / "usercustomize.py").read_text(encoding="utf-8")
        self.assertIn('"main.py"', startup)
        self.assertIn("install_gpu_selection", startup)

        diagnostics = (ROOT / "diagnostics.py").read_text(encoding="utf-8")
        self.assertIn("collect_gpu_diagnostics", diagnostics)
        self.assertIn('"gpu": collect_gpu_diagnostics()', diagnostics)

        for relative in (
            "diagnostics-gtk.py",
            "library/main_app_inline_diagnostics.py",
        ):
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIn("gpu-selection-gtk.py", text)
            self.assertIn("GPU sensors", text)

    def test_fork_documentation_exists(self):
        for relative in (
            "docs/INSTALLATION.md",
            "docs/ROADMAP.md",
            "scripts/test-install.py",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())

    def test_readme_describes_current_media_support(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("MAYLTON_FORK_OVERVIEW", text)
        self.assertNotIn("no video or storage support for now", text)
        self.assertIn("Rev. C 2.1-inch", text)

    def test_installation_guide_documents_safe_updates(self):
        text = (ROOT / "docs" / "INSTALLATION.md").read_text(encoding="utf-8")
        self.assertIn("./install.sh --no-deps", text)
        self.assertIn("--system-site-packages", text)
        self.assertIn("Isolated packaging test", text)


if __name__ == "__main__":
    unittest.main()
