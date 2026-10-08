"""Render independent raster label artwork on the shared 35 mm shell."""
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import bpy
from PIL import Image, ImageDraw
from label_artwork import (_assert_safe_write_directory, load_label_texture,
                           save_webp_with_limit, write_text_atomic)

VARIANTS = {
    'light-notes': 'Light Notes 135',
    'kodak-ultramax-400': 'Kodak UltraMax 400',
    'kodak-gold-200': 'Kodak Gold 200',
    'kodak-ektar-100': 'Kodak Ektar 100',
    'fuji-superia-400': 'Fujicolor Superia X-TRA 400',
    'ilford-hp5-400': 'Ilford HP5 Plus 400',
    # Retain the published identifier/artwork for existing package consumers.
    'kodak-portra-400': 'Kodak Portra 400',
}
REFERENCE_PRESETS = (
    'kodak-ultramax-400', 'kodak-gold-200', 'kodak-ektar-100',
    'fuji-superia-400', 'ilford-hp5-400',
)
SKILL_ROOT = Path(__file__).resolve().parents[1]
ARTWORK_DIR = SKILL_ROOT / 'examples' / 'artwork'


def artwork(variant):
    """Load a completed full-wrap raster texture; no label-layout schema is involved."""
    path = ARTWORK_DIR / f'{variant}.png'
    if not path.is_file():
        raise SystemExit(f'Missing preset texture: {path}')
    return load_label_texture(path)


