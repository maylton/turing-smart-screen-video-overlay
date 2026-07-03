# SPDX-License-Identifier: GPL-3.0-or-later
from typing import Union, Tuple

from PIL import ImageColor

RGBColor = Tuple[int, int, int]
RGBAColor = Tuple[int, int, int, int]

# Color can be an RGB/RGBA tuple, or a string in any of these formats:
# - "r, g, b" (e.g. "255, 0, 0"), as is found in the themes' yaml settings
# - "r, g, b, a" (e.g. "255, 0, 0, 128")
# - any of the formats supported by PIL: https://pillow.readthedocs.io/en/stable/reference/ImageColor.html 
#
# For example, here are multiple ways to write the pure red color:
# - (255, 0, 0)
# - "255, 0, 0"
# - "#ff0000"
# - "red"
# - "hsl(0, 100%, 50%)"
Color = Union[str, RGBColor, RGBAColor]

def parse_color(color: Color) -> Union[RGBColor, RGBAColor]:
    # even if undocumented, let's be nice and accept a list in lieu of a tuple
    if isinstance(color, tuple) or isinstance(color, list):
        if len(color) not in (3, 4):
            raise ValueError("RGB/RGBA color must have 3 or 4 values")
        return tuple(int(component) for component in color)

    if not isinstance(color, str):
        raise ValueError("Color must be either an RGB tuple or a string")

    # Try to parse it as our custom "r, g, b" format
    rgb = color.split(',')
    if len(rgb) in (3, 4):
        try:
            rgbcolor = tuple(int(part.strip()) for part in rgb)
        except ValueError:
            # at least one element can't be converted to int, we continue to
            # try parsing as a PIL color
            pass
        else:
            return rgbcolor

    # fallback as a PIL color
    rgbcolor = ImageColor.getrgb(color)
    return rgbcolor
