"""Safe passive detection and automatic configuration for supported displays."""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

SIZES = {
    '0.96"': (80, 160), '2.1"': (480, 480), '2.8"': (480, 480),
    '3.5"': (320, 480), '4.6"': (320, 960), '5"': (480, 800),
    '5.2"': (720, 1280), '8"': (800, 1280), '8.8"': (480, 1920),
    '9.2"': (480, 1920), '12.3"': (720, 1920),
}
USB_MODELS = {
    0x0028: ("Turing Smart Screen 2.8-inch round", '2.8"', 480, 480),
    0x0046: ("Turing Smart Screen 4.6-inch", '4.6"', 320, 960),
    0x0050: ("Turing Smart Screen 5.2-inch", '5.2"', 720, 1280),
    0x0080: ("Turing Smart Screen 8-inch", '8"', 800, 1280),
    0x0088: ("Turing Smart Screen 8.8-inch", '8.8"', 480, 1920),
    0x0092: ("Turing Smart Screen 9.2-inch", '9.2"', 480, 1920),
    0x0123: ("Turing Smart Screen 12.3-inch", '12.3"', 720, 1920),
}
REV_C_IDS = {(0x1A86, 0xCA21), (0x0525, 0xA4A7), (0x1D6B, 0x0121), (0x1D6B, 0x0106)}
ALIASES = {'2.1"': {'2.1"', '2.8"'}, '2.8"': {'2.8"', '2.1"'}, '9.2"': {'9.2"', '8.8"'}}


@dataclass(frozen=True)
class Detection:
    id: str
    label: str
    revision: str | None
    display_size: str | None
    width: int | None
    height: int | None
    transport: str
    device: str | None
    vid: int | None
    pid: int | None
    serial_number: str | None
    confidence: int
    safe: bool
    complete: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["vid_hex"] = f"{self.vid:04x}" if self.vid is not None else None
        data["pid_hex"] = f"{self.pid:04x}" if self.pid is not None else None
        return data


@dataclass(frozen=True)
class Report:
    enabled: bool
    detections: tuple[Detection, ...]
    selected: Detection | None
    applied: bool
    changed: bool
    previous_revision: str | None
    current_revision: str | None
    previous_theme: str | None
    current_theme: str | None
    message: str
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "detections": [item.to_dict() for item in self.detections],
            "selected": self.selected.to_dict() if self.selected else None,
            "applied": self.applied,
            "changed": self.changed,
            "previous_revision": self.previous_revision,
            "current_revision": self.current_revision,
            "previous_theme": self.previous_theme,
            "current_theme": self.current_theme,
            "message": self.message,
            "warnings": list(self.warnings),
        }


def _get(obj: Any, name: str, default: Any = None) -> Any:
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


