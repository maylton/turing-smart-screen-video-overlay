# Flatpak packaging

This directory contains the first Flatpak packaging preview for Turing Smart Screen.

## Build

```bash
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install -y flathub org.gnome.Platform//50 org.gnome.Sdk//50
flatpak-builder --force-clean --install-deps-from=flathub build-flatpak packaging/flatpak/io.github.turing.SmartScreen.yml
```

To create a local repository and bundle:

```bash
flatpak-builder --force-clean --repo=flatpak-repo --install-deps-from=flathub build-flatpak packaging/flatpak/io.github.turing.SmartScreen.yml
flatpak build-bundle flatpak-repo Turing-Smart-Screen-0.9.0-dev1-flatpak1-x86_64.flatpak io.github.turing.SmartScreen stable
```

## Hardware access

The sandbox grants device access because supported displays span both serial `/dev/ttyUSB*`/`/dev/ttyACM*` devices and raw USB TURZX devices. This does not replace host permissions.

Flatpak cannot install udev rules on the host. If the display is not accessible to the logged-in user, install the repository's rule outside the sandbox:

```bash
sudo install -Dm0644 packaging/70-turing-smart-screen.rules /etc/udev/rules.d/70-turing-smart-screen.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Reconnect the display afterwards.

## Writable application state

Flatpak mounts `/app` read-only, while the current application edits `config.yaml`, themes and generated media relative to its project root. The Flatpak launcher therefore maintains a writable synchronized runtime copy under the application's private XDG data directory. On package upgrades it refreshes application files while preserving configuration, themes and generated media.

## Current limitations

- This is a GitHub release preview, not yet a Flathub submission.
- udev rules still require host-side installation when the device does not already receive `uaccess` permissions.
- GPU telemetry that relies on host-only utilities such as vendor command-line tools may be unavailable in the sandbox; psutil and sysfs-based metrics should continue to work where exposed.
- ICMP/raw-socket ping metrics can be restricted by the Flatpak sandbox and should be treated as optional telemetry.
