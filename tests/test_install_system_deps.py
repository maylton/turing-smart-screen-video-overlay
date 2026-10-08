from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install-system-deps.sh"

OS_RELEASES = {
    "ubuntu": 'ID=ubuntu\nID_LIKE=debian\nPRETTY_NAME="Ubuntu 26.04 LTS"\n',
    "debian": 'ID=debian\nPRETTY_NAME="Debian GNU/Linux 13 (trixie)"\n',
    "linuxmint": 'ID=linuxmint\nID_LIKE="ubuntu debian"\nPRETTY_NAME="Linux Mint 22"\n',
    "arch": 'ID=arch\nPRETTY_NAME="Arch Linux"\n',
    "cachyos": 'ID=cachyos\nID_LIKE=arch\nPRETTY_NAME="CachyOS Linux"\n',
    "fedora": 'ID=fedora\nPRETTY_NAME="Fedora Linux 43 (Workstation Edition)"\n',
    "rocky": 'ID="rocky"\nID_LIKE="rhel centos fedora"\nPRETTY_NAME="Rocky Linux 10"\n',
    "unknown": 'ID=plan9\nPRETTY_NAME="Plan 9"\n',
}


@unittest.skipUnless(shutil.which("bash"), "bash is required for installer tests")
class InstallSystemDepsTests(unittest.TestCase):
    def setUp(self):
        self._directory = tempfile.TemporaryDirectory(prefix="turing-deps-test-")
        self.root = Path(self._directory.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.calls = self.root / "calls.log"
        self.calls.touch()
        # Only the tools the script needs; nothing from the host can be reached.
        for tool in ("cat", "grep", "head"):
            os.symlink(shutil.which(tool), self.bin / tool)
        self.stub("id", 'echo "${FAKE_UID:-1000}"')
        self.stub("sudo", 'echo "sudo $*" >> "$CALLS"; exec "$@"')

    def tearDown(self):
        self._directory.cleanup()

    def stub(self, name, body):
        path = self.bin / name
        path.write_text(f"#!/bin/bash\n{body}\n", encoding="utf-8")
        path.chmod(0o755)

    def logging_stub(self, name, extra=""):
        self.stub(name, f'echo "{name} $*" >> "$CALLS"\n{extra}')

    def run_script(self, distro, *args, env=None):
        os_release = self.root / "os-release"
        os_release.write_text(OS_RELEASES[distro], encoding="utf-8")
        environment = {
            "PATH": str(self.bin),
            "CALLS": str(self.calls),
            "TURING_OS_RELEASE_FILE": str(os_release),
        }
        environment.update(env or {})
        return subprocess.run(
            [shutil.which("bash"), str(SCRIPT), *args],
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def printed(self, distro):
        completed = self.run_script(distro, "--print")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        fields = dict(
            line.split(": ", 1) for line in completed.stdout.splitlines() if ": " in line
        )
        fields["packages"] = fields.get("packages", "").split()
        return fields

    def call_lines(self):
        return self.calls.read_text(encoding="utf-8").splitlines()

    def test_debian_family_includes_cairo_bridge_and_both_webkit_apis(self):
        for distro in ("ubuntu", "debian", "linuxmint"):
            with self.subTest(distro=distro):
                fields = self.printed(distro)
                self.assertEqual(fields["family"], "debian")
                self.assertEqual(fields["manager"], "apt-get")
                for package in (
                    "python3-gi",
                    "python3-gi-cairo",
                    "python3-cairo",
                    "gir1.2-gtk-3.0",
                    "gir1.2-gtk-4.0",
                    "gir1.2-adw-1",
                    "gir1.2-webkit-6.0",
                    "gir1.2-webkit2-4.1",
                    "python3-venv",
                    "ffmpeg",
                ):
                    self.assertIn(package, fields["packages"])

    def test_arch_family_includes_python_cairo(self):
        for distro in ("arch", "cachyos"):
            with self.subTest(distro=distro):
                fields = self.printed(distro)
                self.assertEqual(fields["family"], "arch")
                self.assertEqual(fields["manager"], "pacman")
                for package in (
                    "python-gobject",
                    "python-cairo",
                    "gtk3",
                    "webkitgtk-6.0",
                    "webkit2gtk-4.1",
                ):
                    self.assertIn(package, fields["packages"])

    def test_fedora_family_uses_full_pygobject_package(self):
        for distro in ("fedora", "rocky"):
            with self.subTest(distro=distro):
                fields = self.printed(distro)
                self.assertEqual(fields["family"], "fedora")
                self.assertEqual(fields["manager"], "dnf")
                for package in (
                    "python3-gobject",
                    "python3-cairo",
                    "webkitgtk6.0",
                    "webkit2gtk4.1",
                    "ffmpeg-free",
                ):
                    self.assertIn(package, fields["packages"])
                self.assertNotIn("python3-gobject-base", fields["packages"])

    def test_fedora_keeps_an_existing_ffmpeg(self):
        self.stub("ffmpeg", "exit 0")
        self.assertNotIn("ffmpeg-free", self.printed("fedora")["packages"])

    def test_unknown_distribution_falls_back_to_package_manager(self):
        self.assertEqual(self.printed("unknown")["family"], "unknown")
        self.logging_stub("dnf")
        self.assertEqual(self.printed("unknown")["family"], "fedora")

    def test_unknown_distribution_without_manager_reports_requirements(self):
        completed = self.run_script("unknown")
        self.assertEqual(completed.returncode, 0)
        self.assertIn("gi._gi_cairo", completed.stderr)
        self.assertIn("--no-deps", completed.stderr)
        self.assertEqual(self.call_lines(), [])

    def test_missing_package_manager_is_an_error(self):
        completed = self.run_script("fedora")
        self.assertEqual(completed.returncode, 1)
        self.assertIn("dnf is not available", completed.stderr)

    def test_apt_installs_available_packages_through_sudo(self):
        self.logging_stub("apt-get")
        self.stub(
            "apt-cache",
            'for last; do :; done; [[ "$last" != "gir1.2-webkit-6.0" ]]',
        )
        completed = self.run_script("ubuntu")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        calls = self.call_lines()
        self.assertEqual(calls[0], "sudo apt-get update")
        self.assertEqual(calls[1], "apt-get update")
        install = calls[3]
        self.assertTrue(install.startswith("apt-get install "), calls)
        self.assertIn(" python3-gi-cairo ", f"{install} ")
        self.assertNotIn("gir1.2-webkit-6.0", install)
        self.assertIn("not available", completed.stderr)
        self.assertIn("gir1.2-webkit-6.0", completed.stderr)

    def test_root_does_not_need_sudo(self):
        self.logging_stub("pacman")
        completed = self.run_script("arch", env={"FAKE_UID": "0"})
        self.assertEqual(completed.returncode, 0, completed.stderr)
        calls = self.call_lines()
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].startswith("pacman -S --needed "))
        self.assertIn(" python-cairo ", calls[0])

    def test_dnf5_and_dnf4_skip_unavailable_packages(self):
        for version, flag in (
            ("dnf5 version 5.2.6", "--skip-unavailable"),
            ("4.21.1", "--setopt=strict=0"),
        ):
            with self.subTest(version=version):
                self.calls.write_text("", encoding="utf-8")
                self.logging_stub(
                    "dnf",
                    textwrap.dedent(
                        f"""\
                        if [[ "$1" == "--version" ]]; then echo "{version}"; fi
                        """
                    ),
                )
                completed = self.run_script("fedora")
                self.assertEqual(completed.returncode, 0, completed.stderr)
                installs = [line for line in self.call_lines() if line.startswith("dnf install")]
                self.assertEqual(len(installs), 1, self.call_lines())
                self.assertTrue(installs[0].startswith(f"dnf install {flag} "))
                self.assertIn(" python3-gobject ", installs[0])

    def test_fedora_warns_when_ffmpeg_lacks_libx264(self):
        self.logging_stub("dnf")
        self.stub("ffmpeg", 'echo " V..... libopenh264  OpenH264"')
        completed = self.run_script("fedora")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("no libx264 encoder", completed.stderr)
        self.assertIn("dnf swap ffmpeg-free ffmpeg", completed.stderr)

    def test_unknown_option_is_rejected(self):
        completed = self.run_script("ubuntu", "--bogus")
        self.assertEqual(completed.returncode, 2)


if __name__ == "__main__":
    unittest.main()