def _number(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _scalar(text: str, key: str) -> str:
    match = re.search(rf'(?m)^\s*{re.escape(key)}\s*:\s*["\']?([^"\'\n#]+)', text)
    return match.group(1).strip() if match else ""


def _normalize_size(value: str | None) -> str:
    match = re.search(r"(\d+(?:[\.,]\d+)?)", str(value or ""))
    return f'{match.group(1).replace(",", ".")}"' if match else ""


def _make(
    ident: str,
    label: str,
    revision: str | None,
    display_size: str | None,
    transport: str,
    device: str | None,
    vid: int | None,
    pid: int | None,
    serial: str | None,
    confidence: int,
    safe: bool,
    complete: bool,
    reason: str,
) -> Detection:
    width, height = SIZES.get(display_size, (None, None))
    return Detection(
        ident, label, revision, display_size, width, height, transport,
        device, vid, pid, serial, confidence, safe, complete, reason,
    )


def _active_hint(root: str | os.PathLike[str]) -> tuple[str, str]:
    root = Path(root)
    config = _read(root / "config.yaml")
    revision = _scalar(config, "REVISION").upper()
    theme = _scalar(config, "THEME")
    theme_yaml = _read(root / "res" / "themes" / theme / "theme.yaml")
    return revision, _normalize_size(_scalar(theme_yaml, "DISPLAY_SIZE"))


def _rev_c_detection(root: str | os.PathLike[str], device: str, vid: int | None, pid: int | None, serial: str | None) -> Detection:
    revision, display_size = _active_hint(root)
    if revision == "C" and display_size in {'2.1"', '2.8"', '5"', '8.8"'}:
        return _make(
            f"rev-c-hint:{device}",
            f"Turing Rev. C ({display_size} retained from active theme)",
            "C", display_size, "serial", device, vid, pid, serial, 72, True, False,
            "Rev. C identifies the protocol, but not physical size reliably; the compatible active-theme size is retained.",
        )
    return _make(
        f"rev-c-unknown:{device}",
        "Turing Rev. C — size requires confirmation",
        "C", None, "serial", device, vid, pid, serial, 65, True, False,
        "Rev. C cannot safely distinguish 2.1/2.8/5/8.8-inch variants; revision is applied and the theme is preserved.",
    )


def detect_serial(ports: Sequence[Any], root: str | os.PathLike[str]) -> list[Detection]:
    output: list[Detection] = []
    for port in ports:
        device = str(_get(port, "device", _get(port, "name", "")) or "")
        vid, pid = _number(_get(port, "vid")), _number(_get(port, "pid"))
        serial = _get(port, "serial_number")
        serial = str(serial) if serial not in (None, "") else None
        upper = (serial or "").upper()
        identity = (vid, pid)

        if upper == "USB35INCHIPSV2":
            output.append(_make(f"a:{device}", "Turing/UsbPCMonitor Rev. A 3.5-inch", "A", '3.5"', "serial", device, vid, pid, serial, 100, True, True, "Exact USB35INCHIPSV2 descriptor."))
        elif upper == "2017-2-25":
            output.append(_make(f"b:{device}", "XuanFang Rev. B/flagship 3.5-inch", "B", '3.5"', "serial", device, vid, pid, serial, 100, True, True, "Exact XuanFang descriptor."))
        elif upper == "CT21INCH":
            output.append(_make(f"c21:{device}", "Turing Smart Screen Rev. C 2.1-inch", "C", '2.1"', "serial", device, vid, pid, serial, 100, True, True, "Exact CT21INCH sleeping-device descriptor."))
        elif upper in {"USB7INCH", "20080411"} or identity in REV_C_IDS:
            output.append(_rev_c_detection(root, device, vid, pid, serial))
        elif identity == (0x454D, 0x4E41):
            output.append(_make(f"d:{device}", "Kipye Qiye Rev. D 3.5-inch", "D", '3.5"', "serial", device, vid, pid, serial, 95, True, True, "Unique Kipye VID:PID 454d:4e41."))
        elif upper.startswith("AB"):
            output.append(_make(f"weact-a:{device}", "WeAct Studio FS V1 3.5-inch", "WEACT_A", '3.5"', "serial", device, vid, pid, serial, 95, True, True, "WeAct 3.5-inch serial prefix AB."))
        elif upper.startswith("AD"):
            output.append(_make(f"weact-b:{device}", "WeAct Studio FS V1 0.96-inch", "WEACT_B", '0.96"', "serial", device, vid, pid, serial, 95, True, True, "WeAct 0.96-inch serial prefix AD."))
        elif identity == (0x1A86, 0x5722):
            output.append(_make(f"ambiguous-a-b:{device}", "Compatible CH340 display — Rev. A/B ambiguous", None, None, "serial", device, vid, pid, serial, 30, False, False, "VID:PID 1a86:5722 is shared by Rev. A and Rev. B."))
        elif identity == (0x1A86, 0xFE0C):
            output.append(_make(f"ambiguous-weact:{device}", "WeAct display — size ambiguous", None, None, "serial", device, vid, pid, serial, 30, False, False, "VID:PID 1a86:fe0c is shared by WeAct 0.96 and 3.5-inch models."))
    return output


def detect_usb(devices: Iterable[Any]) -> list[Detection]:
    output: list[Detection] = []
    for device in devices:
        vid = _number(_get(device, "idVendor", _get(device, "vid")))
        pid = _number(_get(device, "idProduct", _get(device, "pid")))
        if vid == 0x1CBE and pid in USB_MODELS:
            label, display_size, width, height = USB_MODELS[pid]
            output.append(Detection(
                f"turing-usb:{pid:04x}", label, "TUR_USB", display_size,
                width, height, "usb", f"usb:{vid:04x}:{pid:04x}",
                vid, pid, None, 100, True, True,
                f"Unique Turing USB product ID {vid:04x}:{pid:04x}.",
            ))
    return output


def system_ports() -> list[Any]:
    try:
        from serial.tools.list_ports import comports
        return list(comports())
    except Exception:
        return []


def system_usb() -> list[Any]:
    try:
        import usb.core
        return list(usb.core.find(find_all=True) or [])
    except Exception:
        return []


def _detect_raw_before_endpoint_grouping(root: str | os.PathLike[str], ports: Sequence[Any] | None = None, usb_devices: Sequence[Any] | None = None) -> list[Detection]:
    items = detect_serial(system_ports() if ports is None else list(ports), root)
    items.extend(detect_usb(system_usb() if usb_devices is None else list(usb_devices)))
    unique: list[Detection] = []
    seen: set[tuple[Any, ...]] = set()
    for item in sorted(items, key=lambda entry: entry.confidence, reverse=True):
        key = (item.transport, item.device, item.vid, item.pid)
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique

def detect(*args, **kwargs):
    items = list(_detect_raw_before_endpoint_grouping(*args, **kwargs))

    # One Rev. C screen may expose two serial endpoints simultaneously:
    # an exact sleeping endpoint such as CT21INCH and an awake CDC endpoint.
    # Keep only the exact/complete item in user-facing detection results.
    complete_models = {
        (
            getattr(item, "revision", None),
            getattr(item, "display_size", None),
        )
        for item in items
        if getattr(item, "safe", getattr(item, "safe_to_apply", False))
        and getattr(item, "complete", getattr(item, "configuration_complete", False))
        and getattr(item, "revision", None)
        and getattr(item, "display_size", None)
    }

    return [
        item
        for item in items
        if not (
            getattr(item, "safe", getattr(item, "safe_to_apply", False))
            and not getattr(
                item,
                "complete",
                getattr(item, "configuration_complete", False),
            )
            and (
                getattr(item, "revision", None),
                getattr(item, "display_size", None),
            )
            in complete_models
        )
    ]


def select(items: Sequence[Detection]) -> Detection | None:
    safe = sorted((item for item in items if item.safe and item.revision), key=lambda item: item.confidence, reverse=True)
    if not safe:
        return None
    if len(safe) > 1 and safe[1].confidence == safe[0].confidence:
        return None
    return safe[0]


def enabled(root: str | os.PathLike[str]) -> bool:
    value = _scalar(_read(Path(root) / "config.yaml"), "AUTO_DETECT").lower()
    return value not in {"0", "false", "no", "off", "disabled"}


def _set_scalar(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"(?m)^(\s*{re.escape(key)}\s*:\s*).*$")
    rendered = f'"{value}"' if key in {"THEME", "COM_PORT"} else value
    return pattern.sub(lambda match: match.group(1) + rendered, text, count=1) if pattern.search(text) else text


def _ensure_enabled(text: str) -> str:
    if re.search(r"(?m)^\s*AUTO_DETECT\s*:", text):
        return _set_scalar(text, "AUTO_DETECT", "true")
    match = re.search(r"(?m)^display\s*:\s*$", text)
    if match:
        return text[:match.end()] + "\n  AUTO_DETECT: true" + text[match.end():]
    return text.rstrip() + "\n\ndisplay:\n  AUTO_DETECT: true\n"


def compatible_themes(root: str | os.PathLike[str], display_size: str) -> list[str]:
    accepted = ALIASES.get(display_size, {display_size})
    result: list[str] = []
    themes = Path(root) / "res" / "themes"
    try:
        entries = sorted(themes.iterdir(), key=lambda path: path.name.casefold())
    except OSError:
        return result
    for directory in entries:
        theme_yaml = directory / "theme.yaml"
        if directory.is_dir() and theme_yaml.is_file():
            if _normalize_size(_scalar(_read(theme_yaml), "DISPLAY_SIZE")) in accepted:
                result.append(directory.name)
    return result


def apply_detection(root: str | os.PathLike[str], detection: Detection) -> Report:
    root = Path(root)
    config_path = root / "config.yaml"
    original = _read(config_path)
    if not original:
        raise FileNotFoundError(config_path)
    if not detection.safe or not detection.revision:
        raise ValueError("Ambiguous detection cannot be applied safely.")

    previous_revision = _scalar(original, "REVISION").upper() or None
    previous_theme = _scalar(original, "THEME") or None
    updated = _ensure_enabled(_set_scalar(_set_scalar(original, "REVISION", detection.revision), "COM_PORT", "AUTO"))
    warnings: list[str] = []

    if detection.complete and detection.display_size:
        matches = compatible_themes(root, detection.display_size)
        if previous_theme not in matches:
            if matches:
                updated = _set_scalar(updated, "THEME", matches[0])
            else:
                warnings.append(f"No installed theme matches {detection.display_size}; current theme preserved.")
    else:
        warnings.append("Physical size was not reliable; current theme preserved.")

    changed = updated != original
    if changed:
        backup = config_path.with_suffix(".yaml.autodetect-backup")
        if not backup.exists():
            shutil.copy2(config_path, backup)
        temporary = config_path.with_suffix(".yaml.autodetect.tmp")
        temporary.write_text(updated, encoding="utf-8")
        os.replace(temporary, config_path)

    return Report(
        True, (detection,), detection, True, changed,
        previous_revision, _scalar(updated, "REVISION").upper() or None,
        previous_theme, _scalar(updated, "THEME") or None,
        f"Detected {detection.label}. " + ("Configuration updated." if changed else "Configuration already matches."),
        tuple(warnings),
    )


def auto_configure(root: str | os.PathLike[str], ports: Sequence[Any] | None = None, usb_devices: Sequence[Any] | None = None, apply: bool = True) -> Report:
    root = Path(root)
    config = _read(root / "config.yaml")
    previous_revision = _scalar(config, "REVISION").upper() or None
    previous_theme = _scalar(config, "THEME") or None
    if not enabled(root):
        return Report(False, (), None, False, False, previous_revision, previous_revision, previous_theme, previous_theme, "Automatic detection is disabled.")

    items = tuple(detect(root, ports, usb_devices))
    chosen = select(items)
    if not chosen:
        message = "No supported display detected." if not items else "Detection is ambiguous; configuration was not changed."
        return Report(True, items, None, False, False, previous_revision, previous_revision, previous_theme, previous_theme, message, tuple(item.reason for item in items if not item.safe))
    if not apply:
        return Report(True, items, chosen, False, False, previous_revision, previous_revision, previous_theme, previous_theme, f"Detected {chosen.label}; dry run only.")
    applied = apply_detection(root, chosen)
    return Report(True, items, chosen, True, applied.changed, applied.previous_revision, applied.current_revision, applied.previous_theme, applied.current_theme, applied.message, applied.warnings)
