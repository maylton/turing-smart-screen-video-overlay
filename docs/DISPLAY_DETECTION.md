# Automatic display detection

The application passively scans serial and USB descriptors before loading the
display driver. Exact supported identifiers automatically update
`display.REVISION`, keep `config.COM_PORT` on `AUTO`, and select an installed
theme compatible with the detected size.

Shared identifiers are never applied silently. The CH340 identifier used by
Rev. A and Rev. B and the generic WeAct identifier are reported as ambiguous.

Rev. C awake descriptors identify the protocol but do not always identify the
physical size reliably. `CT21INCH` selects the 2.1-inch profile directly.
Other Rev. C descriptors preserve an already compatible active-theme size and
report that manual size confirmation may still be required.

Disable the feature with:

```yaml
display:
  AUTO_DETECT: false
```

The first automatic change creates `config.yaml.autodetect-backup`.

```bash
./venv/bin/python3 display-detection.py --json scan
./venv/bin/python3 display-detection.py --json apply
```
