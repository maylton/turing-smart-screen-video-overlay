# AMD GPU selection and sensor diagnostics

The default mode is **automatic**. The application enumerates AMD adapters with
`pyamdgpuinfo` and selects the device that reports the largest VRAM, which
normally distinguishes a discrete Radeon from a Ryzen integrated GPU.

## GTK selector

Open Diagnostics and press **GPU**, or run:

```bash
python3 gpu-selection-gtk.py
```

The selector offers:

- **Automatic — prefer the largest VRAM**;
- one entry for each detected AMD adapter, including index, available name and
  VRAM.

Restart the monitor after changing the preference. The configuration is stored
atomically at:

```text
$XDG_CONFIG_HOME/turing-smart-screen/hardware.json
```

or `~/.config/turing-smart-screen/hardware.json` when `XDG_CONFIG_HOME` is not
set.

An explicit selection stores both the current index and a fingerprint derived
from the adapter name and VRAM. If enumeration order changes after reboot, the
fingerprint relocates the same adapter to its new index. The stored index is used
as a deterministic tie-breaker for identical GPUs and for compatibility with
older preference files.

## CLI

```bash
python3 gpu-selection.py list
python3 gpu-selection.py show
python3 gpu-selection.py set auto
python3 gpu-selection.py set 1
```

An unavailable explicit index is rejected by the CLI. At runtime, a saved GPU
that is no longer present falls back safely to automatic selection rather than
silently choosing a different adapter at the old index.

## Temporary environment override

```bash
TURING_AMD_GPU_INDEX=0 python3 main.py
TURING_AMD_GPU_INDEX=auto python3 main.py
```

The environment override takes priority over the saved configuration and does
not modify the file. Because it is intentionally temporary, an index supplied
through the environment does not use the persistent fingerprint.

## Diagnostics

Text, JSON, standalone GTK Diagnostics and inline Diagnostics report:

- configured mode, requested index and stored fingerprint;
- effective selected adapter and effective fingerprint;
- all detected AMD adapters;
- current load, temperature, VRAM usage and clock when supported by the driver.

Metric failures are isolated: one unsupported sensor does not prevent the other
values or the adapter list from being shown.
