#!/usr/bin/env python3
"""Prepare a blank canister and render one completed raster label texture."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Sequence

SKILL_ROOT = Path(__file__).resolve().parents[1]
RENDERER = SKILL_ROOT / "scripts" / "render-film-cartridge.py"
SCRIPTS_DIR = SKILL_ROOT / "scripts"
REQUIRED_VERSIONS = 'import bpy, PIL; assert bpy.app.version_string == "5.0.1" and PIL.__version__ == "12.3.0"'
BUILT_IN_SLUGS = {
    "light-notes", "kodak-ultramax-400", "kodak-gold-200", "kodak-ektar-100",
    "fuji-superia-400", "ilford-hp5-400", "kodak-portra-400",
}


def _renderer_model_revision() -> str:
    tree = ast.parse(RENDERER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "MODEL_REVISION"
            for target in node.targets
        ):
            revision = ast.literal_eval(node.value)
            if isinstance(revision, str):
                return revision
    raise RuntimeError("Renderer does not declare a literal MODEL_REVISION")


MODEL_REVISION = _renderer_model_revision()


def _candidate_python(args: argparse.Namespace) -> Path:
    candidates: list[Path] = []
    if args.python:
        candidates.append(args.python.expanduser())
    if os.environ.get("FILM_RENDER_PYTHON"):
        candidates.append(Path(os.environ["FILM_RENDER_PYTHON"]).expanduser())
    candidates.extend([
        Path.home() / ".cache/film-roll-skill/venv/bin/python",
        Path.home() / ".cache/film-render/venv/bin/python",
    ])

    seen: set[Path] = set()
    for candidate in candidates:
        # Preserve the venv's python symlink; resolving it bypasses venv site-packages.
        candidate = Path(os.path.abspath(candidate))
        if candidate in seen or not candidate.is_file():
            continue
        seen.add(candidate)
        check = subprocess.run(
            [str(candidate), "-c", REQUIRED_VERSIONS],
            capture_output=True,
            text=True,
            check=False,
        )
        if check.returncode == 0:
            return candidate
    raise SystemExit(
        "No compatible renderer Python found. Set FILM_RENDER_PYTHON or create the "
        "environment described in README.md (Python 3.11, bpy 5.0.1, Pillow 12.3.0)."
    )


def _validated_slug(python: Path, label_path: Path) -> str:
    code = (
        "import sys; from pathlib import Path; "
        "sys.path.insert(0, sys.argv[1]); "
        "from label_artwork import label_slug, load_label_texture; "
        "path = Path(sys.argv[2]); load_label_texture(path); print(label_slug(path))"
    )
    result = subprocess.run(
        [str(python), "-c", code, str(SCRIPTS_DIR), str(label_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"Label image validation failed: {detail}")
    return result.stdout.strip().splitlines()[-1]


def _base_is_current(python: Path, cache: Path, base_dir: Path) -> bool:
    scene_file = cache / "film-cartridge.blend"
    geometry_file = base_dir / "film-cartridge.geometry.json"
    image_file = base_dir / "film-cartridge-shell.webp"
    if not scene_file.is_file() or not geometry_file.is_file() or not image_file.is_file():
        return False
    try:
        geometry = json.loads(geometry_file.read_text(encoding="utf-8"))
        revision = geometry.get("modelRevision")
        frame = geometry["renderFrame"]
        crop = geometry["crop"]
        width, height = geometry["width"], geometry["height"]
        with image_file.open("rb") as shell_file:
            shell_bytes = os.fstat(shell_file.fileno()).st_size
            shell_digest = hashlib.file_digest(shell_file, "sha256").hexdigest()
        if (shell_bytes != geometry.get("bytes") or shell_bytes >= 250_000
                or shell_digest != geometry.get("sha256")
                or not (0 <= crop[0] < crop[2] <= frame["width"]
                        and 0 <= crop[1] < crop[3] <= frame["height"])
                or (crop[2] - crop[0], crop[3] - crop[1]) != (width, height)):
            return False
    except (OSError, UnicodeDecodeError, KeyError, IndexError, TypeError, AttributeError,
            json.JSONDecodeError):
        return False
    if revision != MODEL_REVISION:
        return False

    code = """import bpy, json, sys
