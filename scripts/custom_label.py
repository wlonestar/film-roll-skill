#!/usr/bin/env python3
"""Validate and draw a model-authored film label design without importing Blender."""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

CANVAS_SIZE = (4096, 2048)
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
COLOR_RE = re.compile(r"#[0-9a-fA-F]{6}\Z")
FONT_PATHS = {
    "regular": os.environ.get(
        "FILM_RENDER_FONT_REGULAR", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    ),
    "bold": os.environ.get(
        "FILM_RENDER_FONT_BOLD", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ),
    "italic": os.environ.get(
        "FILM_RENDER_FONT_ITALIC", "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Italic.ttf"
    ),
    "bold_italic": os.environ.get(
        "FILM_RENDER_FONT_BOLD_ITALIC", "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"
    ),
}
MAX_ELEMENTS = 100


def _require_keys(value: dict[str, Any], required: set[str], optional: set[str], where: str) -> None:
    missing = required - value.keys()
    unknown = value.keys() - required - optional
    if missing:
        raise ValueError(f"{where} missing keys: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"{where} has unsupported keys: {', '.join(sorted(unknown))}")


def _number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{where} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{where} must be finite")
    return number


def _color(value: Any, where: str) -> str:
    if not isinstance(value, str) or not COLOR_RE.fullmatch(value):
        raise ValueError(f"{where} must be a #RRGGBB color")
    return value.upper()


def _point(value: Any, where: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{where} must be [x, y]")
    x, y = (_number(value[index], f"{where}[{index}]") for index in range(2))
    if not (0 <= x <= 1 and 0 <= y <= 1):
        raise ValueError(f"{where} coordinates must be normalized to 0..1")
    return x, y


def _box(value: Any, where: str) -> tuple[float, float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"{where} must be [left, top, right, bottom]")
    left, top, right, bottom = (
        _number(value[index], f"{where}[{index}]") for index in range(4)
    )
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError(f"{where} must be an increasing normalized box within 0..1")
    return left, top, right, bottom


def validate_design(design: Any) -> dict[str, Any]:
    """Validate and normalize the small, non-executable label-design format."""
    if not isinstance(design, dict):
        raise ValueError("design must be a JSON object")
    _require_keys(design, {"slug", "background", "elements"}, set(), "design")

    slug = design["slug"]
    if not isinstance(slug, str) or len(slug) > 64 or not SLUG_RE.fullmatch(slug):
        raise ValueError("slug must contain lowercase letters, digits, and single hyphens only")
    background = _color(design["background"], "background")
    elements = design["elements"]
    if not isinstance(elements, list) or len(elements) > MAX_ELEMENTS:
        raise ValueError(f"elements must be a list with at most {MAX_ELEMENTS} items")

    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(elements):
        where = f"elements[{index}]"
        if not isinstance(raw, dict) or not isinstance(raw.get("type"), str):
            raise ValueError(f"{where} must be an object with a type")
        kind = raw["type"]

        if kind == "rect":
            _require_keys(raw, {"type", "box", "fill"}, {"outline", "width"}, where)
            item = {
                "type": kind,
                "box": _box(raw["box"], f"{where}.box"),
                "fill": _color(raw["fill"], f"{where}.fill"),
            }
            if "outline" in raw:
                item["outline"] = _color(raw["outline"], f"{where}.outline")
            if "width" in raw:
                width = _number(raw["width"], f"{where}.width")
                if not 0 < width <= 0.05:
                    raise ValueError(f"{where}.width must be greater than 0 and at most 0.05")
                item["width"] = width
            normalized.append(item)
            continue

        if kind == "line":
            _require_keys(raw, {"type", "points", "color"}, {"width"}, where)
            points = raw["points"]
            if not isinstance(points, list) or not 2 <= len(points) <= 100:
                raise ValueError(f"{where}.points must contain 2..100 points")
            width = _number(raw.get("width", 0.004), f"{where}.width")
            if not 0 < width <= 0.05:
                raise ValueError(f"{where}.width must be greater than 0 and at most 0.05")
            normalized.append({
                "type": kind,
                "points": [_point(point, f"{where}.points[{point_index}]")
                           for point_index, point in enumerate(points)],
                "color": _color(raw["color"], f"{where}.color"),
                "width": width,
            })
            continue

        if kind == "text":
            _require_keys(raw, {"type", "text", "box", "color"}, {"font", "rotation"}, where)
            value = raw["text"]
            if not isinstance(value, str) or not value.strip() or len(value) > 120:
                raise ValueError(f"{where}.text must be a non-empty string of at most 120 characters")
            if any(ord(char) < 32 and char not in "\n\t" for char in value):
                raise ValueError(f"{where}.text contains unsupported control characters")
            font = raw.get("font", "bold")
            if not isinstance(font, str) or font not in FONT_PATHS:
                raise ValueError(f"{where}.font must be one of: {', '.join(FONT_PATHS)}")
            rotation = raw.get("rotation", 0)
            if isinstance(rotation, bool) or rotation not in (0, 90, 180, 270):
                raise ValueError(f"{where}.rotation must be 0, 90, 180, or 270")
            normalized.append({
                "type": kind,
                "text": value,
                "box": _box(raw["box"], f"{where}.box"),
                "color": _color(raw["color"], f"{where}.color"),
                "font": font,
                "rotation": rotation,
            })
            continue

        raise ValueError(f"{where}.type must be 'rect', 'line', or 'text'")

    return {"slug": slug, "background": background, "elements": normalized}


def load_design(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid design JSON at {path}: {error}") from error
    return validate_design(raw)


def _pixel_box(box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    width, height = CANVAS_SIZE
    return (
        round(box[0] * width),
        round(box[1] * height),
        round(box[2] * width),
        round(box[3] * height),
    )


def _draw_text(image: Image.Image, item: dict[str, Any]) -> None:
    left, top, right, bottom = _pixel_box(item["box"])
    target_width, target_height = right - left, bottom - top
    width, height = CANVAS_SIZE
    font_path = FONT_PATHS[item["font"]]
    if not Path(font_path).is_file():
        raise FileNotFoundError(f"font not found: {font_path}")

    measure = ImageDraw.Draw(Image.new("L", (1, 1)))

    def metrics(size: int) -> tuple[ImageFont.FreeTypeFont, tuple[int, int, int, int], int, int]:
        font = ImageFont.truetype(font_path, size)
        if "\n" in item["text"]:
            bbox = measure.multiline_textbbox((0, 0), item["text"], font=font,
                                              spacing=max(1, size // 8), align="center")
        else:
            bbox = measure.textbbox((0, 0), item["text"], font=font)
        glyph_width = max(1, bbox[2] - bbox[0])
        glyph_height = max(1, bbox[3] - bbox[1])
        if item["rotation"] in (90, 270):
            glyph_width, glyph_height = glyph_height, glyph_width
        return font, bbox, glyph_width, glyph_height

    low, high, best = 1, max(width, height), 1
    while low <= high:
        candidate = (low + high) // 2
        _, _, glyph_width, glyph_height = metrics(candidate)
        if glyph_width <= target_width and glyph_height <= target_height:
            best = candidate
            low = candidate + 1
        else:
            high = candidate - 1

    font, bbox, _, _ = metrics(best)
    tile_width = max(1, bbox[2] - bbox[0])
    tile_height = max(1, bbox[3] - bbox[1])
    tile = Image.new("RGBA", (tile_width + 2, tile_height + 2), (0, 0, 0, 0))
    tile_draw = ImageDraw.Draw(tile)
    origin = (1 - bbox[0], 1 - bbox[1])
    if "\n" in item["text"]:
        tile_draw.multiline_text(origin, item["text"], font=font, fill=item["color"],
                                 spacing=max(1, best // 8), align="center")
    else:
        tile_draw.text(origin, item["text"], font=font, fill=item["color"])
    if item["rotation"]:
        tile = tile.rotate(-item["rotation"], expand=True, resample=Image.Resampling.BICUBIC)

    scale = min(target_width / tile.width, target_height / tile.height, 1.0)
    if scale < 1:
        tile = tile.resize((max(1, round(tile.width * scale)), max(1, round(tile.height * scale))),
                           Image.Resampling.LANCZOS)
    x = left + (target_width - tile.width) // 2
    y = top + (target_height - tile.height) // 2
    image.paste(tile, (x, y), tile)


def render_label(raw_design: Any) -> Image.Image:
    design = validate_design(raw_design)
    image = Image.new("RGB", CANVAS_SIZE, design["background"])
    draw = ImageDraw.Draw(image)
    width, height = CANVAS_SIZE

    for item in design["elements"]:
        if item["type"] == "rect":
            box = _pixel_box(item["box"])
            outline = item.get("outline")
            stroke_width = max(1, round(item.get("width", 0.002) * height))
            draw.rectangle(box, fill=item["fill"], outline=outline,
                           width=stroke_width if outline else 1)
        elif item["type"] == "line":
            points = [(round(x * width), round(y * height)) for x, y in item["points"]]
            draw.line(points, fill=item["color"], width=max(1, round(item["width"] * height)),
                      joint="curve")
        else:
            _draw_text(image, item)

    return image
