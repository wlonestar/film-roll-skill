#!/usr/bin/env python3
"""Build the five individually composed reference textures as ordinary raster images."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ARTWORK = ROOT / "examples" / "artwork"
SIZE = (4096, 2048)
FONTS = {
    "regular": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "bold": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "condensed": "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf",
    "condensed_bold": "/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf",
    "italic": "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf",
    "bold_italic": "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
}


def box(rect):
    return tuple(round(value * limit) for value, limit in zip(rect, (SIZE[0], SIZE[1], SIZE[0], SIZE[1])))


def text(image, value, rect, color, face="bold", rotation=0, align="center",
         shadow_color=None, shadow_opacity=0.28, shadow_offset=(12, 14), shadow_blur=9):
    x0, y0, x1, y1 = box(rect)
    max_width, max_height = x1 - x0, y1 - y0
    font_path = FONTS[face]
    measure = ImageDraw.Draw(Image.new("L", (1, 1)))

    def fit(size):
        font = ImageFont.truetype(font_path, size)
        bounds = measure.multiline_textbbox((0, 0), value, font=font,
                                            spacing=max(1, size // 8), align=align)
        width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
        radians = math.radians(rotation)
        out_width = abs(width * math.cos(radians)) + abs(height * math.sin(radians))
        out_height = abs(width * math.sin(radians)) + abs(height * math.cos(radians))
        return font, bounds, out_width, out_height

    low, high, selected = 1, SIZE[1], 1
    while low <= high:
        candidate = (low + high) // 2
        _, _, width, height = fit(candidate)
        if width <= max_width and height <= max_height:
            selected = candidate
            low = candidate + 1
        else:
            high = candidate - 1

    font, bounds, _, _ = fit(selected)
    tile = Image.new("RGBA", (max(1, bounds[2] - bounds[0] + 4),
                               max(1, bounds[3] - bounds[1] + 4)), (0, 0, 0, 0))
    ImageDraw.Draw(tile).multiline_text((2 - bounds[0], 2 - bounds[1]), value,
                                        font=font, fill=color,
                                        spacing=max(1, selected // 8), align=align)
    if rotation:
        tile = tile.rotate(-rotation, expand=True, resample=Image.Resampling.BICUBIC)
    scale = min(max_width / tile.width, max_height / tile.height, 1)
    if scale < 1:
        tile = tile.resize((max(1, round(tile.width * scale)), max(1, round(tile.height * scale))),
                           Image.Resampling.LANCZOS)
    x = x0 if align == "left" else x1 - tile.width if align == "right" else x0 + (max_width - tile.width) // 2
    y = y0 + (max_height - tile.height) // 2
    if shadow_color:
        mask = tile.getchannel("A").filter(ImageFilter.GaussianBlur(shadow_blur))
        mask = mask.point(lambda value: round(value * shadow_opacity))
        shadow = Image.new("RGBA", tile.size, shadow_color)
        shadow.putalpha(mask)
        image.alpha_composite(shadow, (x + shadow_offset[0], y + shadow_offset[1]))
    image.alpha_composite(tile, (x, y))


def rect(image, area, color):
    ImageDraw.Draw(image).rectangle(box(area), fill=color)


def line(image, points, color, width=8):
    pixels = [(round(x * SIZE[0]), round(y * SIZE[1])) for x, y in points]
    ImageDraw.Draw(image).line(pixels, fill=color, width=width, joint="curve")


def finish(slug, image):
    ARTWORK.mkdir(parents=True, exist_ok=True)
    path = ARTWORK / f"{slug}.png"
    image.convert("RGB").save(path, optimize=True)
    print(f"Wrote {path} ({path.stat().st_size} bytes)")


def ultramax():
    # The supplied collage shows the canister with a yellow wrap, not the blue retail box.
    image = Image.new("RGBA", SIZE, "#EAB822")
    rect(image, (0.365, 0, 0.425, 1), "#171817")
    rect(image, (0.425, 0, 0.438, 1), "#D6A51D")
    line(image, [(0.438, 0.08), (0.64, 0.08)], "#C7282B", 13)
    text(image, "KODAK", (0.445, 0.095, 0.62, 0.19), "#C7282B", "bold")
    text(image, "400", (0.445, 0.21, 0.61, 0.79), "#171817", "condensed_bold", rotation=90)
    text(image, "35mm COLOR PRINT FILM", (0.37, 0.20, 0.42, 0.72), "#F0EBD8", "condensed", rotation=90)
    text(image, "36 EXP", (0.37, 0.75, 0.42, 0.91), "#F0EBD8", "condensed_bold", rotation=90)
    text(image, "KODAK COLOR", (0.44, 0.83, 0.62, 0.91), "#171817", "condensed")
    finish("kodak-ultramax-400", image)


def gold_200():
    image = Image.new("RGBA", SIZE, "#EAB51C")
    rect(image, (0.36, 0, 0.415, 1), "#151615")
    rect(image, (0.415, 0, 0.429, 1), "#C6282B")
    text(image, "200", (0.365, 0.12, 0.41, 0.78), "#EAB51C", "condensed_bold", rotation=90)
    text(image, "36 EXP", (0.365, 0.79, 0.41, 0.93), "#EAB51C", "condensed_bold", rotation=90)
    text(image, "KODAK", (0.44, 0.12, 0.60, 0.22), "#C6282B", "bold")
    text(image, "200", (0.435, 0.25, 0.61, 0.70), "#151615", "condensed_bold", rotation=90)
    text(image, "35mm COLOR PRINT FILM", (0.435, 0.74, 0.61, 0.81), "#151615", "condensed")
    finish("kodak-gold-200", image)


def ektar_100():
    image = Image.new("RGBA", SIZE, "#171819")
    rect(image, (0.397, 0, 0.566, 1), "#E8AC24")
    rect(image, (0.566, 0, 0.584, 1), "#CF8E18")
    text(image, "Ektar 100", (0.408, 0.12, 0.55, 0.73), "#171819", "condensed_bold", rotation=90)
    text(image, "KODAK PROFESSIONAL", (0.408, 0.77, 0.55, 0.85), "#171819", "condensed")
    text(image, "COLOR NEGATIVE FILM", (0.408, 0.87, 0.55, 0.94), "#171819", "condensed")
    text(image, "C-41", (0.59, 0.14, 0.62, 0.34), "#F2EFE7", "condensed_bold", rotation=90)
    text(image, "36 EXP", (0.59, 0.43, 0.62, 0.82), "#F2EFE7", "condensed_bold", rotation=90)
    finish("kodak-ektar-100", image)


def ilford_hp5():
    image = Image.new("RGBA", SIZE, "#F2F2EF")
    rect(image, (0.37, 0, 0.397, 1), "#D5D5D1")
    rect(image, (0.535, 0.15, 0.568, 0.82), "#151615")
    text(image, "ILFORD", (0.402, 0.12, 0.45, 0.88), "#111211", "condensed_bold", rotation=90)
    text(image, "HP5", (0.455, 0.12, 0.52, 0.88), "#128A45", "condensed_bold", rotation=90)
    text(image, "PLUS", (0.537, 0.19, 0.566, 0.78), "#F2F2EF", "condensed_bold", rotation=90)
    text(image, "400", (0.578, 0.12, 0.603, 0.34), "#111211", "bold", rotation=90)
    text(image, "BLACK & WHITE FILM", (0.578, 0.39, 0.603, 0.91), "#111211", "condensed", rotation=90)
    finish("ilford-hp5-400", image)


def fuji_superia():
    image = Image.new("RGBA", SIZE, "#F4F4EF")
    rect(image, (0.37, 0, 0.435, 1), "#078F45")
    rect(image, (0, 0.76, 1, 1), "#078F45")
    rect(image, (0, 0.72, 1, 0.76), "#DDEBDD")
    rect(image, (0.435, 0.76, 0.455, 1), "#A9D5B1")
    text(image, "CH 135", (0.375, 0.10, 0.43, 0.19), "#FFFFFF", "condensed_bold")
    text(image, "C-41", (0.375, 0.49, 0.43, 0.58), "#FFFFFF", "condensed_bold")
    text(image, "DX", (0.375, 0.82, 0.43, 0.91), "#FFFFFF", "bold")
    text(image, "36", (0.46, 0.10, 0.50, 0.23), "#171819", "bold")
    text(image, "SUPERIA", (0.505, 0.10, 0.64, 0.23), "#171819", "italic",
         shadow_color="#777670", shadow_opacity=.22)
    text(image, "X-TRA", (0.465, 0.27, 0.63, 0.43), "#171819", "bold_italic",
         shadow_color="#777670", shadow_opacity=.24)
    text(image, "400", (0.46, 0.45, 0.63, 0.68), "#171819", "condensed_bold",
         shadow_color="#777670", shadow_opacity=.30, shadow_offset=(15, 18), shadow_blur=11)
    text(image, "FUJICOLOR", (0.47, 0.79, 0.63, 0.87), "#FFFFFF", "bold",
         shadow_color="#075D30", shadow_opacity=.28)
    text(image, "FUJIFILM", (0.47, 0.89, 0.63, 0.97), "#FFFFFF", "bold",
         shadow_color="#075D30", shadow_opacity=.30)
    finish("fuji-superia-400", image)


def main():
    ultramax()
    gold_200()
    ektar_100()
    fuji_superia()
    ilford_hp5()


if __name__ == "__main__":
    main()
