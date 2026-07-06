# Apply + Sync + Start message testing

This note covers the small status-message and auto-refresh hooks added by the diagnostics integration branch.

## Scope

The patch surfaces clearer messages while the app performs the existing operations:

- changing the active theme;
- stopping/releasing the monitor;
- waiting for the real display port to settle;
- syncing/replacing the theme video;
- starting the monitor again.

It also keeps the existing Overview status cards fresh automatically, so the Monitor card should no longer require clicking Refresh to show the current state.

It does not change the runtime/video behavior itself.

## Expected visible messages

During an Apply + Sync + Start flow, the app may briefly show messages such as:

- `Preparing Apply + Sync + Start…`
- `Stopping monitor…`
- `Waiting for display…`
- `Syncing theme video…`
- `Waiting for wake-up…`
- `Starting monitor…`
- `Running`

Error paths should be clearer too, for example:

- `Video sync failed; starting monitor…`
- `Could not stop monitor`
- `Starting monitor…`

## Overview auto-refresh expectation

The Overview already has Theme, Monitor, and Display cards. This patch adds a lightweight timer that refreshes the existing Overview status while Overview is visible.

Expected behavior:

- start the monitor and wait up to a few seconds;
- the Monitor card should update without clicking Refresh;
- stop the monitor and wait up to a few seconds;
- the Monitor card should update back without clicking Refresh.

## Native video log expectation

The shared logger now filters only the repetitive successful frame-refresh DEBUG line:

- `Video overlay latest frame sent in ...`

Warnings, errors, startup logs, stop logs, and sync logs remain visible.

## Local validation

```bash
python3 -m py_compile \
  configure-gtk.py \
  diagnostics.py \
  diagnostics-gtk.py \
  usercustomize.py \
  library/log.py \
  library/main_app_apply_status.py \
  library/main_app_overview_refresh.py \
  library/main_app_inline_diagnostics.py \
  library/main_app_diagnostics_integration.py

bash -n install.sh
./install.sh
```

## Manual test path

1. Open the native app.
2. Confirm the existing Overview cards still show Theme, Monitor, and Display.
3. Start and stop the monitor from Overview and confirm the Monitor card updates automatically.
4. Pick/set a theme from the Theme Gallery using the flow that applies the theme, syncs video, and starts the monitor.
5. Watch the monitor/status area and toast messages during the operation.
6. Confirm that the terminal is no longer flooded by successful frame-refresh DEBUG lines.
7. Confirm that Settings → Maintenance → Diagnostics opens inline, or falls back to the standalone Diagnostics viewer.
8. Confirm that Start Monitor and Stop Monitor still work normally.

## Safety

The message hook only wraps UI status updates around existing methods. The Overview refresh hook only calls the app's existing Overview refresh while Overview is visible. The shared log filter only hides the repeated successful native-video frame-refresh DEBUG line. These changes do not open serial ports, send commands, upload files, start/stop processes, or change lock behavior by themselves.
