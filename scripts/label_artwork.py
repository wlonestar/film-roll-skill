#!/usr/bin/env python3
"""Load an unconstrained, precomposed wrap texture for the 35 mm shell."""

from __future__ import annotations

import os
import re
import stat
import tempfile
import warnings
from pathlib import Path

from PIL import Image

TEXTURE_SIZE = (4096, 2048)
MAX_INPUT_PIXELS = 16_777_216
MAX_INPUT_BYTES = 32 * 1024 * 1024
SUPPORTED_FORMATS = {"PNG", "JPEG", "WEBP"}
SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def label_slug(path: Path) -> str:
    slug = path.stem
    if len(slug) > 64 or not SLUG_RE.fullmatch(slug):
        raise ValueError("label image filename must use lowercase letters, digits, and single hyphens")
    return slug


def _assert_safe_write_directory(path: Path) -> None:
    path = Path(path).resolve(strict=True)
    user_id = os.geteuid()
    current = path
    while True:
        info = current.stat()
        shared_write = info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        trusted_sticky = bool(info.st_mode & stat.S_ISVTX) and info.st_uid in (0, user_id)
        if shared_write and not trusted_sticky:
            raise PermissionError(f"refusing to write through an untrusted shared directory: {current}")
        if current == path and info.st_uid not in (0, user_id):
            raise PermissionError(f"refusing to write into a directory not owned by root or this user: {path}")
        if current.parent == current:
            break
        current = current.parent


def _assert_private_cache_directory(path: Path) -> None:
    path = Path(path).resolve(strict=True)
    _assert_safe_write_directory(path)
    info = path.stat()
    if info.st_uid != os.geteuid() or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise PermissionError(f"render cache must be private and owned by this user: {path}")


def save_webp_with_limit(image: Image.Image, path: Path, qualities: tuple[int, ...], byte_limit: int) -> int:
    """Atomically save a WebP without following a pre-existing target symlink."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _assert_safe_write_directory(path.parent)
    with tempfile.TemporaryDirectory(prefix=f".{path.name}.", dir=path.parent) as temporary_dir:
        temporary = Path(temporary_dir) / "render.webp"
        for quality in qualities:
            image.save(temporary, quality=quality, method=6, exact=True)
            if temporary.stat().st_size < byte_limit:
                break
        size = temporary.stat().st_size
        if size >= byte_limit:
            raise RuntimeError(f"{path} exceeds the {byte_limit}-byte asset budget")
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
        return size


def write_text_atomic(path: Path, value: str, encoding: str = "utf-8") -> None:
    """Atomically replace a text file without following a target symlink."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _assert_safe_write_directory(path.parent)
    with tempfile.TemporaryDirectory(prefix=f".{path.name}.", dir=path.parent) as temporary_dir:
        temporary = Path(temporary_dir) / "contents.tmp"
        temporary.write_text(value, encoding=encoding)
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)


def load_label_texture(path: Path) -> Image.Image:
    """Load a completed label image without imposing a drawing-command schema."""
    path = Path(path)
    label_slug(path)
    try:
        with path.open("rb") as image_file:
            if os.fstat(image_file.fileno()).st_size > MAX_INPUT_BYTES:
                raise ValueError("label image must be no larger than 32 MiB")
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(image_file) as source:
                    if source.format not in SUPPORTED_FORMATS:
                        raise ValueError("label image must be PNG, JPEG, or WebP")
                    width, height = source.size
                    if width < 512 or height < 256:
                        raise ValueError("label image must be at least 512 × 256 pixels")
                    if width * height > MAX_INPUT_PIXELS:
                        raise ValueError("label image must contain no more than 16 megapixels")
                    if width != height * 2:
                        raise ValueError("label image must be exactly 2:1; it will not be stretched")
                    source.load()
                    image = source.convert("RGBA")
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as error:
        raise ValueError("label image exceeds the safe pixel limit") from error
    except ValueError:
        raise
    except Exception as error:
        raise ValueError(f"could not decode label image at {path}: {error}") from error

    background = Image.new("RGBA", image.size, "#F4F1E8")
    image = Image.alpha_composite(background, image).convert("RGB")
    if image.size != TEXTURE_SIZE:
        image = image.resize(TEXTURE_SIZE, Image.Resampling.LANCZOS)
    return image
