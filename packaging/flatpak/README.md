# Flatpak packaging

This directory contains the Flatpak packaging for Turing Smart Screen 0.9.0.

## Install a GitHub release

Download these release assets:

- `Turing-Smart-Screen-0.9.0-x86_64.flatpak`
- `70-turing-smart-screen.rules`
- `SHA256SUMS`

Optionally verify them:

```bash
sha256sum -c SHA256SUMS
```

Install the Flatpak bundle:

```bash
flatpak install --user ./Turing-Smart-Screen-0.9.0-x86_64.flatpak
```

Install the host udev rule so serial and raw USB display access work outside the sandbox:

```bash
sudo install -Dm0644 70-turing-smart-screen.rules /etc/udev/rules.d/70-turing-smart-screen.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Reconnect the display afterwards.

## Build locally

```bash
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install -y flathub org.gnome.Platform//50 org.gnome.Sdk//50
flatpak-builder --force-clean --install-deps-from=flathub build-flatpak packaging/flatpak/io.github.turing.SmartScreen.yml
```

To create a local repository and bundle:

```bash
flatpak-builder --force-clean --repo=flatpak-repo --install-deps-from=flathub build-flatpak packaging/flatpak/io.github.turing.SmartScreen.yml
flatpak build-bundle flatpak-repo Turing-Smart-Screen-0.9.0-x86_64.flatpak io.github.turing.SmartScreen stable
```

## Hardware access

The sandbox grants device access because supported displays span both serial `/dev/ttyUSB*`/`/dev/ttyACM*` devices and raw USB TURZX devices. This does not replace host permissions.

Flatpak cannot install udev rules on the host. The release therefore ships `70-turing-smart-screen.rules` as a separate asset that must be installed on systems where the logged-in user does not already receive the required `uaccess` permissions.

## AMD GPU telemetry

The Flatpak bundles a current libdrm and builds `pyamdgpuinfo` from source against it. This avoids the private libdrm copies shipped by the prebuilt `pyamdgpuinfo` wheel and allows the app-local `amdgpu.ids` database to be used inside the sandbox.

## Writable application state

Flatpak mounts `/app` read-only, while the current application edits `config.yaml`, themes and generated media relative to its project root. The Flatpak launcher therefore maintains a writable synchronized runtime copy under the application's private XDG data directory. On package upgrades it refreshes application files while preserving configuration, themes and generated media.

## Current limitations

- This is a GitHub release build and is not yet distributed through Flathub.
- udev rules still require host-side installation when the device does not already receive `uaccess` permissions.
- ICMP/raw-socket ping metrics can be restricted by the Flatpak sandbox and should be treated as optional telemetry.
