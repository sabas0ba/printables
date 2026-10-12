#!/usr/bin/env python3
"""Render generated binary STL files for design review (optional dependency)."""

from __future__ import annotations

import argparse
import struct
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


FILES = (
    "front_shell_43.stl",
    "lcd_retainer_43.stl",
    "front_shell_50.stl",
    "lcd_retainer_50.stl",
    "dock_tray_common.stl",
    "rear_cover_common.stl",
)


def read_binary_stl(path: Path):
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    triangles = []
    offset = 84
    for _ in range(count):
        values = struct.unpack_from("<12fH", data, offset)
        triangles.append((values[3:6], values[6:9], values[9:12]))
        offset += 50
    return triangles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("output"))
    parser.add_argument("--output", type=Path, default=Path("output/preview.png"))
    args = parser.parse_args()
    fig = plt.figure(figsize=(14, 9), constrained_layout=True)
    for index, name in enumerate(FILES, start=1):
        triangles = read_binary_stl(args.input / name)
        ax = fig.add_subplot(2, 3, index, projection="3d")
        collection = Poly3DCollection(
            triangles,
            facecolor="#58a6d6",
            edgecolor="#1b3548",
            linewidth=0.08,
            alpha=0.92,
        )
        ax.add_collection3d(collection)
        points = [point for triangle in triangles for point in triangle]
        mins = [min(point[axis] for point in points) for axis in range(3)]
        maxs = [max(point[axis] for point in points) for axis in range(3)]
        ax.set_xlim(mins[0], maxs[0])
        ax.set_ylim(mins[1], maxs[1])
        ax.set_zlim(mins[2], max(maxs[2], mins[2] + 12.0))
        ax.set_box_aspect((140, 92, 38))
        ax.view_init(elev=34, azim=-58)
        ax.set_title(name.removesuffix(".stl"), fontsize=10)
        ax.set_axis_off()
    fig.suptitle("Tang Primer 20K Dock + RGB LCD case", fontsize=16)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=180, facecolor="white")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

