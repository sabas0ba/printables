#!/usr/bin/env python3
"""Layout checks for the generated A4 drawing documents."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import create_retention_design as retention  # noqa: E402
from tools import create_scale_drawing as scale  # noqa: E402
from tools.profiles import PROFILES  # noqa: E402


# Content areas inside each sheet frame, in millimetres: (x0, y0, x1, y1).
# The title block above and the footer text below are excluded.
SCALE_CONTENT = (7.0, 7.0, 290.0, 188.5)
SCALE_KEEPOUTS = (
    (7.0, 7.0, 155.0, 12.8),     # print instruction
    (180.0, 7.0, 282.0, 17.0),   # 100 mm calibration line
)
RETENTION_CONTENT = (7.0, 7.0, 290.0, 185.5)
RETENTION_KEEPOUTS = (
    (7.0, 7.0, 200.0, 12.8),     # reference dimensions footer
)


def overlaps(a, b) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


class DrawingLayout(unittest.TestCase):
    def check_document(self, module, content, keepouts):
        for profile in PROFILES.values():
            with tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "drawing.pdf"
                bounds = scale.recorded_bounds(
                    lambda: module.create_pdf(output, profile)
                )
            self.assertTrue(bounds)
            for page, x0, y0, x1, y1 in bounds:
                box = (x0, y0, x1, y1)
                with self.subTest(profile=profile.key, page=page,
                                  box=tuple(round(v, 2) for v in box)):
                    self.assertGreaterEqual(x0, content[0])
                    self.assertGreaterEqual(y0, content[1])
                    self.assertLessEqual(x1, content[2])
                    self.assertLessEqual(y1, content[3])
                    for keepout in keepouts:
                        self.assertFalse(overlaps(box, keepout))

    def test_scale_drawing_stays_inside_the_sheet_frame(self):
        self.check_document(scale, SCALE_CONTENT, SCALE_KEEPOUTS)

    def test_retention_design_stays_inside_the_sheet_frame(self):
        self.check_document(retention, RETENTION_CONTENT, RETENTION_KEEPOUTS)


if __name__ == "__main__":
    unittest.main()
