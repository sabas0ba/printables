#!/usr/bin/env python3
"""Generate a single STL containing the complete R4 assembly.

This is a dimensional viewer reference, not a printable merged model. It
contains overlapping closed meshes for every modeled assembly component.
"""

from __future__ import annotations

import argparse
import math
import struct
from pathlib import Path

from assembly_r4 import Triangle, assembled_parts, bounds


def triangle_normal(triangle: Triangle) -> tuple[float, float, float] | None:
    a, b, c = triangle
    ux, uy, uz = (b[index] - a[index] for index in range(3))
    vx, vy, vz = (c[index] - a[index] for index in range(3))
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz)
    if length <= 1e-12:
        return None
    return (nx / length, ny / length, nz / length)


def write_binary_stl(path: Path, triangles: list[Triangle], title: str) -> int:
    valid = [(triangle, triangle_normal(triangle)) for triangle in triangles]
    valid = [(triangle, normal) for triangle, normal in valid if normal is not None]
    path.parent.mkdir(parents=True, exist_ok=True)
    header = title.encode("ascii")[:80].ljust(80, b"\0")
    with path.open("wb") as stream:
        stream.write(header)
        stream.write(struct.pack("<I", len(valid)))
        for (a, b, c), normal in valid:
            stream.write(struct.pack("<12fH", *(normal + a + b + c), 0))
    return len(triangles) - len(valid)


def generate(output: Path, input_dir: Path, dock_stl: Path | None, spec_key: str) -> dict[str, object]:
    parts = assembled_parts(input_dir, dock_stl, spec_key)
    triangles = [triangle for part in parts for triangle in part.triangles]
    lower, upper = bounds(triangles)
    removed = write_binary_stl(
        output,
        triangles,
        f"Tang Primer 20K R4 {spec_key} complete assembly - VIEW ONLY",
    )
    return {
        "file": output.name,
        "spec": spec_key,
        "parts": [part.name for part in parts],
        "triangles": len(triangles) - removed,
        "removed_degenerate_triangles": removed,
        "bounds_min_mm": [round(value, 5) for value in lower],
        "bounds_max_mm": [round(value, 5) for value in upper],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("output/release"))
    parser.add_argument("--dock-step-stl", type=Path,
                        help="STEP-derived Dock mesh; default: the Dock envelope box")
    parser.add_argument("--spec", choices=("43", "50"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = generate(args.output, args.input, args.dock_step_stl, args.spec)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
