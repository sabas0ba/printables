import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # the generators import each other as top-level modules
SPEC = importlib.util.spec_from_file_location("generate_case", ROOT / "generate_case.py")
assert SPEC and SPEC.loader
case = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = case
SPEC.loader.exec_module(case)


class GeometryTest(unittest.TestCase):
    def test_official_board_hole_pitch(self):
        holes = case.DOCK_HOLES
        self.assertAlmostEqual(holes[1][0] - holes[0][0], 87.0)
        self.assertAlmostEqual(holes[2][1] - holes[0][1], 65.0)

    def test_generate_all_variants(self):
        with tempfile.TemporaryDirectory() as directory:
            stats = case.generate(Path(directory))
            self.assertEqual(len(stats), 6)
            names = {item["file"] for item in stats}
            self.assertIn("front_shell_43.stl", names)
            self.assertIn("front_shell_50.stl", names)
            self.assertIn("dock_tray_common.stl", names)
            for item in stats:
                self.assertGreater(item["triangles"], 100)
                self.assertGreater(item["size_bytes"], 84)

    def test_case_encloses_largest_lcd(self):
        lcd = case.LCDS["50"]
        self.assertGreater(case.CASE_W, lcd.module_w + 2 * 8.0)
        self.assertGreater(case.CASE_H, lcd.module_h + 2 * 8.0)


if __name__ == "__main__":
    unittest.main()
