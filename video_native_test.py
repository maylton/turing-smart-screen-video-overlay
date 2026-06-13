#!/usr/bin/env python3

import sys
import time

from library.lcd.lcd_comm_rev_c import (
    LcdCommRevC,
    Command,
    Padding,
    SleepInterval,
)


def make_path_command(opcode: int, path: str) -> bytearray:
    """
    Rev. C path command format based on documented UsbMonitor commands:
    OP ef 69 00 + path_length(3 bytes) + 00 00 00 + UTF-8 path
    """
    path_bytes = path.encode("utf-8")
    command = bytearray((opcode, 0xEF, 0x69, 0x00))
    command += len(path_bytes).to_bytes(3, "big")
    command += bytearray((0x00, 0x00, 0x00))
    command += path_bytes
    return command


def send_raw(lcd: LcdCommRevC, payload: bytearray, readsize: int = 1024):
    lcd._send_command(
        Command.SEND_PAYLOAD,
        payload=payload,
        bypass_queue=True,
        readsize=readsize,
    )


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


def list_videos(lcd: LcdCommRevC):
    paths = [
        "/root/video/",
        "/mnt/SDCARD/video/",
    ]

    for path in paths:
        print(f"\nListing videos in: {path}")
        lcd.serial_flush_input()

        command = make_path_command(0x65, path)
        lcd._send_command(
            Command.SEND_PAYLOAD,
            payload=command,
            bypass_queue=True,
        )

        time.sleep(0.5)
        response = lcd.serial_readall()

        print(response)
        print(response.decode(errors="ignore"))


def play_video(lcd: LcdCommRevC, path: str):
    print(f"Trying to play video: {path}")

    set_video_start_mode(lcd)

    command = make_path_command(0x78, path)
    send_raw(lcd, command)

    print("Play command sent.")


def stop_video(lcd: LcdCommRevC):
    print("Stopping video...")
    lcd._send_command(Command.STOP_VIDEO, bypass_queue=True, readsize=1024)
    lcd._send_command(Command.STOP_MEDIA, bypass_queue=True, readsize=1024)
    print("Stop commands sent.")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 video_native_test.py list")
        print("  python3 video_native_test.py play /root/video/example.mp4")
        print("  python3 video_native_test.py stop")
        sys.exit(1)

    action = sys.argv[1]

    lcd = LcdCommRevC(
        com_port="AUTO",
        display_width=480,
        display_height=480,
        update_queue=None,
    )

    try:
        lcd.InitializeComm()

        if action == "list":
            list_videos(lcd)

        elif action == "play":
            if len(sys.argv) < 3:
                print("Missing video path.")
                print("Example:")
                print("  python3 video_native_test.py play /root/video/example.mp4")
                sys.exit(1)

            play_video(lcd, sys.argv[2])

        elif action == "stop":
            stop_video(lcd)

        else:
            print(f"Unknown action: {action}")
            sys.exit(1)

    finally:
        lcd.closeSerial()


if __name__ == "__main__":
    main()
