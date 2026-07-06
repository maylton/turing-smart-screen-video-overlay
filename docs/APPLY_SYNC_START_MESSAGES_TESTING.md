# Apply + Sync + Start message testing

This test note belongs to the Diagnostics/Main App draft branch. It adds clearer user-facing progress messages to the existing Apply + Sync + Start flow without creating a separate PR.

## Scope

The patch surfaces clearer messages while the app performs the existing operations:

- changing the active theme;
- stopping/releasing the monitor;
- waiting for the real display port to settle;
- syncing/replacing the theme video;
- preserving single-video display storage behavior;
- starting the monitor again.

It does not change the runtime/video behavior itself.

## Expected visible messages

During an Apply + Sync + Start flow, the app may briefly show messages such as:

- `Preparing Apply + Sync + Start…`
- `Stopping monitor…`
- `Waiting for display…`
- `Syncing theme video…`
- `Cleaning old video…`
- `Waiting for wake-up…`
- `Starting monitor…`
- `Monitor started`

Error paths should be clearer too, for example:

- `Video sync failed; starting monitor…`
- `Could not stop monitor`
- `Monitor did not stay running`

## Local validation

```bash
python3 -m py_compile \
  diagnostics.py \
  diagnostics-gtk.py \
  usercustomize.py \
  library/main_app_apply_status.py \
  library/main_app_inline_diagnostics.py \
  library/main_app_diagnostics_integration.py

bash -n install.sh
./install.sh

pkill -KILL -f 'turing-smart-screen-main.py|configure-gtk.py|configure_gtk_app.py|theme-editor-gtk.py|video-manager-gtk.py|main.py|diagnostics.py|diagnostics-gtk.py' || true
~/.local/bin/turing-smart-screen
```

## Manual test path

1. Open the native app.
2. Confirm the existing Overview cards still show Theme, Monitor, and Display.
3. Pick/set a theme from the Theme Gallery using the flow that applies the theme, syncs video, and starts the monitor.
4. Watch the monitor/status area and toast messages during the operation.
5. Confirm that Settings → Maintenance → Diagnostics still opens inline.
6. Confirm that Start Monitor and Stop Monitor still work normally.

## Safety

The message hook only wraps UI status updates around existing methods. It does not open serial ports, send commands, upload files, start/stop processes, or change lock behavior by itself.
