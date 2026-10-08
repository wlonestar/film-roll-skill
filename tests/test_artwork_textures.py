import ast
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageChops

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from label_artwork import (TEXTURE_SIZE, _assert_private_cache_directory, label_slug,
                           load_label_texture, save_webp_with_limit)  # noqa: E402
import render_reference  # noqa: E402

REFERENCE_PRESETS = (
    "kodak-ultramax-400",
    "kodak-gold-200",
    "kodak-ektar-100",
    "fuji-superia-400",
    "ilford-hp5-400",
)
ALL_ARTWORK = ("light-notes", *REFERENCE_PRESETS, "kodak-portra-400")
ARTWORK_DIR = SKILL_ROOT / "examples" / "artwork"


class ArtworkTextureTests(unittest.TestCase):
    def test_each_preset_is_an_independent_full_wrap_texture(self):
        hashes = set()
        for slug in ALL_ARTWORK:
            with self.subTest(preset=slug):
                path = ARTWORK_DIR / f"{slug}.png"
                image = load_label_texture(path)
                self.assertEqual(image.mode, "RGB")
                self.assertEqual(image.size, TEXTURE_SIZE)
                self.assertIsNotNone(ImageChops.difference(
                    image, Image.new("RGB", image.size, image.getpixel((0, 0)))
                ).getbbox())
                hashes.add(hash(image.tobytes()))
        self.assertEqual(len(hashes), len(ALL_ARTWORK))

    def test_preset_renderer_uses_raster_artwork_not_a_shared_command_schema(self):
        variants_path = SKILL_ROOT / "scripts" / "film-cartridge-variants.py"
        tree = ast.parse(variants_path.read_text())
        mapping = next(ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == "VARIANTS"
                               for target in node.targets))
        self.assertEqual(set(mapping), set(ALL_ARTWORK))
        source = variants_path.read_text()
        self.assertIn("load_label_texture", source)
        self.assertNotIn("custom_label", source)

    def test_blank_shell_has_no_side_projecting_film_piece(self):
        renderer = (SKILL_ROOT / "scripts" / "render-film-cartridge.py").read_text()
        self.assertIn("Fully wrapped printed stock", renderer)
        self.assertIn("film-cartridge-shell.webp", renderer)
        self.assertIn("surface_strip('Full height felt opening'", renderer)
        self.assertNotIn("Front folded slit lip", renderer)
        self.assertNotIn("bpy.ops.mesh.primitive_cube_add", renderer)
        self.assertNotIn("perforated_leader", renderer)
        self.assertNotIn("Exposed film leader", renderer)

    def test_matching_but_stale_shell_cache_is_not_reused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, base = root / "cache", root / "base"
            cache.mkdir()
            base.mkdir()
            (cache / "film-cartridge.blend").write_bytes(b"old scene")
            (base / "film-cartridge-shell.webp").write_bytes(b"old shell")
            (base / "film-cartridge.geometry.json").write_text(
                json.dumps({"modelRevision": "true-shell-v12"}), encoding="utf-8"
            )
            matching_old_scene = subprocess.CompletedProcess(
                [], 0, stdout="__SCENE_REVISION__true-shell-v12\n", stderr=""
            )
            with patch.object(render_reference.subprocess, "run", return_value=matching_old_scene) as run:
                self.assertFalse(render_reference._base_is_current(Path(sys.executable), cache, base))
                run.assert_not_called()

    def test_base_cache_rejects_shell_size_mismatch_before_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, base = root / "cache", root / "base"
            cache.mkdir()
            base.mkdir()
            (cache / "film-cartridge.blend").write_bytes(b"scene")
            (base / "film-cartridge-shell.webp").write_bytes(b"broken")
            geometry = {
                "modelRevision": "true-shell-v15", "bytes": 6, "sha256": "0" * 64,
                "renderFrame": {"width": 10, "height": 10},
                "crop": [0, 0, 10, 10], "width": 10, "height": 10,
            }
            (base / "film-cartridge.geometry.json").write_text(json.dumps(geometry), encoding="utf-8")
            with patch.object(render_reference.subprocess, "run") as run:
                self.assertFalse(render_reference._base_is_current(Path(sys.executable), cache, base))
                run.assert_not_called()

    def test_malformed_geometry_cache_is_treated_as_stale(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, base = root / "cache", root / "base"
            cache.mkdir()
            base.mkdir()
            (cache / "film-cartridge.blend").write_bytes(b"scene")
            shell = base / "film-cartridge-shell.webp"
            shell.write_bytes(b"shell bytes")
            geometry = {
                "modelRevision": "true-shell-v15", "bytes": shell.stat().st_size,
                "sha256": hashlib.sha256(shell.read_bytes()).hexdigest(),
                "renderFrame": {"width": 100, "height": 200},
                "crop": [], "width": 10, "height": 20,
            }
            (base / "film-cartridge.geometry.json").write_text(json.dumps(geometry), encoding="utf-8")
            geometry_file = base / "film-cartridge.geometry.json"
            with patch.object(render_reference.subprocess, "run") as run:
                self.assertFalse(render_reference._base_is_current(Path(sys.executable), cache, base))
                geometry_file.write_bytes(bytes([255]))
                self.assertFalse(render_reference._base_is_current(Path(sys.executable), cache, base))
                run.assert_not_called()

    def test_base_cache_rejects_scene_frame_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache, base = root / "cache", root / "base"
            cache.mkdir()
            base.mkdir()
            (cache / "film-cartridge.blend").write_bytes(b"scene")
            shell = base / "film-cartridge-shell.webp"
            shell.write_bytes(b"shell bytes")
            geometry = {
                "modelRevision": "true-shell-v15", "bytes": shell.stat().st_size,
                "sha256": hashlib.sha256(shell.read_bytes()).hexdigest(),
                "renderFrame": {"width": 100, "height": 200},
                "crop": [0, 0, 10, 20], "width": 10, "height": 20,
            }
            (base / "film-cartridge.geometry.json").write_text(json.dumps(geometry), encoding="utf-8")
            output = chr(10).join([
                "__SCENE_REVISION__true-shell-v15",
                "__SCENE_INFO__[99, 200, 100]",
                '__SHELL_INFO__["WEBP", "RGBA", 10, 20]',
            ])
            result = subprocess.CompletedProcess([], 0, stdout=output, stderr="")
            with patch.object(render_reference.subprocess, "run", return_value=result):
                self.assertFalse(render_reference._base_is_current(Path(sys.executable), cache, base))

    def test_reference_materials_have_paper_and_molded_surface_shading(self):
        renderer = (SKILL_ROOT / "scripts" / "render-film-cartridge.py").read_text()
        self.assertIn("Fine paper fibers", renderer)
        self.assertIn("Satin stock roughness variation", renderer)
        self.assertIn("Subtle molded horizontal rings", renderer)
        self.assertIn("Broad upper-left key", renderer)
        self.assertIn("Low front shadow fill", renderer)
        self.assertIn("MODEL_REVISION = 'true-shell-v15'", renderer)
        wrapper = (SKILL_ROOT / "scripts" / "render_reference.py").read_text()
        self.assertIn("if slug in BUILT_IN_SLUGS:", wrapper)
        self.assertIn("fcntl.flock", renderer)
        self.assertIn("cleanup_stale_intermediates(CACHE)", renderer)
        artwork_builder = (SKILL_ROOT / "scripts" / "build_reference_artwork.py").read_text()
        self.assertIn("shadow_color=", artwork_builder)

    def test_partial_variant_render_does_not_catalog_stale_assets(self):
        variants = (SKILL_ROOT / "scripts" / "film-cartridge-variants.py").read_text()
        self.assertIn("rendered_ids = set()", variants)
        self.assertIn("if variant not in rendered_ids:", variants)
        self.assertIn("_write_inventory(destination, model_revision, size, coverage, rendered_ids)", variants)
        self.assertNotIn("manifest_path.unlink(missing_ok=True)", variants)
        self.assertIn("tempfile.TemporaryDirectory", variants)
        self.assertIn("os.O_EXCL", variants)
        self.assertIn("if slug in VARIANTS:", variants)
        self.assertIn("TemporaryDirectory(prefix='film-roll-variants-'", variants)
        self.assertIn("os.replace(staging / f'{variant}.webp'", variants)
        self.assertIn("save_webp_with_limit", variants)
        self.assertIn("hashlib.file_digest", variants)
        self.assertIn("write_text_atomic(destination / 'catalog.json'", variants)
        self.assertIn("os.replace(temporary_path, preview_path)", variants)

    def test_webp_write_replaces_a_symlink_without_touching_its_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            victim = root / "victim.bin"
            victim.write_bytes(b"leave this file unchanged")
            target = root / "render.webp"
            target.symlink_to(victim)

            size = save_webp_with_limit(Image.new("RGB", (512, 256), "#4287B8"),
                                        target, (90,), 100_000)
            self.assertFalse(target.is_symlink())
            self.assertEqual(target.stat().st_size, size)
            self.assertEqual(victim.read_bytes(), b"leave this file unchanged")
            with Image.open(target) as rendered:
                self.assertEqual(rendered.format, "WEBP")

    def test_cache_directory_must_be_user_owned_and_not_shared_writable(self):
        with tempfile.TemporaryDirectory() as temporary:
            shared = Path(temporary) / "cache"
            shared.mkdir()
            shared.chmod(0o1777)
            with self.assertRaisesRegex(PermissionError, "render cache must be private"):
                _assert_private_cache_directory(shared)

    def test_atomic_renderer_rejects_shared_nonsticky_output_directories(self):
        with tempfile.TemporaryDirectory() as temporary:
            shared = Path(temporary) / "shared"
            shared.mkdir()
            shared.chmod(0o777)
            with self.assertRaisesRegex(PermissionError, "untrusted shared directory"):
                save_webp_with_limit(Image.new("RGB", (512, 256), "white"),
                                     shared / "render.webp", (90,), 100_000)
            self.assertFalse((shared / "render.webp").exists())

    def test_accepts_and_normalizes_a_transparent_arbitrary_texture(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "custom-label.png"
            Image.new("RGBA", (1024, 512), (20, 90, 160, 128)).save(path)
            image = load_label_texture(path)
            self.assertEqual(image.size, TEXTURE_SIZE)
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(label_slug(path), "custom-label")
            self.assertNotEqual(image.getpixel((0, 0)), (255, 255, 255))

    def test_rejects_non_wrap_aspect_and_path_like_names(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bad_shape = root / "bad-shape.png"
            Image.new("RGB", (640, 480), "white").save(bad_shape)
            with self.assertRaisesRegex(ValueError, "2:1"):
                load_label_texture(bad_shape)

            near_wrap = root / "near-wrap.png"
            Image.new("RGB", (1025, 512), "white").save(near_wrap)
            with self.assertRaisesRegex(ValueError, "exactly 2:1"):
                load_label_texture(near_wrap)

            with self.assertRaisesRegex(ValueError, "filename"):
                label_slug(root / "Bad Name.png")

    def test_rejects_oversized_image_before_loading_pixels(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "oversized.png"
            Image.new("RGB", (6000, 3000), "white").save(path)
            with self.assertRaisesRegex(ValueError, "16 megapixels"):
                load_label_texture(path)


if __name__ == "__main__":
    unittest.main()
