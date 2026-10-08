# Film cartridge renderer

`render-film-cartridge.py` generates original label artwork with Pillow, maps it continuously onto a cylindrical mesh, and raytraces the product in Blender Cycles. No downloaded model, Kodak artwork, SVG, CSS cylinder, or runtime renderer is used. The spindle has a modeled hollow interior; caps have rolled profile geometry. The left light trap contains felt but no film strip.

This standalone skill renders into its own `output/` directory by default. Set `FILM_ROLL_OUTPUT_DIR` or pass `--output-dir` to select another location. The skill does not update or publish the `film-roll` package; copy an asset into that library only when explicitly requested.

## Reproduce (development only)

```sh
mkdir -p ~/.cache/film-roll-skill/tmp
uv venv --python 3.11 ~/.cache/film-roll-skill/venv
TMPDIR=$HOME/.cache/film-roll-skill/tmp uv pip install --python ~/.cache/film-roll-skill/venv/bin/python bpy==5.0.1 pillow==12.3.0
~/.cache/film-roll-skill/venv/bin/python scripts/render-film-cartridge.py --output-dir output/_base
```

Requires system fonts `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`, `DejaVuSans-Bold.ttf`, `DejaVuSerif-Italic.ttf`, and `DejaVuSans-BoldOblique.ttf`. The cache defaults to `~/.cache/film-roll-skill/render`; set `FILM_RENDER_CACHE` to move working files. Intermediate label, full-resolution transparent PNG, cropped PNG, and inspectable `.blend` scene remain in that external cache. No dependencies are added to the website.

Outputs:
- `output/film-cartridge.webp`: 700 × 1365, RGBA with the pinned environment.
- `output/film-cartridge.geometry.json`: `modelRevision`, the 900 × 1500 render frame, the
  final crop, the cropped width/height, and normalized geometry for that crop (origin
  top-left). Content bounds are alpha bounds, with right/bottom exclusive. Cap positions
  are projected geometric centers, not the front edges of the ellipses.

The supplied product photo reads slightly slimmer than the previous render, so this
revision trims the shell's radial silhouette by 6% while preserving its 42 mm body height,
7.2 mm hollow winding spindle, and 2.0 mm rolled rim. The render's resulting width/height
ratio and measured slit coordinates are recorded in the shared geometry file. The sealed
top cap now has a dark recessed well around the raised spool hub, rather than one broad
flat face. The surface finish is less metallic and more satin, giving the black shell
broader, softer highlights.

## Custom reference-derived labels

The skill translates the user's visual reference into a validated drawing JSON; the renderer does not consume or copy the source photo. See `design-format.md` for the format. For normal use, prefer `python3 scripts/render_reference.py --design-json <design.json>`; it prepares a revision-matched base and allocates a fresh output directory. For direct renderer use, keep the base `film-cartridge.webp` and `film-cartridge.geometry.json` beside the design JSON in the selected output directory, then run:

```sh
~/.cache/film-roll-skill/venv/bin/python scripts/render-film-cartridge.py \
  --design-json output/my-design/my-design.design.json \
  --output-dir output/my-design
```

The output is `output/my-design/<slug>.webp`, using the shared shell alpha and geometry. The renderer refuses to overwrite an existing file with the same slug.

## Spare branded exteriors

```sh
# Reuse ~/.cache/film-roll-skill/render/film-cartridge.blend.
~/.cache/film-roll-skill/venv/bin/python scripts/render-film-cartridge.py --variant all --output-dir output/_base
~/.cache/film-roll-skill/venv/bin/python scripts/render-film-cartridge.py --variant fuji-superia-400 --output-dir output/_base
```

The default (or `--variant light-notes`) retains the original generator above. The five branded layouts live as editable JSON in `examples/`; `scripts/film-cartridge-variants.py` reads those files directly, so example designs and library source artwork cannot drift apart. The cached original scene is required; on a fresh machine generate it with the default command first.

Outputs in `output/` (or the directory supplied with `--output-dir`):
- `kodak-gold-200.webp`
- `kodak-portra-400.webp`
- `kodak-ektar-100.webp`
- `fuji-superia-400.webp`
- `ilford-hp5-400.webp`
- `catalog.json`: IDs, display names, filenames, dimensions, actual byte counts, and
  the common `./film-cartridge.geometry.json` reference. Individual runs inventory
  whichever variants already exist; `all` produces the complete five-entry catalog.

Each is transparent RGBA WebP, 700 × 1365 and below 150,000 bytes. A neutral-background
contact sheet is written to `/tmp/film-cartridges-contact.jpg`. Label textures and
full-frame renders stay in the external cache, not the website. No UI, selector,
film effects, runtime renderer, or runtime dependencies are added.