from PIL import Image
bpy.ops.wm.open_mainfile(filepath=sys.argv[1])
scene = bpy.context.scene
print('__SCENE_REVISION__' + str(scene.get('modelRevision', '')))
print('__SCENE_INFO__' + json.dumps([scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage]))
with Image.open(sys.argv[2]) as image:
    print('__SHELL_INFO__' + json.dumps([image.format, image.mode, *image.size]))
"""
    check = subprocess.run(
        [str(python), "-c", code, str(scene_file), str(image_file)],
        capture_output=True, text=True, check=False
    )
    actual = next((line.removeprefix("__SCENE_REVISION__")
                   for line in check.stdout.splitlines()
                   if line.startswith("__SCENE_REVISION__")), None)
    scene_info = next((line.removeprefix("__SCENE_INFO__")
                       for line in check.stdout.splitlines()
                       if line.startswith("__SCENE_INFO__")), None)
    shell_info = next((line.removeprefix("__SHELL_INFO__")
                       for line in check.stdout.splitlines()
                       if line.startswith("__SHELL_INFO__")), None)
    try:
        actual_scene = json.loads(scene_info) if scene_info else None
        actual_shell = json.loads(shell_info) if shell_info else None
    except json.JSONDecodeError:
        actual_scene = actual_shell = None
    return (check.returncode == 0 and actual == revision
            and actual_scene == [frame["width"], frame["height"], 100]
            and actual_shell == ["WEBP", "RGBA", width, height])


def _assert_safe_write_directory(path: Path) -> None:
    path = path.resolve(strict=True)
    user_id = os.geteuid()
    current = path
    while True:
        info = current.stat()
        shared_write = info.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        trusted_sticky = bool(info.st_mode & stat.S_ISVTX) and info.st_uid in (0, user_id)
        if shared_write and not trusted_sticky:
            raise SystemExit(f"Refusing untrusted shared render directory: {current}")
        if current == path and info.st_uid not in (0, user_id):
            raise SystemExit(f"Refusing render directory not owned by root or this user: {path}")
        if current.parent == current:
            break
        current = current.parent


def _assert_private_cache_directory(path: Path) -> None:
    path = path.resolve(strict=True)
    _assert_safe_write_directory(path)
    info = path.stat()
    if info.st_uid != os.geteuid() or info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise SystemExit(f"Render cache must be private and owned by this user: {path}")


def _prepare_base(python: Path, output_root: Path, cache_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    cache_root.parent.mkdir(parents=True, exist_ok=True)
    _assert_safe_write_directory(output_root)
    _assert_safe_write_directory(cache_root.parent)
    for suffix in range(1, 1000):
        base_name = "_base" if suffix == 1 else f"_base-{suffix:02d}"
        cache_name = cache_root.name if suffix == 1 else f"{cache_root.name}-{suffix:02d}"
        base_dir = output_root / base_name
        cache = cache_root.parent / cache_name
        if cache.is_symlink() or base_dir.is_symlink():
            raise SystemExit("Refusing a symlinked base render or cache directory")
        if cache.is_dir():
            _assert_private_cache_directory(cache)
        if base_dir.is_dir():
            _assert_safe_write_directory(base_dir)
        if _base_is_current(python, cache, base_dir):
            return base_dir, cache
        try:
            base_dir.mkdir(mode=0o700)
        except FileExistsError:
            continue
        try:
            cache.mkdir(mode=0o700)
            _assert_private_cache_directory(cache)
        except FileExistsError:
            base_dir.rmdir()
            continue
        except BaseException:
            base_dir.rmdir()
            if cache.is_dir() and not cache.is_symlink():
                shutil.rmtree(cache, ignore_errors=True)
            raise

        env = os.environ.copy()
        env["FILM_RENDER_CACHE"] = str(cache)
        print(f"Preparing the base 35 mm shell in {base_dir}", flush=True)
        try:
            _run([str(python), str(RENDERER), "--output-dir", str(base_dir)], env)
            if not _base_is_current(python, cache, base_dir):
                raise SystemExit("Base render completed but its scene and geometry did not validate")
        except BaseException:
            shutil.rmtree(base_dir, ignore_errors=True)
            shutil.rmtree(cache, ignore_errors=True)
            raise
        return base_dir, cache
    raise SystemExit("Could not allocate a fresh base shell/cache directory")


def _next_output_dir(root: Path, slug: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    _assert_safe_write_directory(root)
    for suffix in range(1, 1000):
        name = slug if suffix == 1 else f"{slug}-{suffix:02d}"
        candidate = root / name
        try:
            candidate.mkdir(mode=0o700)
            return candidate
        except FileExistsError:
            continue
    raise SystemExit(f"Could not allocate a unique output directory for {slug!r}")


def _run(command: Sequence[str], env: dict[str, str]) -> None:
    result = subprocess.run(command, env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def _remove_partial_output(output_dir: Path, slug: str) -> None:
    generated = (
        "film-cartridge-shell.webp",
        "film-cartridge.geometry.json",
        f"{slug}.png",
        f"{slug}.webp",
    )
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        directory_fd = os.open(output_dir, flags)
    except OSError:
        return
    try:
        opened = os.fstat(directory_fd)
        try:
            current = os.stat(output_dir, follow_symlinks=False)
        except OSError:
            return
        if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (opened.st_dev, opened.st_ino):
            return
        for name in generated:
            try:
                os.unlink(name, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
            except OSError:
                pass
        try:
            current = os.stat(output_dir, follow_symlinks=False)
            if (current.st_dev, current.st_ino) == (opened.st_dev, opened.st_ino):
                os.rmdir(output_dir)
        except OSError:
            pass
    finally:
        os.close(directory_fd)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label-image", required=True, type=Path,
                        help="completed 2:1 raster artwork for the canister label")
    parser.add_argument("--output-root", type=Path,
                        help="parent directory for generated renders (default: skill output/)")
    parser.add_argument("--python", type=Path,
                        help="compatible Blender Python; can also be set with FILM_RENDER_PYTHON")
    parser.add_argument("--cache-dir", type=Path,
                        help="Blender render cache (default: FILM_RENDER_CACHE or skill cache)")
    args = parser.parse_args()

    label_path = args.label_image.expanduser().resolve()
    if not label_path.is_file():
        raise SystemExit(f"Label image not found: {label_path}")

    python = _candidate_python(args)
    slug = _validated_slug(python, label_path)
    if slug in BUILT_IN_SLUGS:
        slug = f"custom-{slug}"
    output_setting = args.output_root or Path(
        os.environ.get("FILM_ROLL_OUTPUT_DIR", str(SKILL_ROOT / "output"))
    )
    output_root = output_setting.expanduser().resolve()
    cache_setting = args.cache_dir or Path(
        os.environ.get("FILM_RENDER_CACHE", str(Path.home() / ".cache/film-roll-skill/render"))
    )
    cache = cache_setting.expanduser().resolve()
    base_dir, cache = _prepare_base(python, output_root, cache)
    base_files = (base_dir / "film-cartridge-shell.webp", base_dir / "film-cartridge.geometry.json")
    env = os.environ.copy()
    env["FILM_RENDER_CACHE"] = str(cache)

    output_dir = _next_output_dir(output_root, slug)
    try:
        for path in base_files:
            shutil.copy2(path, output_dir / path.name)
        artwork_copy = output_dir / f"{slug}.png"
        normalize = (
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); "
            "from label_artwork import load_label_texture; "
            "load_label_texture(Path(sys.argv[2])).save(Path(sys.argv[3]), format='PNG')"
        )
        normalized = subprocess.run(
            [str(python), "-c", normalize, str(SCRIPTS_DIR), str(label_path), str(artwork_copy)],
            capture_output=True,
            text=True,
            check=False,
        )
        if normalized.returncode != 0:
            detail = normalized.stderr.strip() or normalized.stdout.strip()
            raise SystemExit(f"Could not normalize label image: {detail}")

        print(f"Rendering artwork {slug!r} into {output_dir}", flush=True)
        _run([
            str(python), str(RENDERER),
            "--label-image", str(artwork_copy),
            "--output-dir", str(output_dir),
        ], env)

        image_path = output_dir / f"{slug}.webp"
        if not image_path.is_file() or image_path.stat().st_size == 0:
            raise SystemExit(f"Renderer did not produce an image at {image_path}")
        print(json.dumps({
            "image": str(image_path),
            "artwork": str(artwork_copy),
            "outputDirectory": str(output_dir),
            "bytes": image_path.stat().st_size,
        }, indent=2))
    except BaseException:
        _remove_partial_output(output_dir, slug)
        raise


if __name__ == "__main__":
    main()
