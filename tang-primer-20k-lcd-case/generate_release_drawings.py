#!/usr/bin/env python3
"""Generate the single authoritative R4 drawing set from delivered STL meshes."""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas

from assembly_r4 import read_binary_stl
from drawing_assembly_r4 import page_frame, section_sheet, three_view_sheet
from generate_drawings import MM, OUTLINE, calibration, dim_h, dim_v, line, notes_block, text


BLUE = HexColor("#335F87")


def _point_key(point):
    return tuple(round(value, 5) for value in point)


def _normal(triangle):
    a, b, c = triangle
    u = tuple(b[i] - a[i] for i in range(3))
    v = tuple(c[i] - a[i] for i in range(3))
    n = (
        u[1] * v[2] - u[2] * v[1],
        u[2] * v[0] - u[0] * v[2],
        u[0] * v[1] - u[1] * v[0],
    )
    length = math.sqrt(sum(value * value for value in n))
    return tuple(value / length for value in n) if length else (0.0, 0.0, 0.0)


def feature_edges(triangles):
    """Return STL crease edges while suppressing coplanar triangulation lines."""
    edge_normals = defaultdict(list)
    edge_points = {}
    for triangle in triangles:
        normal = _normal(triangle)
        for a, b in ((triangle[0], triangle[1]), (triangle[1], triangle[2]), (triangle[2], triangle[0])):
            ka, kb = _point_key(a), _point_key(b)
            key = tuple(sorted((ka, kb)))
            edge_normals[key].append(normal)
            edge_points[key] = (ka, kb)
    result = []
    for key, normals in edge_normals.items():
        keep = len(normals) == 1
        if not keep:
            first = normals[0]
            keep = any(abs(sum(first[i] * other[i] for i in range(3))) < 0.999 for other in normals[1:])
        if keep:
            result.append(edge_points[key])
    return result


def mesh_bounds(triangles):
    points = [point for tri in triangles for point in tri]
    return (
        tuple(min(point[i] for point in points) for i in range(3)),
        tuple(max(point[i] for point in points) for i in range(3)),
    )


def projection(c, edges, bounds, h_axis, v_axis, ox, oy, title):
    lower, upper = bounds
    text(c, ox, oy + upper[v_axis] - lower[v_axis] + 5, title, 3.2, OUTLINE, True)
    for a, b in edges:
        ax, ay = ox + a[h_axis] - lower[h_axis], oy + a[v_axis] - lower[v_axis]
        bx, by = ox + b[h_axis] - lower[h_axis], oy + b[v_axis] - lower[v_axis]
        if abs(ax - bx) + abs(ay - by) > 1e-6:
            line(c, ax, ay, bx, by, BLUE, 0.22)


def part_sheet(c, path: Path, title: str, sheet: str, notes: list[str]) -> None:
    triangles = read_binary_stl(path)
    bounds = mesh_bounds(triangles)
    edges = feature_edges(triangles)
    lower, upper = bounds
    sx, sy, sz = (upper[i] - lower[i] for i in range(3))
    page_frame(c, f"PRINTED PART - {title}", sheet, "1:1")
    projection(c, edges, bounds, 0, 1, 25, 151, "FRONT / XY - STL FEATURE EDGES")
    dim_h(c, 25, 25 + sx, 142, 151, f"{sx:.2f}")
    dim_v(c, 151, 151 + sy, 16, 25, f"{sy:.2f}")
    projection(c, edges, bounds, 0, 2, 25, 94, "TOP / XZ")
    dim_h(c, 25, 25 + sx, 85, 94, f"{sx:.2f}")
    dim_v(c, 94, 94 + sz, 16, 25, f"{sz:.2f}")
    projection(c, edges, bounds, 2, 1, 190, 151, "RIGHT / ZY")
    dim_h(c, 190, 190 + sz, 142, 151, f"{sz:.2f}")
    dim_v(c, 151, 151 + sy, 181, 190, f"{sy:.2f}")
    notes_block(c, 250, 250, "CONTROLLED GEOMETRY", [
        f"Source: {path.name}",
        f"STL bounds: {sx:.2f} x {sy:.2f} x {sz:.2f}",
        "Views are direct orthographic feature-edge projections.",
        "Coplanar STL facet diagonals are suppressed only.",
        *notes,
    ], [
        "Blue lines are generated from the delivered STL, not redrawn sketches.",
        "Print at 100%; verify the 100 mm bar and 20 mm square.",
    ])
    calibration(c)
    c.showPage()


