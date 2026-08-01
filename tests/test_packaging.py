from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PackagingContractTests(unittest.TestCase):
    def test_installer_exposes_system_gtk_to_the_venv(self):
        text = (ROOT / "install.sh").read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("-m venv --system-site-packages"), 2)
        self.assertIn('"$PREFIX/venv/bin/python3" -m pip', text)
        self.assertIn("System GTK4 and Libadwaita imports OK", text)
        self.assertIn(
            "Project venv GTK, Pillow, pyserial, Babel and ruamel.yaml imports OK",
            text,
        )

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
