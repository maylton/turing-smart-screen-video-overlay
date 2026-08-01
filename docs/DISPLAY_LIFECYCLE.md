# Passive display lifecycle

`library/display_lifecycle.py` provides one passive display state for CLI,
standalone GTK diagnostics and inline diagnostics. It never opens or writes to
the display serial port.

## States

| State | Meaning |
| --- | --- |
| `disconnected` | No supported serial descriptor was found. |
| `usbmonitor_waking` | UsbMonitor is visible, but the real ttyACM device is still appearing. |
| `tty_ready` | A real display ttyACM device exists and no owner was found. |
| `busy` | The application runtime lock or an external process owns the channel. |
| `running` | The monitor owns the channel, or a monitor PID was found as a fallback. |
| `unknown` | Serial enumeration failed and the state cannot be classified safely. |

## Priority

The classifier uses this order:

1. monitor runtime lock;
2. another application runtime operation;
3. monitor PID fallback when lock metadata is missing;
4. external serial ownership reported by `fuser`;
5. unowned real ttyACM device;
6. UsbMonitor descriptor while waking;
7. serial enumeration error;
8. disconnected.

The `fuser` check is best-effort, runs without root and never terminates a
process. On systems without `fuser`, a real unowned ttyACM descriptor is treated
as ready unless the application advisory lock says otherwise.

## Diagnostics payload

The JSON report contains:

```json
{
  "display_lifecycle": {
    "state": "tty_ready",
    "detail": "The display serial device is ready.",
    "devices": ["/dev/ttyACM0"],
    "owner_pids": [],
    "warning": ""
  }
}
```

UI surfaces translate the display label and detail, while the machine-readable
state remains stable in English.
