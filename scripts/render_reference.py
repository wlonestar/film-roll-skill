#!/usr/bin/env python3
"""Prepare an isolated output folder and render one validated reference-derived design."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

SKILL_ROOT = Path(__file__).resolve().parents[1]
RENDERER = SKILL_ROOT / "scripts" / "render-film-cartridge.py"
SCRIPTS_DIR = SKILL_ROOT / "scripts"
REQUIRED_VERSIONS = 'import bpy, PIL; assert bpy.app.version_string == "5.0.1" and PIL.__version__ == "12.3.0"'


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


def _validated_slug(python: Path, design_path: Path) -> str:
    code = (
        "import sys; from pathlib import Path; "
        "sys.path.insert(0, sys.argv[1]); "
        "from custom_label import load_design; "
        "print(load_design(Path(sys.argv[2]))['slug'])"
    )
    result = subprocess.run(
        [str(python), "-c", code, str(SCRIPTS_DIR), str(design_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise SystemExit(f"Design validation failed: {detail}")
    return result.stdout.strip().splitlines()[-1]


def _base_is_current(python: Path, cache: Path, base_dir: Path) -> bool:
    scene_file = cache / "film-cartridge.blend"
    geometry_file = base_dir / "film-cartridge.geometry.json"
    image_file = base_dir / "film-cartridge.webp"
    if not scene_file.is_file() or not geometry_file.is_file() or not image_file.is_file():
        return False
    try:
        revision = json.loads(geometry_file.read_text(encoding="utf-8")).get("modelRevision")
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(revision, str):
        return False

    code = (
        "import bpy, sys; bpy.ops.wm.open_mainfile(filepath=sys.argv[1]); "
        "print('__SCENE_REVISION__' + str(bpy.context.scene.get('modelRevision', '')))"
    )
    check = subprocess.run(
        [str(python), "-c", code, str(scene_file)], capture_output=True, text=True, check=False
    )
    actual = next((line.removeprefix("__SCENE_REVISION__")
                   for line in check.stdout.splitlines()
                   if line.startswith("__SCENE_REVISION__")), None)
    return check.returncode == 0 and actual == revision


def _prepare_base(python: Path, output_root: Path, cache_root: Path) -> tuple[Path, Path]:
    output_root.mkdir(parents=True, exist_ok=True)
    cache_root.parent.mkdir(parents=True, exist_ok=True)
    for suffix in range(1, 1000):
        base_name = "_base" if suffix == 1 else f"_base-{suffix:02d}"
        cache_name = cache_root.name if suffix == 1 else f"{cache_root.name}-{suffix:02d}"
        base_dir = output_root / base_name
        cache = cache_root.parent / cache_name
        if _base_is_current(python, cache, base_dir):
            return base_dir, cache
        if base_dir.exists() or cache.exists():
            continue

        env = os.environ.copy()
        env["FILM_RENDER_CACHE"] = str(cache)
        print(f"Preparing the base 35 mm shell in {base_dir}", flush=True)
        _run([str(python), str(RENDERER), "--output-dir", str(base_dir)], env)
        if not _base_is_current(python, cache, base_dir):
            raise SystemExit("Base render completed but its scene and geometry did not validate")
        return base_dir, cache
    raise SystemExit("Could not allocate a fresh base shell/cache directory")


def _next_output_dir(root: Path, slug: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for suffix in range(1, 1000):
        name = slug if suffix == 1 else f"{slug}-{suffix:02d}"
        candidate = root / name
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise SystemExit(f"Could not allocate a unique output directory for {slug!r}")


def _run(command: Sequence[str], env: dict[str, str]) -> None:
    result = subprocess.run(command, env=env, check=False)
    if result.returncode != 0:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--design-json", required=True, type=Path,
                        help="validated label design JSON created from the reference image")
    parser.add_argument("--output-root", type=Path,
                        help="parent directory for generated renders (default: skill output/)")
    parser.add_argument("--python", type=Path,
                        help="compatible Blender Python; can also be set with FILM_RENDER_PYTHON")
    parser.add_argument("--cache-dir", type=Path,
                        help="Blender render cache (default: FILM_RENDER_CACHE or skill cache)")
    args = parser.parse_args()

    design_path = args.design_json.expanduser().resolve()
    if not design_path.is_file():
        raise SystemExit(f"Design JSON not found: {design_path}")

    python = _candidate_python(args)
    slug = _validated_slug(python, design_path)
    output_setting = args.output_root or Path(
        os.environ.get("FILM_ROLL_OUTPUT_DIR", str(SKILL_ROOT / "output"))
    )
    output_root = output_setting.expanduser().resolve()
    cache_setting = args.cache_dir or Path(
        os.environ.get("FILM_RENDER_CACHE", str(Path.home() / ".cache/film-roll-skill/render"))
    )
    cache = cache_setting.expanduser().resolve()
    base_dir, cache = _prepare_base(python, output_root, cache)
    base_files = (base_dir / "film-cartridge.webp", base_dir / "film-cartridge.geometry.json")
    env = os.environ.copy()
    env["FILM_RENDER_CACHE"] = str(cache)

    output_dir = _next_output_dir(output_root, slug)
    for path in base_files:
        shutil.copy2(path, output_dir / path.name)
    design_copy = output_dir / f"{slug}.design.json"
    shutil.copy2(design_path, design_copy)

    print(f"Rendering design {slug!r} into {output_dir}", flush=True)
    _run([
        str(python), str(RENDERER),
        "--design-json", str(design_copy),
        "--output-dir", str(output_dir),
    ], env)

    image_path = output_dir / f"{slug}.webp"
    if not image_path.is_file() or image_path.stat().st_size == 0:
        raise SystemExit(f"Renderer did not produce an image at {image_path}")
    print(json.dumps({
        "image": str(image_path),
        "design": str(design_copy),
        "outputDirectory": str(output_dir),
        "bytes": image_path.stat().st_size,
    }, indent=2))


if __name__ == "__main__":
    main()
