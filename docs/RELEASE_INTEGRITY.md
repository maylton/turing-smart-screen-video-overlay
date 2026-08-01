# Release and installation integrity

The validated installer entry point is:

```bash
bash install-checked.sh [install.sh options]
```

It performs three phases:

1. verifies that the source checkout contains the minimum coherent application
   tree, including translation and hardware-specific dependency profiles;
2. delegates the actual installation to the existing `install.sh`;
3. verifies the installed tree and writes `.installation.json` with the version,
   source commit, installation time, Python version, platform, locale and install
   mode.

## Inspect an installation

User installation:

```bash
python3 scripts/installation-report.py show \
  ~/.local/share/turing-smart-screen
```

System installation:

```bash
sudo python3 scripts/installation-report.py show \
  /opt/turing-smart-screen
```

A checkout with tracked modifications is recorded with a `-dirty` suffix. This
makes it clear when an installation was produced from locally edited code.

## Version policy

`VERSION` is the single human-readable application version. Development builds
use a suffix such as `0.9.0-dev1`. Stable releases should remove the development
suffix and receive a matching Git tag.
