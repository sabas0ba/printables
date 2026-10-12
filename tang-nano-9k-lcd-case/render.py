"""Render the views and drawings of every LCD profile into output/<profile>/.

Reads the STL files written by generate.py. Each profile gets three PNG views
in images/ and three PDF documents in pdf/.
"""

from pathlib import Path

from generate import STL_DIRECTORY
from tools import create_retention_design, create_scale_drawing, create_visuals
from tools.profiles import PROFILES


DIRECTORY = Path(__file__).resolve().parent
OUTPUT_DIRECTORY = DIRECTORY / "output"


def main():
    for key, profile in PROFILES.items():
        output = OUTPUT_DIRECTORY / key
        create_visuals.create_profile_visuals(STL_DIRECTORY / key, output, profile)
        create_scale_drawing.create_pdf(
            output / "pdf" / create_scale_drawing.OUTPUT_NAME, profile)
        create_retention_design.create_pdf(
            output / "pdf" / create_retention_design.OUTPUT_NAME, profile)


if __name__ == "__main__":
    main()
