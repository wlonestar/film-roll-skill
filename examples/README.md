# Independent full-wrap appearances

The five refreshed branded appearances are authored as individual raster textures based on the supplied photos of actual 135 canisters. There is no shared label grid or vector-command template. The first reference included a retail box and multiple Kodak canisters; only the UltraMax canister's label informed that texture.

![Rendered preview of the five individually reconstructed cartridges](preset-preview.jpg)

| Appearance | Texture | Reference |
| --- | --- | --- |
| Kodak UltraMax 400 | [Full-wrap PNG](artwork/kodak-ultramax-400.png) | User-supplied Kodak UltraMax canister photo; box artwork excluded. |
| Kodak Gold 200 | [Full-wrap PNG](artwork/kodak-gold-200.png) | User-supplied close-up of the yellow Kodak 200 canister. |
| Kodak Ektar 100 | [Full-wrap PNG](artwork/kodak-ektar-100.png) | User-supplied image and [actual 135 canister](https://commons.wikimedia.org/wiki/File:Kodak_Ektar_100_135_film_cartridge_(01).jpg). |
| Fujicolor Superia X-TRA 400 | [Full-wrap PNG](artwork/fuji-superia-400.png) | User-supplied image and [actual Superia canister](https://www.adorama.com/images/Large/fjchsp36.jpg). |
| Ilford HP5 Plus 400 | [Full-wrap PNG](artwork/ilford-hp5-400.png) | User-supplied image and [official HP5 Plus canister page](https://ilford.co.jp/photo/product/hp5-plus/). |

`artwork/light-notes.png` is the separate fictional example appearance. `artwork/kodak-portra-400.png` remains for compatibility with the already published package identifier, but is not part of the refreshed five. All textures are source artwork for the `--variant` renderer. The five refreshed PNGs can be rebuilt with `python3 scripts/build_reference_artwork.py`. The WebP uses a plain canister shell with no side-projecting piece.
