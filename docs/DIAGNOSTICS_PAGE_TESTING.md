# Diagnostics viewer testing

This branch adds a GTK diagnostics viewer as the first UI step after the safe CLI collector.
It now also includes the first passive display lifecycle state model used by the Diagnostics page.

## What to test

1. The CLI collector still works:

   ```bash
   python3 -m py_compile \
     diagnostics.py \
     diagnostics-gtk.py \
     usercustomize.py \
     library/display_lifecycle.py \
     library/main_app_diagnostics_integration.py \
     library/main_app_inline_diagnostics.py

   python3 diagnostics.py
   python3 diagnostics.py --json
   ```

2. The standalone GTK viewer opens:

   ```bash
   python3 diagnostics-gtk.py
   ```

3. In the standalone viewer:

   - Refresh updates the cards and full report.
   - Copy diagnostics puts the text report on the clipboard.
   - JSON copies the machine-readable report.
   - The Display card shows a lifecycle label such as `Ready`, `Running`, `Busy`, `Waking`, `Disconnected`, or `Unknown`.
   - The page does not stop/start the monitor and does not open the display serial port.

4. The main app exposes the inline viewer from Settings:

   ```bash
   ./install.sh
   pkill -KILL -f 'turing-smart-screen-main.py|configure-gtk.py|configure_gtk_app.py|theme-editor-gtk.py|video-manager-gtk.py|main.py|diagnostics.py|diagnostics-gtk.py' || true
   ~/.local/bin/turing-smart-screen
   ```

   Then open:

   ```text
   Settings → Maintenance → Diagnostics
   ```

   The Diagnostics row should open inside the same native app window.

## Display lifecycle states

The passive lifecycle model intentionally does not open the serial port. It reads serial descriptors,
monitor process state, and best-effort device ownership with `fuser` when available.

Expected initial states:

- `disconnected`: no real `/dev/ttyACM*` display and no UsbMonitor endpoint detected.
- `usbmonitor_waking`: a UsbMonitor endpoint is visible, but no real ttyACM display is ready yet.
- `tty_ready`: a real `/dev/ttyACM*` candidate is present and no monitor process is detected.
- `busy`: a real ttyACM candidate appears to be owned by another process.
- `running`: the app monitor process is detected.
- `unknown`: serial enumeration or passive detection failed before a reliable state could be inferred.

## Notes

The diagnostics viewer is reachable from the main GTK app and remains safe: it reads configuration,
process state, and USB descriptors without opening the display serial port.
