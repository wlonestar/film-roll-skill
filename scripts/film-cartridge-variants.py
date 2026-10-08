"""Development-only representative film labels on the unchanged Light Notes shell."""
import json
from pathlib import Path

import bpy
from PIL import Image, ImageDraw

VARIANTS = {
    'kodak-gold-200': 'Kodak Gold 200',
    'kodak-portra-400': 'Kodak Portra 400',
    'kodak-ektar-100': 'Kodak Ektar 100',
    'fuji-superia-400': 'Fujicolor Superia X-TRA 400',
    'ilford-hp5-400': 'Ilford HP5 Plus 400',
}
SKILL_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DIR = SKILL_ROOT / 'examples'


def artwork(variant):
    """Load an executable design example; the JSON is the preset source of truth."""
    from custom_label import load_design, render_label

    design_path = EXAMPLE_DIR / f'{variant}.json'
    if not design_path.is_file():
        raise SystemExit(f'Missing skill preset example: {design_path}')
    design = load_design(design_path)
    if design['slug'] != variant:
        raise SystemExit(f'Preset slug {design["slug"]!r} does not match {variant!r}')
    return render_label(design)


def _cached_render_context(cache, output, model_revision):
    scene_path = cache / 'film-cartridge.blend'
    geometry_path = output / 'film-cartridge.geometry.json'
    original_path = output / 'film-cartridge.webp'
    if not scene_path.exists() or not geometry_path.exists() or not original_path.exists():
        raise SystemExit(
            'Base shell assets are missing. Run render-film-cartridge.py once without '
            '--design-json or a non-default --variant first.'
        )

    bpy.ops.wm.open_mainfile(filepath=str(scene_path))
    scene = bpy.context.scene
    geometry = json.loads(geometry_path.read_text())
    if scene.get('modelRevision') != model_revision or geometry.get('modelRevision') != model_revision:
        raise SystemExit('Cached shell and geometry revisions differ. Regenerate the base shell first.')

    frame = geometry['renderFrame']
    crop = tuple(geometry['crop'])
    size = (geometry['width'], geometry['height'])
    if ((scene.render.resolution_x, scene.render.resolution_y) != (frame['width'], frame['height'])
            or scene.render.resolution_percentage != 100):
        raise SystemExit('Cached scene frame differs from geometry. Regenerate the base shell first.')
    if (not (0 <= crop[0] < crop[2] <= frame['width']
             and 0 <= crop[1] < crop[3] <= frame['height'])
            or (crop[2] - crop[0], crop[3] - crop[1]) != size):
        raise SystemExit('Invalid geometry crop. Regenerate the base shell first.')

    scene.cycles.seed = 0
    label_object = bpy.data.objects.get('Fully wrapped printed stock')
    if label_object is None or not label_object.data.materials:
        raise SystemExit('Cached scene is missing its printed label material.')
    label = label_object.data.materials[0]
    texture_nodes = [node for node in label.node_tree.nodes if node.type == 'TEX_IMAGE']
    if not texture_nodes:
        raise SystemExit('Cached label material has no image texture.')

    with Image.open(original_path) as original:
        coverage = original.getchannel('A').copy()
    if coverage.size != size:
        raise SystemExit('Original alpha dimensions differ from geometry. Regenerate the base shell first.')
    return scene, crop, size, coverage, texture_nodes[0]


def _render_label(scene, texture, label_image, label_path, render_path,
                  crop, coverage, target, byte_limit):
    label_image.save(label_path)
    texture.image = bpy.data.images.load(str(label_path), check_existing=False)
    scene.render.filepath = str(render_path)
    bpy.ops.render.render(write_still=True)
    with Image.open(render_path) as rendered:
        image = rendered.convert('RGBA').crop(crop)
    if image.size != coverage.size:
        raise RuntimeError(f'{target}: rendered dimensions differ from the shared shell geometry')
    image.putalpha(coverage)
    for quality in (92, 88, 84, 80, 76):
        image.save(target, quality=quality, method=6, exact=True)
        if target.stat().st_size < byte_limit:
            break
    if target.stat().st_size >= byte_limit:
        raise RuntimeError(f'{target} exceeds the {byte_limit}-byte asset budget')
    print(f'Generated {target}: {target.stat().st_size} bytes', flush=True)


def render_variants(selection, cache, output, model_revision):
    scene, crop, size, coverage, texture = _cached_render_context(cache, output, model_revision)
    destination = output
    destination.mkdir(parents=True, exist_ok=True)
    selected = VARIANTS if selection == 'all' else [selection]
    for variant in selected:
        _render_label(
            scene, texture, artwork(variant), cache / f'{variant}-label.png',
            cache / f'{variant}-render.png', crop, coverage,
            destination / f'{variant}.webp', 150_000,
        )

    records = []
    for variant, name in VARIANTS.items():
        target = destination / f'{variant}.webp'
        if target.exists():
            with Image.open(target) as asset:
                if asset.size != size or asset.getchannel('A').tobytes() != coverage.tobytes():
                    continue  # Do not inventory stale assets during a partial regeneration.
                width, height = asset.size
            records.append(dict(id=variant, name=name, filename=target.name,
                                width=width, height=height, bytes=target.stat().st_size))
    manifest = dict(modelRevision=model_revision, geometry='./film-cartridge.geometry.json',
                    description='Unofficial label reconstructions based on photos of actual 135 cartridges; not licensed artwork or exact packaging/year replicas.',
                    cartridges=records)
    (destination / 'catalog.json').write_text(json.dumps(manifest, indent=2) + '\n')
    preview = Image.new('RGB', (1200, 485), '#d9d6cf')
    for index, record in enumerate(records):
        with Image.open(destination / record['filename']) as image:
            image.thumbnail((225, 420), Image.Resampling.LANCZOS)
            preview.paste(image, (index * 240 + (240 - image.width) // 2, 12), image)
        ImageDraw.Draw(preview).text((index * 240 + 8, 450), record['name'], fill='#242424')
    preview.save('/tmp/film-cartridges-contact.jpg')


def render_custom_design(design_path, cache, output, model_revision):
    from custom_label import load_design, render_label

    design = load_design(Path(design_path))
    target = output / f"{design['slug']}.webp"
    if target.exists():
        raise SystemExit(f'Output already exists: {target}. Choose a new design slug or output directory.')

    scene, crop, _, coverage, texture = _cached_render_context(cache, output, model_revision)
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    _render_label(
        scene, texture, render_label(design),
        cache / f"{design['slug']}-label.png",
        cache / f"{design['slug']}-render.png",
        crop, coverage, target, 250_000,
    )