def _cached_render_context(cache, output, model_revision):
    scene_path = cache / 'film-cartridge.blend'
    geometry_path = output / 'film-cartridge.geometry.json'
    original_path = output / 'film-cartridge-shell.webp'
    if not scene_path.exists() or not geometry_path.exists() or not original_path.exists():
        raise SystemExit(
            'Base shell assets are missing. Run render-film-cartridge.py once without '
            '--label-image or a non-default --variant first.'
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
        raise SystemExit('Cached shell frame differs from geometry. Regenerate the base shell first.')
    if (not (0 <= crop[0] < crop[2] <= frame['width']
             and 0 <= crop[1] < crop[3] <= frame['height'])
            or (crop[2] - crop[0], crop[3] - crop[1]) != size):
        raise SystemExit('Invalid geometry crop. Regenerate the base shell first.')

    scene.cycles.seed = 0
    label_object = bpy.data.objects.get('Fully wrapped printed stock')
    if label_object is None or not label_object.data.materials:
        raise SystemExit('Cached shell is missing its printed label material.')
    label = label_object.data.materials[0]
    texture_nodes = [node for node in label.node_tree.nodes if node.type == 'TEX_IMAGE']
    if not texture_nodes:
        raise SystemExit('Cached label material has no image texture.')

    with original_path.open('rb') as shell_file:
        shell_bytes = os.fstat(shell_file.fileno()).st_size
        shell_digest = hashlib.file_digest(shell_file, 'sha256').hexdigest()
        if (shell_bytes != geometry.get('bytes') or shell_bytes >= 250_000
                or shell_digest != geometry.get('sha256')):
            raise SystemExit('Blank shell identity differs from geometry. Regenerate the base shell first.')
        shell_file.seek(0)
        with Image.open(shell_file) as original:
            if original.mode != 'RGBA' or original.size != size:
                raise SystemExit('Original shell dimensions or mode differ from geometry. Regenerate the base shell first.')
            coverage = original.getchannel('A').copy()
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
    size = save_webp_with_limit(image, target, (92, 88, 84, 80, 76), byte_limit)
    print(f'Generated {target}: {size} bytes', flush=True)


def _write_inventory(destination, model_revision, size, coverage, rendered_ids):
    records = []
    for variant, name in VARIANTS.items():
        if variant not in rendered_ids:
            continue
        target = destination / f'{variant}.webp'
        with Image.open(target) as asset:
            if asset.size != size or asset.getchannel('A').tobytes() != coverage.tobytes():
                continue
            width, height = asset.size
        records.append(dict(id=variant, name=name, filename=target.name,
                            width=width, height=height, bytes=target.stat().st_size))
    manifest = dict(modelRevision=model_revision, geometry='./film-cartridge.geometry.json',
                    description='Original label interpretations built from individual wrap textures; not licensed artwork or exact packaging/year replicas.',
                    cartridges=records)
    write_text_atomic(destination / 'catalog.json', json.dumps(manifest, indent=2) + '\n')

    if not set(REFERENCE_PRESETS).issubset(rendered_ids):
        return
    temporary_path = None
    try:
        preview = Image.new('RGB', (1200, 485), '#d9d6cf')
        for index, variant in enumerate(REFERENCE_PRESETS):
            record = next((item for item in records if item['id'] == variant), None)
            if not record:
                continue
            with Image.open(destination / record['filename']) as image:
                image.thumbnail((225, 420), Image.Resampling.LANCZOS)
                preview.paste(image, (index * 240 + (240 - image.width) // 2, 12), image)
            ImageDraw.Draw(preview).text((index * 240 + 8, 450), record['name'], fill='#242424')
        preview_path = Path(tempfile.gettempdir()) / f'film-cartridges-contact-{os.geteuid()}.jpg'
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f'.film-cartridges-contact-{os.geteuid()}-', suffix='.jpg', dir=preview_path.parent
        )
        with os.fdopen(descriptor, 'wb') as temporary_file:
            preview.save(temporary_file, format='JPEG')
        os.replace(temporary_path, preview_path)
    except (OSError, ValueError) as error:
        print(f'Could not update optional contact sheet: {error}', file=sys.stderr, flush=True)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)


def render_variants(selection, cache, output, model_revision):
    scene, crop, size, coverage, texture = _cached_render_context(cache, output, model_revision)
    destination = output
    destination.mkdir(parents=True, exist_ok=True)
    _assert_safe_write_directory(destination)
    selected = tuple(VARIANTS) if selection == 'all' else (selection,)
    rendered_ids = set()
    with tempfile.TemporaryDirectory(prefix='film-roll-variants-', dir=destination) as staging_dir:
        staging = Path(staging_dir)
        (staging / '.film-roll-temp-marker').write_text('film-roll-skill-render-temp-v1', encoding='utf-8')
        for variant in selected:
            staged_target = staging / f'{variant}.webp'
            with tempfile.TemporaryDirectory(prefix=f'film-roll-render-{variant}-', dir=staging) as temporary:
                intermediate = Path(temporary)
                _render_label(
                    scene, texture, artwork(variant), intermediate / 'label.png',
                    intermediate / 'render.png', crop, coverage,
                    staged_target, 150_000,
                )
        for variant in selected:
            os.replace(staging / f'{variant}.webp', destination / f'{variant}.webp')
            rendered_ids.add(variant)
            _write_inventory(destination, model_revision, size, coverage, rendered_ids)


def render_custom_artwork(label_path, cache, output, model_revision):
    from label_artwork import label_slug

    label_path = Path(label_path)
    label_image = load_label_texture(label_path)
    slug = label_slug(label_path)
    if slug in VARIANTS:
        raise SystemExit(f'Custom label filename conflicts with built-in preset {slug!r}; use a distinct filename.')
    target = output / f'{slug}.webp'
    if target.exists() or target.is_symlink():
        raise SystemExit(f'Output already exists: {target}. Choose a new texture filename or output directory.')

    scene, crop, _, coverage, texture = _cached_render_context(cache, output, model_revision)
    cache.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    reservation = output / f'.film-roll-custom-reservation-{slug}'
    try:
        descriptor = os.open(
            reservation, os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, 'O_NOFOLLOW', 0), 0o600
        )
    except FileExistsError:
        raise SystemExit(f'Custom render is already reserved: {reservation}')
    os.close(descriptor)
    try:
        with tempfile.TemporaryDirectory(prefix=f'film-roll-custom-{slug}-', dir=cache) as temporary:
            intermediate = Path(temporary)
            (intermediate / '.film-roll-temp-marker').write_text('film-roll-skill-render-temp-v1', encoding='utf-8')
            _render_label(
                scene, texture, label_image,
                intermediate / 'label.png', intermediate / 'render.png',
                crop, coverage, target, 250_000,
            )
    except BaseException:
        reservation.unlink(missing_ok=True)
        raise
    reservation.unlink(missing_ok=True)
