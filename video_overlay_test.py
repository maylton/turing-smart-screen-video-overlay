#!/usr/bin/env python3

import sys
import time

from library.lcd.serialize import chunked
from library.lcd.lcd_comm import Orientation
from PIL import Image, ImageDraw, ImageFont

from library.lcd.lcd_comm_rev_c import (
    LcdCommRevC,
    Command,
    Padding,
    SleepInterval,
)


WIDTH = 480
HEIGHT = 480
VIDEO_PATH = "/mnt/SDCARD/video/24.mp4"


def pad_to_250(data: bytes) -> bytes:
    if len(data) > 250:
        raise ValueError("Command header is larger than 250 bytes")
    return data + b"\x00" * (250 - len(data))

def send_raw(lcd: LcdCommRevC, payload: bytearray, readsize=None):
    lcd._send_command(
        Command.SEND_PAYLOAD,
        payload=payload,
        bypass_queue=True,
        readsize=readsize,
    )


def make_path_command(opcode: int, path: str) -> bytearray:
    path_bytes = path.encode("utf-8")

    cmd = bytearray((opcode, 0xEF, 0x69, 0x00))
    cmd += len(path_bytes).to_bytes(3, "big")
    cmd += bytearray((0x00, 0x00, 0x00))
    cmd += path_bytes

    return cmd


def set_video_start_mode(lcd: LcdCommRevC):
    payload = (
        Command.STARTMODE_VIDEO.value
        + Padding.NULL.value
        + Command.NO_FLIP.value
        + SleepInterval.OFF.value
    )

    lcd._send_command(
        Command.OPTIONS,
        payload=payload,
        bypass_queue=True,
        readsize=1024,
    )


def play_video(lcd: LcdCommRevC):
    print(f"Playing video: {VIDEO_PATH}")

    set_video_start_mode(lcd)

    cmd = make_path_command(0x78, VIDEO_PATH)
    send_raw(lcd, cmd, readsize=1024)

    time.sleep(1)


def stop_video(lcd: LcdCommRevC):
    print("Stopping video...")

    lcd._send_command(Command.STOP_VIDEO, bypass_queue=True, readsize=1024)
    lcd._send_command(Command.STOP_MEDIA, bypass_queue=True, readsize=1024)


def make_overlay_image() -> Image.Image:
    """
    Full transparent 480x480 image with a visible test box.
    If alpha works correctly, only the box/text should appear over the video.
    """
    image = Image.new("RGBA", (WIDTH, HEIGHT), (255, 0, 0, 255))
    draw = ImageDraw.Draw(image)

    # Test box
    draw.rounded_rectangle(
        (80, 180, 400, 270),
        radius=16,
        fill=(0, 0, 0, 190),
        outline=(255, 255, 255, 255),
        width=3,
    )

    # Test text
    try:
        font = ImageFont.truetype("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", 32)
    except Exception:
        font = ImageFont.load_default()

    draw.text((115, 205), "VIDEO OVERLAY", fill=(255, 255, 255, 255), font=font)

    return image


def make_visible_pixels_fullscreen(width: int = WIDTH, height: int = HEIGHT) -> bytearray:
    """
    Build visible-pixels-info for the whole screen.

    Format from issue #90:
    start_position(3 bytes) + count(2 bytes), repeated,
    then 00 ef 69.

    For Rev. C 2.1"/2.8", normal code calculates position as:
    position = row * display_height + column
    Since width == height == 480, this is row * 480 + col.
    """
    data = bytearray()

    for row in range(height):
        start_position = row * height
        data += start_position.to_bytes(3, "big")
        data += width.to_bytes(2, "big")

    data += b"\x00\xef\x69"
    return data


def make_visible_pixels_fullscreen(width: int = WIDTH, height: int = HEIGHT) -> bytearray:
    """
    Mark only the test overlay box area as visible.

    The box is drawn roughly from:
    x=80 to 400
    y=180 to 270

    Since _generate_full_image rotates the image depending on orientation,
    this may still need adjustment, but it is a cleaner first visibility test
    than marking the whole screen.
    """
    data = bytearray()

    x_start = 80
    x_end = 400
    y_start = 180
    y_end = 270

    visible_width = x_end - x_start

    for y in range(y_start, y_end):
        start_position = y * HEIGHT + x_start
        data += start_position.to_bytes(3, "big")
        data += visible_width.to_bytes(2, "big")

    data += b"\x00\xef\x69"
    return data

