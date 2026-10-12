#!/usr/bin/env python3
"""Render the release STL set for visual inspection."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from render_preview import read_binary_stl


FILES = (
    "front_shell_43_snap.stl",
    "lcd_retainer_43_snap.stl",
    "front_shell_50_snap.stl",
    "lcd_retainer_50_snap.stl",
    "dock_tray_screw_common.stl",
    "rear_access_frame_common.stl",
    "rear_service_cap_common.stl",
    "case_snap_pin.stl",
    "fit_coupon.stl",
)


def render(input_dir: Path, output: Path) -> None:
    fig = plt.figure(figsize=(16, 9), constrained_layout=True)
    for index, name in enumerate(FILES, start=1):
        triangles = read_binary_stl(input_dir / name)
        ax = fig.add_subplot(3, 3, index, projection="3d")
        collection = Poly3DCollection(
            triangles,
            facecolor="#58a6d6",
            edgecolor="#1b3548",
            linewidth=0.08,
            alpha=0.93,
        )
        ax.add_collection3d(collection)
        points = [point for triangle in triangles for point in triangle]
        mins = [min(point[axis] for point in points) for axis in range(3)]
        maxs = [max(point[axis] for point in points) for axis in range(3)]
        spans = [maxs[i] - mins[i] for i in range(3)]
        ax.set_xlim(mins[0], maxs[0])
        ax.set_ylim(mins[1], maxs[1])
        ax.set_zlim(mins[2], max(maxs[2], mins[2] + 10.0))
        ax.set_box_aspect((max(spans[0], 10), max(spans[1], 10), max(spans[2], 10)))
        ax.view_init(elev=34, azim=-58)
        ax.set_title(name.removesuffix(".stl"), fontsize=9)
        ax.set_axis_off()
    fig.suptitle("Tang Primer 20K LCD enclosure release R4", fontsize=16)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180, facecolor="white")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("stl"))
    parser.add_argument("--output", type=Path, default=Path("output/printed_parts.png"))
    args = parser.parse_args()
    render(args.input, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
