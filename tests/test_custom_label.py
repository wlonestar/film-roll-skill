import sys
import unittest
from pathlib import Path

from PIL import Image, ImageChops

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from custom_label import load_design, render_label, validate_design  # noqa: E402
from render_reference import _next_output_dir  # noqa: E402


class CustomLabelTests(unittest.TestCase):
    def test_example_design_renders_at_wrapped_texture_size(self):
        design = load_design(SKILL_ROOT / "examples" / "amber-400.json")
        image = render_label(design)

        self.assertEqual(image.size, (4096, 2048))
        self.assertEqual(image.getpixel((0, 0)), (240, 181, 27))
        self.assertEqual(image.getpixel((1200, 1000)), (23, 24, 23))
        blank = Image.new("RGB", image.size, (240, 181, 27))
        self.assertIsNotNone(ImageChops.difference(image, blank).getbbox())

    def test_supports_regular_bold_and_italic_font_variants(self):
        for font in ("regular", "bold", "italic", "bold_italic"):
            with self.subTest(font=font):
                image = render_label({
                    "slug": "font-sample",
                    "background": "#FFFFFF",
                    "elements": [{
                        "type": "text", "text": "X-TRA", "box": [0.2, 0.2, 0.8, 0.8],
                        "color": "#111111", "font": font,
                    }],
                })
                self.assertIsNotNone(ImageChops.difference(
                    image, Image.new("RGB", image.size, (255, 255, 255))
                ).getbbox())

    def test_rejects_path_like_output_slug(self):
        with self.assertRaisesRegex(ValueError, "slug"):
            validate_design({"slug": "../outside", "background": "#FFFFFF", "elements": []})

    def test_rejects_invalid_normalized_geometry(self):
        with self.assertRaisesRegex(ValueError, "normalized"):
            validate_design({
                "slug": "bad-box",
                "background": "#FFFFFF",
                "elements": [{"type": "rect", "box": [-0.1, 0, 0.5, 1], "fill": "#000000"}],
            })

    def test_rejects_unknown_draw_commands(self):
        with self.assertRaisesRegex(ValueError, "rect.*line.*text"):
            validate_design({
                "slug": "bad-command",
                "background": "#FFFFFF",
                "elements": [{"type": "shell", "box": [0, 0, 1, 1]}],
            })

    def test_rejects_non_hex_colors(self):
        with self.assertRaisesRegex(ValueError, "#RRGGBB"):
            validate_design({"slug": "bad-color", "background": "yellow", "elements": []})

    def test_output_allocator_uses_new_directory_on_collision(self):
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as temp:
            root = Path(temp)
            first = _next_output_dir(root, "amber-400")
            second = _next_output_dir(root, "amber-400")
            self.assertEqual(first.name, "amber-400")
            self.assertEqual(second.name, "amber-400-02")
            self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
