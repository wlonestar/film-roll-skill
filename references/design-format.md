# Reference-derived label design format

The skill inspects the user's image and writes a small JSON description. The Python renderer turns that description into a 4096 × 2048 wraparound label texture, then the Blender scene renders the existing 35 mm cartridge shell. It does not paste the source photograph onto the shell or infer new 3D geometry.

Read `examples/amber-400.json` for a minimal example, or the five `examples/<preset>.json` files for label layouts reconstructed independently from product photographs. The JSON root has exactly these fields:

```json
{
  "slug": "amber-400",
  "background": "#F0B51B",
  "elements": []
}
```

- `slug`: 1–64 lowercase ASCII letters/digits separated by single hyphens. It becomes the output filename `<slug>.webp`; never put paths here.
- `background`: `#RRGGBB` label-stock color.
- `elements`: up to 100 drawing commands, rendered in array order.

All positions are normalized from 0 to 1. A box is `[left, top, right, bottom]`; a point is `[x, y]`. Coordinates must stay inside the canvas and boxes must have positive width and height. The texture wraps around the canister: `x=0` and `x=1` meet at the rear seam, while the visible front is centered near `x=0.5`. `y=0` is the top edge of the label. Choose the layout and orientation from the supplied photograph; there is no required side-panel position or shared preset grid. Avoid overlapping text boxes; texture-space overlap remains overlap on the rendered label.

Supported commands:

```json
{"type":"rect", "box":[0.25,0,0.42,1], "fill":"#171817"}
{"type":"rect", "box":[0.1,0.1,0.9,0.9], "fill":"#FFFFFF", "outline":"#111111", "width":0.004}
{"type":"line", "points":[[0.1,0.2],[0.9,0.2]], "color":"#171817", "width":0.006}
{"type":"text", "text":"400", "box":[0.43,0.3,0.72,0.8], "color":"#171817", "font":"bold", "rotation":90}
```

- `rect`: `fill` is required; `outline` and `width` are optional. Width is a fraction of canvas height and only affects an outline.
- `line`: requires 2–100 points and a color. Width is a fraction of canvas height, default `0.004`.
- `text`: requires text, box, and color. `font` is `bold`, `regular`, `italic`, or `bold_italic` (default `bold`); `rotation` is clockwise `0`, `90`, `180`, or `270` degrees (default `0`). Text is fit within its box without stretching.

Colors must be six-digit hex. Unsupported command types, extra fields, path-like slugs, invalid coordinates, and excessive element counts are rejected before rendering. The renderer uses DejaVu Sans and DejaVu Serif by default (`DejaVuSans.ttf`, `DejaVuSans-Bold.ttf`, `DejaVuSerif-Italic.ttf`, and `DejaVuSans-BoldOblique.ttf`); set the corresponding `FILM_RENDER_FONT_*` variables only when suitable local font files are available. Inspect glyph coverage for non-Latin text before rendering; do not silently claim unreadable text is accurate.
