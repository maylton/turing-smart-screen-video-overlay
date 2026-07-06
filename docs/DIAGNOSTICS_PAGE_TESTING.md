# Diagnostics viewer testing

This branch adds a standalone GTK diagnostics viewer as the first UI step after the safe CLI collector.

## What to test

1. The CLI collector still works:

   ```bash
   python3 -m py_compile diagnostics.py diagnostics-gtk.py
   python3 diagnostics.py
   python3 diagnostics.py --json
   ```

2. The standalone GTK viewer opens:

   ```bash
   python3 diagnostics-gtk.py
   ```

3. In the viewer:

   - Refresh updates the cards and full report.
   - Copy diagnostics puts the report on the clipboard.
   - The page does not stop/start the monitor and does not open the display serial port.

## Notes

This is intentionally not merged into the main app sidebar yet. Keeping it standalone first makes the diagnostics UI safer to test before wiring it into the main GTK launcher.
