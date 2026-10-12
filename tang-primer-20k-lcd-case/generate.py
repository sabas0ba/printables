"""Generate the printable STL files and the two view-only assemblies into stl/.

The geometry is defined in generate_case.py and generate_case_r4.py. The
complete assemblies place every part, the LCD and the Dock envelope box in
assembly coordinates; they are for viewing, not for slicing.
"""

from pathlib import Path

import generate_assembled_stl_r4
import generate_case_r4


DIRECTORY = Path(__file__).resolve().parent
STL_DIRECTORY = DIRECTORY / "stl"
LCD_KEYS = ("43", "50")


def complete_assembly(key):
    return STL_DIRECTORY / f"Tang_Primer_20K_Case_R4_Complete_Assembly_{key}.stl"


def main():
    generate_case_r4.generate(STL_DIRECTORY)
    for key in LCD_KEYS:
        generate_assembled_stl_r4.generate(complete_assembly(key), STL_DIRECTORY, None, key)


if __name__ == "__main__":
    main()
