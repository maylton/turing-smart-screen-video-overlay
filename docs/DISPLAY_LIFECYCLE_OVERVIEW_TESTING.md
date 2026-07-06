# Display lifecycle Overview testing

This branch starts Milestone 2 by surfacing the display lifecycle state in the main app Overview.

## Scope

The implementation updates the existing Overview status row that previously showed `Connected display` / detection output. In this test branch it becomes a passive `Display state` row.

The row is refreshed after Overview refreshes and periodically while the app is open.

## Safety

This state reader is intentionally passive:

- it does not open the display serial port;
- it does not send commands to the display;
- it does not start or stop the monitor;
- it does not require root;
- it reads the runtime controller state and serial descriptors only.

## Expected states

- `Running`: the monitor process owns the display.
- `Busy`: another process owns the display lock/connection.
- `Ready`: a real `/dev/ttyACM*` display candidate is visible.
- `Waking`: a UsbMonitor endpoint is visible, but no real ttyACM display is ready yet.
- `Disconnected`: no real ttyACM display or UsbMonitor endpoint was detected.
- `Unknown`: runtime or serial inspection failed.

## Local validation

From the test worktree:

```bash
python3 -m py_compile \
  diagnostics.py \
  diagnostics-gtk.py \
  usercustomize.py \
  library/main_app_display_lifecycle.py \
  library/main_app_inline_diagnostics.py \
  library/main_app_diagnostics_integration.py

bash -n install.sh
./install.sh

pkill -KILL -f 'turing-smart-screen-main.py|configure-gtk.py|configure_gtk_app.py|theme-editor-gtk.py|video-manager-gtk.py|main.py|diagnostics.py|diagnostics-gtk.py' || true
~/.local/bin/turing-smart-screen
```

Then check:

1. Open **Overview**.
2. The Status group should show **Display state**.
3. The subtitle should update to one of the lifecycle states above.
4. Open **Settings → Maintenance → Diagnostics** and confirm the inline Diagnostics page still opens.
5. Use **Start monitor** and **Stop monitor** from Overview and confirm the Display state row updates.

## Notes

This patch intentionally does not change Apply + Start behavior yet. That belongs to the next Milestone 2 step after the passive Overview status is validated.