def generate(output: Path, input_dir: Path, dock_stl: Path | None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output), pagesize=landscape(A3), pageCompression=1)
    c.setTitle("Tang Primer 20K LCD enclosure R4 authoritative 1:1 drawings")
    c.setAuthor("OpenAI Codex")
    three_view_sheet(c, "43", "1/13")
    three_view_sheet(c, "50", "2/13")
    section_sheet(c, input_dir, dock_stl, "43", "3/13")
    section_sheet(c, input_dir, dock_stl, "50", "4/13")
    part_sheet(c, input_dir / "front_shell_43_snap.stl", "FRONT SHELL 4.3", "5/13", [
        "Print orientation: XY display face on bed; supports: none.",
    ])
    part_sheet(c, input_dir / "lcd_retainer_43_snap.stl", "LCD RETAINER 4.3", "6/13", [
        "Print orientation: XY flat face on bed; supports: none.",
    ])
    part_sheet(c, input_dir / "front_shell_50_snap.stl", "FRONT SHELL 5.0", "7/13", [
        "Print orientation: XY display face on bed; supports: none.",
    ])
    part_sheet(c, input_dir / "lcd_retainer_50_snap.stl", "LCD RETAINER 5.0", "8/13", [
        "Print orientation: XY flat face on bed; supports: none.",
    ])
    part_sheet(c, input_dir / "dock_tray_screw_common.stl", "DOCK TRAY / M2.5", "9/13", [
        "4 x official holes on 87.00 x 65.00 pitch.",
        "Boss 7.00 square; pilot 2.00 square x 4.80 deep.",
        "Hardware: 4 x M2.5 x 6 pan-head screws.",
        "Open FPC rails: no bridge; secure with polyimide tape.",
    ])
    part_sheet(c, input_dir / "rear_access_frame_common.stl", "REAR ACCESS FRAME", "10/13", [
        "Print orientation: open flange XY face on bed; supports: none.",
        "Center opening is 120.00 x 92.00 for direct SODIMM/PMOD access.",
        "Frame remains fixed by the four original 37.00 mm case pins.",
    ])
    part_sheet(c, input_dir / "rear_service_cap_common.stl", "REAR SERVICE CAP", "11/13", [
        "Print orientation: rear lattice XY face on bed; supports: none.",
        "Install upper hooks first; rotate lower edge until both tabs click.",
        "Press both lower tabs inward, rotate outward and lift to remove.",
        "Two 20.00 mm open-edge cable exits retain connected PMOD leads.",
    ])
    part_sheet(c, input_dir / "case_snap_pin.stl", "CASE SNAP PIN", "12/13", [
        "Quantity: 4. Export orientation is the required flat orientation.",
        "Print fit_coupon.stl before the full enclosure.",
    ])
    part_sheet(c, input_dir / "fit_coupon.stl", "FIT COUPON", "13/13", [
        "Left: 4.30 square case-pin path. Right: 2.00 square M2.5 blind pilot.",
        "Use production material, orientation and slicer compensation.",
    ])
    c.save()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("output/release"))
    parser.add_argument("--dock-step-stl", type=Path,
                        help="STEP-derived Dock mesh; default: the Dock envelope box")
    parser.add_argument("--output", type=Path, default=Path("output/release/Tang_Primer_20K_Case_R4_Drawings_1to1.pdf"))
    args = parser.parse_args()
    generate(args.output, args.input, args.dock_step_stl)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
