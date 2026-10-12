#!/usr/bin/env python3
"""Verify release geometry and write a machine-readable report."""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import math
from pathlib import Path

from pypdf import PdfReader

import assembly_r4 as assembly
import generate_case_r4 as design


STL_FILES = (
    "front_shell_43_snap.stl", "lcd_retainer_43_snap.stl",
    "front_shell_50_snap.stl", "lcd_retainer_50_snap.stl",
    "dock_tray_screw_common.stl", "rear_access_frame_common.stl",
    "rear_service_cap_common.stl",
    "case_snap_pin.stl", "fit_coupon.stl",
)
ASSEMBLY_STL_FILES = (
    "Tang_Primer_20K_Case_R4_Complete_Assembly_43.stl",
    "Tang_Primer_20K_Case_R4_Complete_Assembly_50.stl",
)
SINGLE_PART_STL_FILES = (
    "lcd_retainer_43_snap.stl",
    "lcd_retainer_50_snap.stl",
)


def normal(triangle):
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


def point_in_xy(point, triangle, tolerance=1e-6):
    x, y = point
    a, b, c = ((p[0], p[1]) for p in triangle)
    denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(denominator) < tolerance:
        return False
    u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / denominator
    v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / denominator
    w = 1.0 - u - v
    return min(u, v, w) >= -tolerance


def unsupported_box_bases(triangles):
    """Check the full base of every z-raised box against lower box volume.

    The release tray and rear cover are constructed exclusively from Mesh.box
    primitives.  Each contributes exactly 12 consecutive triangles, so this
    check evaluates the union support which a slicer creates from overlaps.
    """
    if len(triangles) % 12:
        raise ValueError("box-only printability check requires 12-triangle groups")
    boxes = [assembly.bounds(triangles[index:index + 12]) for index in range(0, len(triangles), 12)]
    unsupported = []
    for lower, upper in boxes:
        if lower[2] <= 1e-5:
            continue
        z = lower[2] - 1e-4
        samples = [
            (lower[0] + (upper[0] - lower[0]) * fx,
             lower[1] + (upper[1] - lower[1]) * fy)
            for fx in (0.02, 0.25, 0.50, 0.75, 0.98)
            for fy in (0.02, 0.25, 0.50, 0.75, 0.98)
        ]
        for x, y in samples:
            if not any(
                support_lower[0] - 1e-5 <= x <= support_upper[0] + 1e-5
                and support_lower[1] - 1e-5 <= y <= support_upper[1] + 1e-5
                and support_lower[2] - 1e-5 <= z <= support_upper[2] + 1e-5
                for support_lower, support_upper in boxes
            ):
                unsupported.append({"box_min": lower, "box_max": upper, "sample": (x, y, z)})
                break
    return unsupported


def mesh_topology(triangles):
    """Report exact triangle-edge topology for a generated STL mesh."""
    edge_triangles = defaultdict(list)
    edge_directions = defaultdict(list)
    canonical_triangles = set()
    duplicate_triangles = 0
    for index, triangle in enumerate(triangles):
        canonical = tuple(sorted(triangle))
        if canonical in canonical_triangles:
            duplicate_triangles += 1
        canonical_triangles.add(canonical)
        for start, end in ((0, 1), (1, 2), (2, 0)):
            edge = tuple(sorted((triangle[start], triangle[end])))
            edge_triangles[edge].append(index)
            edge_directions[edge].append((triangle[start], triangle[end]) == edge)

    adjacent = [set() for _ in triangles]
    for indexes in edge_triangles.values():
        for index in indexes:
            adjacent[index].update(other for other in indexes if other != index)
    pending = set(range(len(triangles)))
    components = 0
    while pending:
        components += 1
        stack = [pending.pop()]
        while stack:
            index = stack.pop()
            neighbors = adjacent[index] & pending
            pending.difference_update(neighbors)
            stack.extend(neighbors)

    return {
        "surface_components": components,
        "boundary_edges": sum(len(indexes) == 1 for indexes in edge_triangles.values()),
        "non_manifold_edges": sum(len(indexes) > 2 for indexes in edge_triangles.values()),
        "inconsistent_winding_edges": sum(
            len(directions) == 2 and directions[0] == directions[1]
            for directions in edge_directions.values()
        ),
        "duplicate_triangles": duplicate_triangles,
    }


