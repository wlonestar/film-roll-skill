import ast
import sys
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_ROOT / "scripts"))

from custom_label import load_design, render_label  # noqa: E402

PRESETS = (
    "kodak-gold-200",
    "kodak-portra-400",
    "kodak-ektar-100",
    "fuji-superia-400",
    "ilford-hp5-400",
)


def overlaps(first, second):
    return (first[0] < second[2] and second[0] < first[2]
            and first[1] < second[3] and second[1] < first[3])


class PresetDesignTests(unittest.TestCase):
    def test_overlap_guard_detects_the_old_portra_side_panel_collision(self):
        old_side_text = (1380 / 4096, 260 / 2048, 1660 / 4096, 900 / 2048)
        old_front_text = (1390 / 4096, 430 / 2048, 2680 / 4096, 535 / 2048)
        self.assertTrue(overlaps(old_side_text, old_front_text))

    def test_five_library_presets_are_executable_skill_examples(self):
        example_slugs = {path.stem for path in (SKILL_ROOT / "examples").glob("*.json")}
        self.assertTrue(set(PRESETS).issubset(example_slugs))

        variants_source = (SKILL_ROOT / "scripts" / "film-cartridge-variants.py").read_text()
        tree = ast.parse(variants_source)
        mapping = next(ast.literal_eval(node.value) for node in tree.body
                       if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == "VARIANTS"
                               for target in node.targets))
        self.assertEqual(set(mapping), set(PRESETS))

        for slug in PRESETS:
            with self.subTest(preset=slug):
                design = load_design(SKILL_ROOT / "examples" / f"{slug}.json")
                self.assertEqual(design["slug"], slug)
                self.assertEqual(render_label(design).size, (4096, 2048))

    def test_examples_retain_model_specific_label_signatures(self):
        designs = {slug: load_design(SKILL_ROOT / "examples" / f"{slug}.json")
                   for slug in PRESETS}

        def texts(slug):
            return {item["text"] for item in designs[slug]["elements"]
                    if item["type"] == "text"}

        gold = designs["kodak-gold-200"]
        self.assertEqual(gold["background"], "#F4B31A")
        self.assertTrue({"KODAK", "200", "35mm color print film"}.issubset(texts("kodak-gold-200")))
        self.assertNotIn("PORTRA 400", texts("kodak-gold-200"))

        portra = designs["kodak-portra-400"]
        self.assertTrue({"PORTRA 400", "KODAK PROFESSIONAL", "36 EXP"}.issubset(texts("kodak-portra-400")))
        portra_stripes = [item for item in portra["elements"] if item["type"] == "rect"]
        self.assertEqual(len(portra_stripes), 1)
        self.assertLess(portra_stripes[0]["box"][2] - portra_stripes[0]["box"][0], 0.04)

        ektar = designs["kodak-ektar-100"]
        self.assertTrue({"Ektar 100", "36 EXP"}.issubset(texts("kodak-ektar-100")))
        self.assertTrue(any(item["type"] == "rect" and item["fill"] == "#E7AA22"
                            for item in ektar["elements"]))

        fuji = designs["fuji-superia-400"]
        self.assertTrue({"SUPERIA", "X-TRA", "400", "FUJICOLOR", "FUJIFILM"}.issubset(texts("fuji-superia-400")))
        fuji_fonts = {item["font"] for item in fuji["elements"] if item["type"] == "text"}
        self.assertTrue({"italic", "bold_italic"}.issubset(fuji_fonts))

        ilford = designs["ilford-hp5-400"]
        self.assertTrue({"ILFORD", "HP5", "PLUS", "400"}.issubset(texts("ilford-hp5-400")))
        self.assertTrue(any(item["type"] == "rect" and item["fill"] == "#1B1C1B"
                            for item in ilford["elements"]))

    def test_all_example_text_boxes_are_separate(self):
        for design_path in sorted((SKILL_ROOT / "examples").glob("*.json")):
            with self.subTest(example=design_path.stem):
                design = load_design(design_path)
                text_boxes = [item["box"] for item in design["elements"]
                              if item["type"] == "text"]
                for index, box in enumerate(text_boxes):
                    for other in text_boxes[index + 1:]:
                        self.assertFalse(overlaps(box, other),
                                         f"{design_path.stem}: overlapping text boxes {box} and {other}")


if __name__ == "__main__":
    unittest.main()
