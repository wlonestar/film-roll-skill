# Film cartridge renderer

`render-film-cartridge.py` builds an unbranded, neutral-stock 35 mm canister with hollow spindle, rolled end caps, and a flush side seam. It has no projecting film leader or tab. The skill prepares an independent full-wrap raster label, which Blender applies to the reusable shell and renders as a transparent WebP. Paper stock gets fine grain and uneven satin roughness; the shell gets molded-plastic microtexture and directional softbox lighting to reproduce the real-photo highlights and soft shadows rather than a uniformly lit, perfectly smooth mockup. The source product photo is visual guidance, not pasted onto the output. No model, image, or runtime renderer is downloaded or added to the website.

## Reproduce (development only)

```sh
mkdir -p ~/.cache/film-roll-skill/tmp
uv venv --python 3.11 ~/.cache/film-roll-skill/venv
TMPDIR=$HOME/.cache/film-roll-skill/tmp uv pip install --python ~/.cache/film-roll-skill/venv/bin/python bpy==5.0.1 pillow==12.3.0
```

The previous compatible environment at `~/.cache/film-render/venv` can be reused if it contains the pinned versions; the scripts prefer the new skill-specific environment when both are available. The render cache defaults to `~/.cache/film-roll-skill/render`; set `FILM_RENDER_CACHE` to move intermediate files. Render processes serialize through a private per-user lock, and marked, owned cache/output staging directories are pruned after 24 hours. For path safety, the selected write directory must be owned by this user or root; any shared writable ancestor must also be root- or user-owned and sticky. Nothing uploads the reference image.

## Blank shell and custom artwork

```sh
~/.cache/film-roll-skill/venv/bin/python scripts/render-film-cartridge.py --output-dir output/_base
python3 scripts/render_reference.py --label-image output/.artwork-inbox/my-film.png
```

The first command creates an unbranded blank shell and matching geometry metadata. The wrapper accepts any valid 2:1 raster label image, normalizes it to 4096 × 2048 without stretching, and allocates a fresh output directory. It returns a transparent `<slug>.webp`, a normalized copy of the artwork, and shared geometry metadata. There is no element JSON or preset layout schema.

For direct rendering, the blank shell and geometry metadata must be inside the output directory. Build the shell first, then copy those two files into a fresh output directory:

```sh
mkdir -p output/my-film
cp output/_base/film-cartridge-shell.webp output/_base/film-cartridge.geometry.json output/my-film/
~/.cache/film-roll-skill/venv/bin/python scripts/render-film-cartridge.py \
  --label-image output/my-film.png \
  --output-dir output/my-film
```

## Built-in appearances

```sh
~/.cache/film-roll-skill/venv/bin/python scripts/render-film-cartridge.py --output-dir output/_base
~/.cache/film-roll-skill/venv/bin/python scripts/render-film-cartridge.py --variant all --output-dir output/_base
```

The five refreshed references are Kodak UltraMax 400, Kodak Gold 200, Kodak Ektar 100, Fujicolor Superia X-TRA 400, and Ilford HP5 Plus 400. Light Notes is a separate fictional example; Kodak Portra 400 remains renderable for compatibility but is not part of the refreshed five. Each appearance is a standalone texture in `examples/artwork/`. `--variant all` writes a complete catalog; a single-variant run catalogs only that newly rendered variant so same-sized outputs from older revisions cannot be mistaken for current renders.

Outputs:
- `film-cartridge-shell.webp`: unbranded blank canister shell.
- `film-cartridge.geometry.json`: shell and live-strip alignment metadata.
- `light-notes.webp`, the five refreshed branded appearances, and `kodak-portra-400.webp`.
- `catalog.json`: variant IDs, names, dimensions, byte sizes, and geometry reference.

With the pinned environment, output WebPs are currently 686 × 1365 RGBA and below 150,000 bytes. `--variant all` writes a five-reference contact sheet to `/tmp/film-cartridges-contact-<uid>.jpg`; single-variant renders leave it unchanged.

## Shared geometry

Every variant shares the same Blender scene, 900 × 1500 render frame, crop `(107, 74, 793, 1439)` (right/bottom exclusive), and alpha coverage. The current shell/material revision is `true-shell-v15`; a revision mismatch stops rendering so stale geometry or lighting cannot be mixed with a new scene. The 3D shell is 23.5 mm diameter × 42 mm body height, with a 48.2 mm overall height. It has no side-projecting piece. The JSON geometry records crop, slit, body/cap centers, and physical dimensions; its `bytes` and `sha256` fields bind the metadata to the blank shell. Variant generation stages assets before publication; a render failure before publication leaves existing preset files and the catalog untouched. If a process is interrupted during the final per-file publish, rerun `--variant all` to complete the set.

For a live-strip height `h` in CSS pixels:

```js
const spriteHeight = h / (geometry.slit.bottomY - geometry.slit.topY);
const spriteWidth = spriteHeight * geometry.width / geometry.height;
const top = filmCenterY - spriteHeight * geometry.slit.centerY;
const left = filmRightX - spriteWidth * geometry.slit.centerX;
```

Preserve aspect ratio. The live strip meets the flush side opening; nothing is modeled or rendered outside the canister silhouette.
