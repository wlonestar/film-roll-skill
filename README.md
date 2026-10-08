# film-roll-skill

A standalone Pi skill for turning a user-provided film-cartridge image into an original, stylized 3D 35 mm cartridge render. The model reads the reference image and writes a small label-design JSON; the bundled Pillow/Blender scripts render that design on the existing cartridge shell.

The shell geometry is fixed. This is not photogrammetry, a general 3D reconstruction tool, or a claim of an exact or licensed product replica. By default, all generated files stay under `output/`; the skill does not modify the `film-roll` library or gallery.

## Requirements

- Pi with image input enabled for visual inspection.
- `uv` and Python 3.11.
- `bpy==5.0.1`, `Pillow==12.3.0` in the dedicated environment.
- DejaVu Sans regular/bold, DejaVu Serif italic, and DejaVu Sans bold-oblique fonts at the paths documented in `references/renderer-details.md`.

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

This directory is intentionally under `~/work`, not an automatically discovered skill directory. Add `~/work/film-roll-skill` to the `skills` array in `~/.pi/agent/settings.json`, then run `/reload`. Invoke it with `/skill:film-roll-skill` or let the description route matching image-render requests.

## Files

- `SKILL.md`: image-to-label workflow and safe output rules.
- `scripts/render_reference.py`: safe orchestration, environment selection, base-scene preparation, and collision-free output directories.
- `scripts/render-film-cartridge.py`: base, built-in variant, and custom JSON render entry point.
- `scripts/film-cartridge-variants.py`: Blender material replacement and render helpers.
- `scripts/custom_label.py`: validates and draws the non-executable label-design format.
- `references/design-format.md`: JSON format used by the skill.
- `references/renderer-details.md`: renderer setup, geometry, and built-in label notes.
- `examples/amber-400.json`: fictional sample label for tests and experimentation.
- `examples/README.md` and `examples/preset-preview.jpg`: visual index of the five built-in examples.
- `examples/kodak-gold-200.json`, `kodak-portra-400.json`, `kodak-ektar-100.json`, `fuji-superia-400.json`, and `ilford-hp5-400.json`: executable, editable examples used as the source artwork for the five library cartridges.

Run the local validation suite from this directory:

```sh
~/.cache/film-roll-skill/venv/bin/python -m unittest discover -s tests -v
```
