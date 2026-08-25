# Contributing to Turing Smart Screen for Linux

Thanks for your interest in improving this Linux-focused fork.

This repository builds on
[`mathoudebine/turing-smart-screen-python`](https://github.com/mathoudebine/turing-smart-screen-python),
but issues and pull requests about the GTK application, Flatpak packaging,
fork-specific themes/media workflows and hardware findings should be opened **in
this repository** unless the change is explicitly being prepared for upstream.

## Before contributing

Please read:

- [`README.md`](README.md) for current scope and hardware validation;
- [`docs/INSTALLATION.md`](docs/INSTALLATION.md) for Flatpak/native setup;
- [`CHANGELOG.md`](CHANGELOG.md) for current release status;
- [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md).

The canonical development branch is `main`.

## Reporting bugs

Use this repository's issue tracker:

<https://github.com/maylton/turing-smart-screen-video-overlay/issues>

Before opening a report:

1. Confirm you are using the latest release or current `main`.
2. Search existing issues for the same behavior.
3. Reproduce the problem with as little unrelated state as possible.
4. Include relevant logs instead of screenshots of terminal text when possible.

For hardware/runtime bugs, include:

- display model, size and revision;
- ROM/firmware information when known;
- USB vendor/product IDs when relevant;
- Linux distribution and desktop environment;
- installation type: Flatpak or native/source;
- application version/commit;
- whether the problem occurs from the GTK UI, system tray or direct `main.py` execution;
- serial/raw USB device paths involved;
- exact error output.

For Flatpak device-access problems, also mention whether
`70-turing-smart-screen.rules` is installed on the host.

## Suggesting enhancements

Open an issue describing:

- the workflow you want to improve;
- the current behavior;
- the proposed behavior;
- affected hardware/theme type, if any;
- whether the idea is Linux/fork-specific or might also benefit upstream.

Prefer focused proposals over large unrelated feature bundles.

## Code contributions

### Set up a source checkout

```bash
git clone https://github.com/maylton/turing-smart-screen-video-overlay.git
cd turing-smart-screen-video-overlay

./install.sh --check-only
```

For normal end-user use, Flatpak is recommended. For development, a native/source
checkout is usually easier because project files remain directly editable.

### Create a branch

```bash
git switch main
git pull --ff-only
git switch -c your-topic-branch
```

Keep each pull request centered on one bug, feature or documentation goal where
practical.

### Validation

Run the checks relevant to your change. Before release-facing changes, run:

```bash
./scripts/verify-release-readiness.sh
```

For Flatpak changes, build from the manifest:

```bash
flatpak-builder \
  build-flatpak \
  --user \
  --install-deps-from=flathub \
  --force-clean \
  --install \
  packaging/flatpak/io.github.turing.SmartScreen.yml
```

The GitHub Actions Flatpak workflow also performs export smoke checks and verifies
that the AMD Python extension does not regress to a wheel containing private
`pyamdgpuinfo.libs` libdrm copies.

### Hardware-sensitive changes

Changes involving these areas require extra care:

- raw USB reset/recovery;
- Rev. C initialization;
- native video playback;
- display-side file upload/delete;
- power control;
- serial ownership/lifecycle.

Do not broaden or replace working hardware-recovery logic solely to work around a
packaging or permissions problem. Prefer first identifying whether the failure is
caused by host udev permissions, Flatpak device exposure, process ownership or the
actual device protocol.

When possible, document physical validation and the exact tested profile in the
pull request.

## Documentation contributions

Documentation fixes are welcome, especially for:

- new hardware validation;
- Linux distribution differences;
- Flatpak permissions/runtime behavior;
- theme authoring;
- installation/troubleshooting;
- reproducible bug findings.

Keep public documentation aligned with the current `main` branch and latest
stable release. Avoid instructions that point users to old feature branches.

## Relationship with upstream

This fork has a broader Linux desktop scope than upstream. Changes that are small,
platform-neutral and independently useful may be good candidates for the upstream
project, for example:

- protocol/hardware fixes;
- isolated helper functions;
- generic diagnostics;
- documentation corrections;
- small test improvements.

Large GTK application, Flatpak or fork-specific workflow changes generally belong
here unless upstream maintainers explicitly indicate otherwise.

## Development process disclosure

The fork has been developed with substantial AI assistance. Contributions should
still be understandable, reviewable and testable by humans. Generated code is not
exempt from normal correctness, licensing, safety or attribution requirements.

## Licensing

By contributing, you confirm that you have the right to submit your changes under
the repository's GPL-3.0-or-later license. See [`LICENSE`](LICENSE).
