# film-roll-skill

`film-roll-skill` is an optional companion skill for the [`film-roll`](https://github.com/wlonestar/film-roll) package. It helps a coding agent turn a film-canister reference photo into original wrap artwork and a transparent WebP render that can be used as a cartridge appearance in `film-roll`. The skill is not a package dependency and does not change package assets unless you ask.

This is an Agent Skill, not a Pi-only feature. Any agent host that supports the Agent Skills format can use it; the host handles skill discovery and invocation.

## Install with an agent

Ask an agent that supports Agent Skills:

> Install `film-roll-skill` from https://github.com/wlonestar/film-roll-skill using this agent host's supported Agent Skills mechanism, then confirm it's available.

![Five film-canister appearances rendered for film-roll: Kodak UltraMax 400, Kodak Gold 200, Kodak Ektar 100, Fujicolor Superia X-TRA 400, and Ilford HP5 Plus 400](examples/preset-preview.jpg)

## Use with an agent

Give your agent a reference photo and ask for a render, for example:

> Use this canister photo as a reference. Create a transparent WebP render for film-roll, keeping the label's distinctive layout and adding no projecting film leader.

You can also ask for one of the included appearances:

> Render the Kodak Gold 200 canister appearance as a transparent WebP and show me the result.

New renders go under `output/` by default. To use one in `film-roll`, provide its WebP and matching `film-cartridge.geometry.json` as a custom cartridge. The skill only updates package assets when you explicitly request it.

## Contents

- `SKILL.md`: the image-to-render workflow and output rules.
- `scripts/`: artwork preparation and the Blender-based canister renderer.
- `references/`: artwork texture and renderer notes.
- `examples/preset-preview.jpg`: preview of the five refreshed reference appearances.
- `examples/artwork/`: full-wrap raster artwork for the references and examples.

The shell geometry is a reusable plain 35 mm canister, not a photogrammetric reconstruction. Renders do not include a loose film tail or projecting tab. Product labels are original interpretations of their references, not claims of exact packaging or licensed replicas.
