# Diagnostics viewer testing

This branch adds a GTK diagnostics viewer as the first UI step after the safe CLI collector.

## What to test

1. The CLI collector still works:

   ```bash
   python3 -m py_compile \
     diagnostics.py \
     diagnostics-gtk.py \
     usercustomize.py \
     library/main_app_diagnostics_integration.py

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
   - The page does not stop/start the monitor and does not open the display serial port.

4. The main app exposes the viewer from Settings:

   ```bash
   python3 configure-gtk.py
   ```

   Then open:

   ```text
   Settings → Maintenance → Diagnostics
   ```

   The Diagnostics row should open the same standalone viewer.

## Notes

The diagnostics viewer is now reachable from the main GTK app, but it still runs as a separate process and remains safe: it reads configuration, process state, and USB descriptors without opening the display serial port.