def generate(input_dir: Path, drawing: Path, specification: Path, output: Path) -> dict:
    stl_checks = []
    meshes = {}
    for filename in STL_FILES:
        triangles = assembly.read_binary_stl(input_dir / filename)
        meshes[filename] = triangles
        lower, upper = assembly.bounds(triangles)
        finite = all(math.isfinite(value) for triangle in triangles for point in triangle for value in point)
        check = {
            "file": filename, "triangles": len(triangles),
            "bounds_min_mm": lower, "bounds_max_mm": upper,
            "finite": finite, "print_bed_z0": abs(lower[2]) < 1e-6,
        }
        if filename in SINGLE_PART_STL_FILES:
            check.update(mesh_topology(triangles))
        stl_checks.append(check)

    assembly_stl_checks = []
    for filename in ASSEMBLY_STL_FILES:
        triangles = assembly.read_binary_stl(input_dir / filename)
        lower, upper = assembly.bounds(triangles)
        assembly_stl_checks.append({
            "file": filename,
            "triangles": len(triangles),
            "bounds_min_mm": lower,
            "bounds_max_mm": upper,
            "viewer_reference_only": True,
        })

    dock_global = assembly.official_global_bounds(
        assembly.DOCK_STEP_BOUNDS_LOCAL, assembly.DOCK_STEP_OFFSET,
    )
    rear_inner = assembly.CASE_DEPTH - design.WALL
    pilot_depth = design.TRAY_T + design.DOCK_STANDOFF_H - design.DOCK_PILOT_BOTTOM
    screw_engagement = design.DOCK_SCREW_LENGTH - design.DOCK_PCB_T_NOMINAL
    report = {
        "revision": "R4",
        "version": design.PROJECT_VERSION,
        "result": "PASS",
        "stl": stl_checks,
        "complete_assembly_stl": assembly_stl_checks,
        "checks": {
            "dock_hole_pitch_mm": [
                design.DOCK_HOLES[1][0] - design.DOCK_HOLES[0][0],
                design.DOCK_HOLES[2][1] - design.DOCK_HOLES[0][1],
            ],
            "dock_fasteners": "4 x M2.5 x 6 pan-head",
            "pilot_depth_mm": pilot_depth,
            "plastic_engagement_mm": screw_engagement,
            "pilot_bottom_clearance_mm": pilot_depth - screw_engagement,
            "official_step_to_rear_inner_clearance_mm": rear_inner - dock_global[1][2],
            "dock_tray_unsupported_box_bases": len(unsupported_box_bases(meshes["dock_tray_screw_common.stl"])),
            "rear_access_frame_unsupported_box_bases": len(unsupported_box_bases(meshes["rear_access_frame_common.stl"])),
            "service_access_opening_mm": [design.ACCESS_OPENING[2], design.ACCESS_OPENING[3]],
            "service_extension_depth_mm": design.SERVICE_CAP_DEPTH,
            "service_cap_hooks": design.SERVICE_HOOK_COUNT,
            "service_cap_push_tabs": design.SERVICE_LATCH_COUNT,
            "drawing_pages": len(PdfReader(drawing).pages),
            "specification_pages": len(PdfReader(specification).pages),
        },
        "limitations": [
            "No slicer executable is installed; toolpath-level bridge analysis was not run.",
            "Physical fit, screw torque, FPC bend allowance and long-duration vibration remain prototype tests.",
        ],
    }
    checks = report["checks"]
    if not all(item["finite"] and item["print_bed_z0"] for item in stl_checks):
        report["result"] = "FAIL"
    if not all(
        item["surface_components"] == 1
        and item["boundary_edges"] == 0
        and item["non_manifold_edges"] == 0
        and item["inconsistent_winding_edges"] == 0
        and item["duplicate_triangles"] == 0
        for item in stl_checks
        if item["file"] in SINGLE_PART_STL_FILES
    ):
        report["result"] = "FAIL"
    if not all(
        abs(item["bounds_min_mm"][2] + 1.8) < 1e-4
        and abs(item["bounds_max_mm"][2] - 53.8) < 1e-4
        for item in assembly_stl_checks
    ):
        report["result"] = "FAIL"
    if checks["dock_tray_unsupported_box_bases"] or checks["rear_access_frame_unsupported_box_bases"]:
        report["result"] = "FAIL"
    if checks["drawing_pages"] != 13 or checks["pilot_bottom_clearance_mm"] < 0.35:
        report["result"] = "FAIL"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("output/release"))
    parser.add_argument("--drawing", type=Path, default=Path("output/release/Tang_Primer_20K_Case_R4_Drawings_1to1.pdf"))
    parser.add_argument("--specification", type=Path, default=Path("output/release/Tang_Primer_20K_Case_R4_Design_Specification.pdf"))
    parser.add_argument("--output", type=Path, default=Path("output/release/verification_report.json"))
    args = parser.parse_args()
    report = generate(args.input, args.drawing, args.specification, args.output)
    print(f"{args.output}: {report['result']}")
    return 0 if report["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
