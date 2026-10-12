import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # the generators import each other as top-level modules
SPEC = importlib.util.spec_from_file_location("generate_drawings", ROOT / "generate_drawings.py")
assert SPEC and SPEC.loader
drawings = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = drawings
SPEC.loader.exec_module(drawings)


class DrawingTest(unittest.TestCase):
    def test_a3_ten_page_drawing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "drawing.pdf"
            drawings.generate(path)
            reader = PdfReader(path)
            self.assertEqual(len(reader.pages), 10)
            for page in reader.pages:
                width_mm = float(page.mediabox.width) / drawings.MM
                height_mm = float(page.mediabox.height) / drawings.MM
                self.assertAlmostEqual(width_mm, 420.0, places=2)
                self.assertAlmostEqual(height_mm, 297.0, places=2)

    def test_scale_constant_is_physical_mm(self):
        self.assertAlmostEqual(drawings.MM, 72.0 / 25.4, places=10)


if __name__ == "__main__":
    unittest.main()