### Shared geometry and framing

Variants load the original Blender scene without rebuilding or transforming any
mesh, camera, UVs, lights, or material shading. Only the cylindrical label material's
image texture changes. Cycles uses the original 96 samples and AgX transform.
All use the **same** render frame and crop recorded in
`output/film-cartridge.geometry.json` (currently `(93, 74, 793, 1439)`, right/bottom
exclusive, the original alpha bounds `(101, 82, 785, 1431)` plus eight pixels). Nothing
about the framing is duplicated as a constant in the variant script: frame, crop, size,
and alpha are read from the geometry, and a `modelRevision` mismatch stops the run so a
stale cache can never mix shell generations. There is no per-variant crop or resizing.
The original WebP's alpha plane is reused after rendering: contrast-dependent
adaptive sampling otherwise changes a few fractional edge pixels. Thus every
variant has pixel-identical coverage to the original, not just equal bounds.
The hollow spindle, black end caps, silhouette and LEFT felt opening retain the
original projection. Existing geometry metadata remains valid for every variant;
its `bytes` field describes only the original asset, not the spares.

### Reference inspection and scope

These are **unofficial representative reconstructions**, not exact packaging/year
replicas or claims of brand affiliation. Each label was laid out independently from
its own physical-cartridge reference; there is no shared text grid or mandatory side
panel. All shipped pixels are our own Blender renders and Pillow artwork; reference
photographs are not distributed. Typeface substitutions use the system DejaVu fonts.
The examples preserve the individual label's visible palette, text direction, and
hierarchy while omitting unreadable or uncertain microprint.

The prior local cache mixed product-box and marketing photos with cartridge photos; those non-cartridge images are not valid label references. Each source below was re-opened and checked to show the actual 135 canister. If a page also shows a box, only the visible canister informed the reconstruction:

- Kodak Gold 200, 135: <https://commons.wikimedia.org/wiki/File:Kodak-gold-200.jpg> shows the actual yellow-labeled cartridge. The edition pictured has black KODAK/200 printing; the rendered label follows that canister rather than the retail box.
- Kodak Portra 400, 135-36: <https://fotok.es/carretes-paso-universal-35mm/kodak-portra-400-36exp-135-1-unidad> shows the actual dark cartridge with a narrow yellow edge, white PORTRA 400 lettering, and smaller Kodak Professional/36 EXP print. Its first two gallery images are canisters; the later image is the box and is not used as reference.
- Kodak Ektar 100, 135: <https://commons.wikimedia.org/wiki/File:Kodak_Ektar_100_135_film_cartridge_(01).jpg> is a photograph of the actual black-and-yellow cartridge.
- Fujicolor Superia X-TRA 400, 135-36: <https://www.adorama.com/images/Large/fjchsp36.jpg> shows the actual white canister, green side/process strip, large black X-TRA/400 lettering, and green Fujicolor/Fujifilm base. Technical naming reference: <https://asset.fujifilm.com/master/emea/files/2020-10/9a958fdcc6bd1442a06f71e134b811f6/films_superia-xtra400_datasheet_01.pdf>.
- Ilford HP5 Plus, 135-36: <https://ilford.co.jp/photo/product/hp5-plus/> and its image <https://ilford.co.jp/photo/wp-content/uploads/2023/02/hp5_135_36_c_b_1-1200x1200.jpg> show the actual white canister with black/green ILFORD/HP5/PLUS layout; the adjacent box is excluded as a reference.

The source photographs remain external references; no source pixels are used in the
renders. Tiny or hidden text is omitted rather than guessed.

## Film attachment

The felt opening represents 35 mm vertically; the rendered body is 23.5 mm diameter × 42 mm high, a 6% radial trim from the nominal 25 mm diameter to match the supplied photo. Camera elevation is 10°, orthographic, with a straight vertical body axis. The slit endpoints are projected from the actual felt geometry, not inferred from the image silhouette. The lower rolled rim reverses its face winding when mirrored, so its normals and reflections match the upper rim.

For a live strip height `h` in CSS pixels:

```js
const spriteHeight = h / (geometry.slit.bottomY - geometry.slit.topY);
const spriteWidth = spriteHeight * geometry.width / geometry.height;
const top = filmCenterY - spriteHeight * geometry.slit.centerY;
const left = filmRightX - spriteWidth * geometry.slit.centerX;
```

Preserve aspect ratio. Place the sprite above the live strip and let the strip terminate within the felt opening (`leftX`–`rightX`), hiding the seam. Slit coordinates refer to the exposed 35 mm opening; the surrounding black metal housing continues above and below it. No app or component files are modified by this generator.