def send_visible_pixels_info(lcd: LcdCommRevC):
    visible = make_visible_pixels_fullscreen()

    # Official TURZX format:
    # d0 ef 69 00 + visible_size as 3 bytes
    d0_header = bytearray((0xD0, 0xEF, 0x69, 0x00))
    d0_header += len(visible).to_bytes(3, "big")

    visible_chunked = bytearray(b"\x00".join(chunked(bytes(visible), 249)))

    print(f"Sending D0 visible-pixels info:")
    print(f"  logical size: {len(visible)}")
    print(f"  chunked size: {len(visible_chunked)}")

    payload = bytearray()
    payload += pad_to_250(d0_header)
    payload += visible_chunked

    send_raw(lcd, payload, readsize=1024)

def apply_video_overlay(lcd: LcdCommRevC):
    # Official TURZX sends this after D0.
    cf_command = bytearray((0xCF, 0xEF, 0x69, 0x00, 0x00, 0x00, 0x01))

    print("Sending CF apply video overlay command...")

    send_raw(lcd, bytearray(pad_to_250(cf_command)), readsize=1024)

def send_initial_video_overlay(lcd: LcdCommRevC):
    overlay = make_overlay_image()

    # For 480x480 BGRA:
    # 480 * 480 * 4 / 256 = 3600 = 0x0e10
    #
    # Normal image background uses C8.
    # Video background overlay uses CA.
    overlay_size = int(WIDTH * HEIGHT / 64).to_bytes(2, "big")
    cmd = bytearray((0xCA, 0xEF, 0x69, 0x00)) + overlay_size

    print("Sending initial video overlay image...")

    send_raw(lcd, cmd)

    # Reuse the project's own BGRA full-image serializer.
    # This preserves the same 249-byte chunking behavior used by DisplayPILImage().
    image_payload = bytearray(lcd._generate_full_image(overlay))
    send_raw(lcd, image_payload, readsize=1024)

    print("Sending visibility map...")
    send_visible_pixels_info(lcd)

def send_initial_video_overlay(lcd: LcdCommRevC):
    overlay = make_overlay_image()

    # 480x480 BGRA = 480 * 480 * 4 bytes.
    # The protocol size field is bytes / 256:
    # 480 * 480 * 4 / 256 = 3600 = 0x0e10
    overlay_size = int(WIDTH * HEIGHT / 64).to_bytes(2, "big")

    # Important:
    # The normal Rev. C fullscreen image path sends:
    # PRE_UPDATE_BITMAP -> START_DISPLAY_BITMAP -> C8 command -> image payload.
    #
    # For video background, we try the same preparation,
    # but replacing C8 with CA.
    video_overlay_cmd = bytearray((0xCA, 0xEF, 0x69, 0x00)) + overlay_size

    print("Preparing bitmap stream for video overlay...")

    lcd._send_command(
        Command.PRE_UPDATE_BITMAP,
        bypass_queue=True,
        readsize=1024,
    )

    lcd._send_command(
        Command.START_DISPLAY_BITMAP,
        padding=Padding.START_DISPLAY_BITMAP,
        bypass_queue=True,
    )

    print("Sending CA video overlay command...")

    # Mimic project's fullscreen C8 path:
    # it sends command + a repeated size payload.
    lcd._send_command(
        Command.SEND_PAYLOAD,
        payload=video_overlay_cmd,
        bypass_queue=True,
    )

    print("Sending video overlay image payload...")

    image_payload = bytearray(lcd._generate_full_image(overlay))

    lcd._send_command(
        Command.SEND_PAYLOAD,
        payload=image_payload,
        bypass_queue=True,
        readsize=1024,
    )

    print("Sending visibility map...")
    send_visible_pixels_info(lcd)

    print("Applying video overlay...")
    apply_video_overlay(lcd)

    lcd._send_command(
        Command.QUERY_STATUS,
        bypass_queue=True,
        readsize=1024,
    )

def query_status(lcd: LcdCommRevC):
    print("Querying render status...")
    lcd._send_command(Command.QUERY_STATUS, bypass_queue=True, readsize=1024)


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "run"

    lcd = LcdCommRevC(
        com_port="AUTO",
        display_width=WIDTH,
        display_height=HEIGHT,
        update_queue=None,
    )

    try:
        lcd.InitializeComm()
        # Do not call lcd.SetOrientation() here, because it sends STARTMODE_DEFAULT.
        # We only want to change how _generate_full_image() serializes the overlay.
        lcd.orientation = Orientation.LANDSCAPE

        if action == "stop":
            stop_video(lcd)
            return

        play_video(lcd)
        send_initial_video_overlay(lcd)
        query_status(lcd)

        print("")
        print("Test sent.")
        print("Expected result:")
        print("- video keeps moving")
        print("- box/text stays visible without flickering")
        print("")
        print("To stop video:")
        print("  python3 video_overlay_test.py stop")

    finally:
        lcd.closeSerial()


if __name__ == "__main__":
    main()
