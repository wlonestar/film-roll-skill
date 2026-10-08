# film-roll-skill

A standalone Pi skill for turning a user-provided film-cartridge image into an individually composed, transparent WebP 3D render. Pillow and Blender apply full-wrap raster artwork to a reusable blank 35 mm shell with no side-projecting film piece.

The shell geometry is fixed. This is not photogrammetry, a general 3D reconstruction tool, or a claim of an exact or licensed product replica. New user renders stay under `output/`; successful renders are retained in separate directories, so archive or remove old output folders manually. Marked temporary staging directories are pruned after 24 hours on the next run. A forced kill during initial base setup can leave incomplete `_base[-NN]` and matching cache directories; remove those pairs manually after confirming no renderer is active. The skill updates the `film-roll` library only when explicitly requested.

## Requirements

- Pi with image input enabled for visual inspection.
- `uv` and Python 3.11.
- `bpy==5.0.1`, `Pillow==12.3.0` in the dedicated environment.

The previous renderer environment at `~/.cache/film-render/venv` can be reused if it contains the exact versions above. Otherwise, one-time setup for this skill, after reviewing the command:

```sh
mkdir -p ~/.cache/film-roll-skill/tmp
uv venv --python 3.11 ~/.cache/film-roll-skill/venv
TMPDIR=$HOME/.cache/film-roll-skill/tmp uv pip install \
  --python ~/.cache/film-roll-skill/venv/bin/python \
  bpy==5.0.1 pillow==12.3.0
```

The scripts use a separate cache under `~/.cache/film-roll-skill`. They do not upload the reference image or add dependencies to the website/library.

## Use in Pi

This directory is not automatically discovered as a skill. Add its absolute path to the `skills` array in `~/.pi/agent/settings.json`, then run `/reload`. For this checkout the path is `~/work/film-roll-dir/film-roll-skill`; use the actual checkout path elsewhere. Invoke it with `/skill:film-roll-skill` or let the description route matching image-render requests.

## Files

- `SKILL.md`: image-to-label workflow and safe output rules.
- `scripts/render_reference.py`: safe orchestration, environment selection, base-scene preparation, and collision-free output directories.
- `scripts/render-film-cartridge.py`: blank-shell, built-in variant, and custom raster render entry point.
- `scripts/film-cartridge-variants.py`: validates, applies, and renders full-wrap artwork textures.
- `scripts/label_artwork.py`: image loading and projection-size checks, with no drawing-command schema.
- `scripts/build_reference_artwork.py`: individual Pillow compositions for the five checked-in reference textures.
- `references/artwork-textures.md`: raster dimensions, projection seam, and input constraints.
- `references/renderer-details.md`: renderer setup, geometry, and built-in label notes.
- `examples/README.md` and `examples/preset-preview.jpg`: visual index of the five refreshed references.
- `examples/artwork/*.png`: complete independent wrap textures for the refreshed five references, Light Notes, and the Portra compatibility appearance.

Run the local validation suite from this directory:

```sh
RENDER_PYTHON="${FILM_RENDER_PYTHON:-$HOME/.cache/film-roll-skill/venv/bin/python}"
if [ ! -x "$RENDER_PYTHON" ]; then RENDER_PYTHON="$HOME/.cache/film-render/venv/bin/python"; fi
"$RENDER_PYTHON" -m unittest discover -s tests -v
```
