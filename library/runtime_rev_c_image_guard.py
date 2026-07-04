# SPDX-License-Identifier: GPL-3.0-or-later
"""Runtime guard for Rev. C bitmap updates with offscreen coordinates.

Some themes intentionally place static images partially outside the canvas so the
visible area is cropped. The Rev. C low-level updater previously encoded the
raw negative address and crashed with ``OverflowError``. This guard clips the
transformed image before packet generation, and skips fully offscreen images.
"""

from __future__ import annotations

from PIL import Image

from library.lcd.lcd_comm import Orientation
from library.lcd.serialize import chunked, image_to_BGRA, image_to_BGR
from library.log import logger


def install_rev_c_image_bounds_guard() -> None:
    from library.lcd import lcd_comm_rev_c as rev_c

    if getattr(rev_c.LcdCommRevC, "_nocky_bounds_guard_installed", False):
        return

    Command = rev_c.Command
    Count = rev_c.Count
    Padding = rev_c.Padding
    SubRevision = rev_c.SubRevision

    def display_bounds(self) -> tuple[int, int, int]:
        """Return row limit, column limit, and row pitch for Rev. C packets."""
        if self.sub_revision == SubRevision.REV_8INCH:
            return self.display_height, self.display_width, self.display_width
        return self.display_width, self.display_height, self.display_height

    def transform_for_orientation(
        self,
        image: Image.Image,
        x: int,
        y: int,
    ) -> tuple[Image.Image, int, int]:
        x0, y0 = int(x), int(y)
        if self.sub_revision == SubRevision.REV_8INCH:
            if self.orientation == Orientation.LANDSCAPE:
                image = image.rotate(270, expand=True)
                y0 = self.get_height() - y - image.width
            elif self.orientation == Orientation.REVERSE_LANDSCAPE:
                image = image.rotate(90, expand=True)
                x0 = self.get_width() - x - image.height
            elif self.orientation == Orientation.PORTRAIT:
                image = image.rotate(180, expand=True)
                x0 = self.get_height() - y - image.height
                y0 = self.get_height() - x - image.width
            elif self.orientation == Orientation.REVERSE_PORTRAIT:
                x0 = y
                y0 = x
        else:
            if self.orientation == Orientation.PORTRAIT:
                image = image.rotate(90, expand=True)
                x0 = self.get_width() - x - image.height
            elif self.orientation == Orientation.REVERSE_PORTRAIT:
                image = image.rotate(270, expand=True)
                y0 = self.get_height() - y - image.width
            elif self.orientation == Orientation.REVERSE_LANDSCAPE:
                image = image.rotate(180)
                y0 = self.get_width() - x - image.width
                x0 = self.get_height() - y - image.height
            elif self.orientation == Orientation.LANDSCAPE:
                x0 = y
                y0 = x
        return image, int(x0), int(y0)

    def clip_update_image(
        self,
        image: Image.Image,
        x0: int,
        y0: int,
        original_x: int,
        original_y: int,
    ) -> tuple[Image.Image, int, int] | None:
        row_limit, column_limit, _pitch = display_bounds(self)
        crop_left = max(0, -y0)
        crop_top = max(0, -x0)
        crop_right = min(image.width, column_limit - y0)
        crop_bottom = min(image.height, row_limit - x0)

        if crop_right <= crop_left or crop_bottom <= crop_top:
            logger.warning(
                "Skipping Rev. C bitmap outside display bounds: original=(%s,%s) "
                "transformed=(%s,%s,%sx%s) bounds=%sx%s",
                original_x,
                original_y,
                x0,
                y0,
                image.width,
                image.height,
                column_limit,
                row_limit,
            )
            return None

        if (
            crop_left,
            crop_top,
            crop_right,
            crop_bottom,
        ) != (0, 0, image.width, image.height):
            logger.warning(
                "Clipping Rev. C bitmap to display bounds: original=(%s,%s) "
                "transformed=(%s,%s,%sx%s) crop=(%s,%s,%s,%s) bounds=%sx%s",
                original_x,
                original_y,
                x0,
                y0,
                image.width,
                image.height,
                crop_left,
                crop_top,
                crop_right,
                crop_bottom,
                column_limit,
                row_limit,
            )
            image = image.crop((crop_left, crop_top, crop_right, crop_bottom))
            x0 += crop_top
            y0 += crop_left

        return image, x0, y0

    def guarded_generate_update_image(
        self,
        image: Image.Image,
        x: int,
        y: int,
        count: int,
        cmd: Command | None = None,
    ):
        image, x0, y0 = transform_for_orientation(self, image, x, y)
        clipped = clip_update_image(self, image, x0, y0, x, y)
        if clipped is None:
            return None
        image, x0, y0 = clipped

        if self.sub_revision != SubRevision.REV_2INCH and self.rom_version > 88:
            img_data, pixel_size = image_to_BGRA(image)
        else:
            img_data, pixel_size = image_to_BGR(image)

        _row_limit, _column_limit, pitch = display_bounds(self)
        img_raw_data = bytearray()
        for h, line in enumerate(chunked(img_data, image.width * pixel_size)):
            address = ((x0 + h) * pitch) + y0
            if address < 0:
                logger.warning(
                    "Skipping invalid negative Rev. C bitmap address after clipping: %s",
                    address,
                )
                continue
            img_raw_data += int(address).to_bytes(3, "big")
            img_raw_data += int(image.width).to_bytes(2, "big")
            img_raw_data += line

        if not img_raw_data:
            logger.warning("Skipping Rev. C bitmap update with no visible rows")
            return None

        image_size = int(len(img_raw_data) + 2).to_bytes(3, "big")
        payload = bytearray()
        if cmd:
            payload.extend(cmd.value)
        payload.extend(image_size)
        payload.extend(Padding.NULL.value * 3)
        payload.extend(count.to_bytes(4, "big"))

        if len(img_raw_data) > 250:
            img_raw_data = bytearray(b"\x00").join(chunked(bytes(img_raw_data), 249))
        img_raw_data += b"\xef\x69"
        return img_raw_data, payload

    def guarded_display_pil_image(
        self,
        image: Image.Image,
        x: int = 0,
        y: int = 0,
        image_width: int = 0,
        image_height: int = 0,
    ):
        if not image_height:
            image_height = image.size[1]
        if not image_width:
            image_width = image.size[0]

        if image.size[1] > self.get_height():
            image_height = self.get_height()
        if image.size[0] > self.get_width():
            image_width = self.get_width()

        if image_width != image.size[0] or image_height != image.size[1]:
            image = image.crop((0, 0, image_width, image_height))

        if image_height <= 0 or image_width <= 0:
            logger.warning("Skipping Rev. C bitmap with invalid size %sx%s", image_width, image_height)
            return

        if self.video_overlay_enabled:
            self.DisplayPILImageOnVideoOverlay(
                image=image,
                x=x,
                y=y,
                image_width=image_width,
                image_height=image_height,
            )
            return

        if x == 0 and y == 0 and image_width == self.get_width() and image_height == self.get_height():
            with self.update_queue_mutex:
                self._send_command(Command.PRE_UPDATE_BITMAP)
                self._send_command(
                    Command.START_DISPLAY_BITMAP,
                    padding=Padding.START_DISPLAY_BITMAP,
                )

                if self.sub_revision == SubRevision.REV_5INCH:
                    display_bmp_cmd = Command.DISPLAY_BITMAP_5INCH
                elif self.sub_revision == SubRevision.REV_2INCH:
                    display_bmp_cmd = Command.DISPLAY_BITMAP_2INCH
                elif self.sub_revision == SubRevision.REV_8INCH:
                    display_bmp_cmd = Command.DISPLAY_BITMAP_8INCH
                else:
                    raise ValueError(
                        f"Unsupported Rev. C resolution: {self.display_width}x{self.display_height}"
                    )

                self._send_command(display_bmp_cmd)
                self._send_command(
                    Command.SEND_PAYLOAD,
                    payload=bytearray(self._generate_full_image(image)),
                    readsize=1024,
                )
                self._send_command(Command.QUERY_STATUS, readsize=1024)
            return

        with self.update_queue_mutex:
            result = self._generate_update_image(
                image,
                x,
                y,
                Count.Start,
                Command.UPDATE_BITMAP,
            )
            if result is None:
                return
            img, pyd = result
            self._send_command(Command.SEND_PAYLOAD, payload=pyd)
            self._send_command(Command.SEND_PAYLOAD, payload=img)
            self._send_command(Command.QUERY_STATUS, readsize=1024)
        Count.Start += 1

    rev_c.LcdCommRevC._generate_update_image = guarded_generate_update_image
    rev_c.LcdCommRevC.DisplayPILImage = guarded_display_pil_image
    rev_c.LcdCommRevC._nocky_bounds_guard_installed = True
    logger.debug("Installed Rev. C bitmap bounds guard")
