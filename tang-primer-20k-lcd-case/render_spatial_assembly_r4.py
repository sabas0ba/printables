#!/usr/bin/env python3
"""Render transparent and exploded spatial assembly views from exact meshes."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from assembly_r4 import CASE_DEPTH, Part, assembled_parts, bounds, exploded_parts


def display_triangles(part: Part):
    # The official STEP-derived Dock mesh is dense.  Even sampling preserves a
    # faithful visual silhouette while keeping matplotlib memory bounded.
    limit = 75000 if "Official Dock" in part.name else 120000
    step = max(1, len(part.triangles) // limit)
    return part.triangles[::step]


def render_axis(ax, parts: list[Part], title: str, exploded: bool) -> None:
    for part in parts:
        ax.add_collection3d(Poly3DCollection(
            display_triangles(part), facecolor=part.color,
            edgecolor=part.color if len(part.triangles) > 100000 else "#25313b",
            linewidth=0.02 if len(part.triangles) > 100000 else 0.055,
            alpha=part.alpha,
        ))
    all_triangles = [tri for part in parts for tri in part.triangles[::max(1, len(part.triangles)//20000)] ]
    lower, upper = bounds(all_triangles)
    ax.set_xlim(-8, 148)
    ax.set_ylim(-4, 98)
    ax.set_zlim(lower[2] - 4, upper[2] + 5)
    ax.set_box_aspect((156, 102, max(48, upper[2] - lower[2] + 9)))
    ax.view_init(elev=27, azim=-55)
    ax.set_title(title, fontsize=13, fontweight="bold", pad=4)
    ax.set_xlabel("X  width", fontsize=8)
    ax.set_ylabel("Y  height", fontsize=8)
    ax.set_zlabel("Z  front -> rear", fontsize=8)
    ax.tick_params(labelsize=6, pad=0)
    ax.grid(True, linewidth=0.25, alpha=0.35)
    if not exploded:
        ax.text(72, 95, CASE_DEPTH + 1.0, f"assembled depth {CASE_DEPTH:.2f} mm", fontsize=8)


def render(input_dir: Path, dock_step_stl: Path | None, spec_key: str, output: Path) -> None:
    assembled = assembled_parts(input_dir, dock_step_stl, spec_key)
    exploded = exploded_parts(assembled)
    fig = plt.figure(figsize=(16, 9), constrained_layout=True)
    render_axis(fig.add_subplot(1, 2, 1, projection="3d"), assembled,
                "Transparent assembled view", False)
    render_axis(fig.add_subplot(1, 2, 2, projection="3d"), exploded,
                "Exploded on the real Z assembly axis", True)
    legend = [Patch(facecolor=p.color, edgecolor="#25313b", label=p.name, alpha=max(p.alpha, 0.72)) for p in assembled]
    fig.legend(handles=legend, loc="lower center", ncol=4, fontsize=8, frameon=False)
    size = "4.3-inch" if spec_key == "43" else "5.0-inch"
    fig.suptitle(
        f"Tang Primer 20K case R4 - {size} spatial assembly\n"
        + ("Dock and installed Core shown as the overall envelope of the official Sipeed STEP"
           if dock_step_stl is None else
           "Official Sipeed Dock 3713 STEP includes the Core 3690 in its installed position"),
        fontsize=16, fontweight="bold",
    )
    fig.text(0.5, 0.055,
        "Front shell -> LCD -> retainer -> tray -> Dock+Core -> access frame -> service cap.  3D views are NTS; dimensions are in mm.",
             ha="center", fontsize=9)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=190, facecolor="white")
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("output/release"))
    parser.add_argument("--dock-step-stl", type=Path,
                        help="STEP-derived Dock mesh; default: the Dock envelope box")
    parser.add_argument("--spec", choices=("43", "50"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.input, args.dock_step_stl, args.spec, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
