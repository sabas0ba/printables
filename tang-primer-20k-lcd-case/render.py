"""Render the views, drawings and reports into output/ and verify the release.

Reads the STL files written by generate.py. The Dock and the installed Core
appear as the envelope box of the official STEP in every view. Exits with a
non-zero status when the verification report is not PASS.
"""

from pathlib import Path

from reportlab import rl_config

# Omit creation timestamps and random document IDs from the PDF files.
rl_config.invariant = 1

import generate_design_spec_r4  # noqa: E402
import generate_reference_3mf_r4  # noqa: E402
import generate_release_drawings  # noqa: E402
import render_preview_r4  # noqa: E402
import render_spatial_assembly_r4  # noqa: E402
import verify_release  # noqa: E402
from generate import LCD_KEYS, STL_DIRECTORY  # noqa: E402


DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = DIRECTORY / "output"
DRAWING = OUTPUT_DIRECTORY / "Tang_Primer_20K_Case_R4_Drawings_1to1.pdf"
SPECIFICATION = OUTPUT_DIRECTORY / "Tang_Primer_20K_Case_R4_Design_Specification.pdf"


def main():
    for key in LCD_KEYS:
        render_spatial_assembly_r4.render(
            STL_DIRECTORY, None, key, OUTPUT_DIRECTORY / f"assembly_{key}.png")
        generate_reference_3mf_r4.generate(
            OUTPUT_DIRECTORY / f"Tang_Primer_20K_Case_R4_Reference_Assembly_{key}.3mf",
            STL_DIRECTORY, None, key)
    render_preview_r4.render(STL_DIRECTORY, OUTPUT_DIRECTORY / "printed_parts.png")
    generate_release_drawings.generate(DRAWING, STL_DIRECTORY, None)
    generate_design_spec_r4.generate(SPECIFICATION)
    report = verify_release.generate(
        STL_DIRECTORY, DRAWING, SPECIFICATION, OUTPUT_DIRECTORY / "verification_report.json")
    if report["result"] != "PASS":
        raise SystemExit("verification_report.json: " + report["result"])


if __name__ == "__main__":
    main()
