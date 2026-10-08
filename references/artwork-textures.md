# Full-wrap artwork textures

The skill interprets the user's cartridge photo and creates a complete raster label image. There is no label-element JSON schema: artwork may use any composition, fonts, gradients, illustration, typography, or texture needed for that reference. The Blender renderer only validates and applies the finished texture to the blank shell.

## Texture dimensions and projection

- Use an opaque PNG, JPEG, or WebP with a 2:1 aspect ratio. The loader accepts images from 512 × 256 up to 16 megapixels and 32 MiB, then normalizes them to 4096 × 2048.
- Use an opaque background. Transparent pixels are composited onto warm label stock.
- `x=0` and `x=1` meet at the rear seam; the visible front is centered near `x=0.5`. `y=0` is the top edge of the label.
- These coordinates describe only the cylinder projection. They do not prescribe a front panel width, side strip, text alignment, or shared layout.
- The 3D shell has no outward-projecting film leader. Keep all appearance differences on the label surface.

The renderer rejects invalid filenames, unsupported image files, and non-2:1 aspect ratios rather than silently stretching artwork.

## Built-in textures

`examples/artwork/` contains individual full-wrap textures for the five refreshed references, plus Light Notes and a compatibility Kodak Portra 400 appearance. The five current references are independently composed; their shared dimensions are only the texture projection contract, not a visual template.

The input product photo is not pasted into the render. The skill examines it and produces new label artwork, excluding the photographed background and surrounding objects. The PNG itself is the editable source of truth for its appearance.
