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

## CLI

```bash
python3 gpu-selection.py list
python3 gpu-selection.py show
python3 gpu-selection.py set auto
python3 gpu-selection.py set 1
```

An unavailable explicit index is rejected by the CLI. At runtime, a saved index
that is no longer present falls back safely to automatic selection.

## Temporary environment override

```bash
TURING_AMD_GPU_INDEX=0 python3 main.py
TURING_AMD_GPU_INDEX=auto python3 main.py
```

The environment override takes priority over the saved configuration and does
not modify the file.

## Diagnostics

Text, JSON, standalone GTK Diagnostics and inline Diagnostics report:

- configured mode and requested index;
- effective selected adapter;
- all detected AMD adapters;
- current load, temperature, VRAM usage and clock when supported by the driver.

Metric failures are isolated: one unsupported sensor does not prevent the other
values or the adapter list from being shown.
