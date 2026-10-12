"""Generate the STL files of every LCD profile into stl/<profile>/.

The geometry is defined in tools/generate_stl.py and tools/profiles.py.
"""

from pathlib import Path

from tools import generate_stl
from tools.profiles import PROFILES


DIRECTORY = Path(__file__).resolve().parent
STL_DIRECTORY = DIRECTORY / "stl"


def main():
    for key, profile in PROFILES.items():
        generate_stl.generate(STL_DIRECTORY / key, profile)


if __name__ == "__main__":
    main()
