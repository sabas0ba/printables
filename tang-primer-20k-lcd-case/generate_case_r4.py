#!/usr/bin/env python3
"""Generate the R4 Tang Primer 20K LCD enclosure.

The enclosure and LCD retainer remain tool-less.  The Dock is fixed with four
M2.5 screws through its official corner holes into blind printed pilot bosses.
Every delivered part is exported in its intended, support-free print
orientation.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Sequence

from generate_case import (
    BEZEL_T,
    CASE_H,
    CASE_W,
    DOCK_H,
    DOCK_HOLES,
    DOCK_W,
    DOCK_X,
    DOCK_Y,
    FRONT_DEPTH,
    LCDS,
    Mesh,
    TRAY_T,
    WALL,
    add_lcd_locators,
    stl_stats,
)


PROJECT_VERSION = Path(__file__).with_name("VERSION").read_text(encoding="ascii").strip()
PIN_HOLE = 4.30
REAR_FRAME_DEPTH = 22.00
SERVICE_CAP_DEPTH = 20.00
STRUCTURAL_DEPTH = BEZEL_T + FRONT_DEPTH + TRAY_T + REAR_FRAME_DEPTH
CASE_DEPTH = STRUCTURAL_DEPTH + SERVICE_CAP_DEPTH
PIN_SHAFT = 3.50
PIN_HEAD = 7.50
PIN_HEAD_T = 1.80
PIN_LATCH_SHOULDER = STRUCTURAL_DEPTH
PIN_TIP = PIN_HEAD_T + PIN_LATCH_SHOULDER + 1.40

ACCESS_OPENING = (10.0, 10.0, CASE_W - 20.0, CASE_H - 20.0)
SERVICE_HOOK_X = (40.0, 86.0)
SERVICE_HOOK_W = 14.0
SERVICE_TONGUE_T = 1.20
SERVICE_SLOT_CLEARANCE = 0.60
SERVICE_HOOK_REACH = 23.00
SERVICE_UPPER_TONGUE_REACH = SERVICE_CAP_DEPTH + WALL
SERVICE_DETENT = 1.00
SERVICE_CABLE_EXITS = ((35.0, 20.0), (85.0, 20.0))
SERVICE_HOOK_COUNT = 2
SERVICE_LATCH_COUNT = 2

DOCK_PCB_T_NOMINAL = 1.590
DOCK_STANDOFF_H = 3.20
DOCK_SCREW_NOMINAL = 2.50
DOCK_SCREW_LENGTH = 6.00
DOCK_PILOT = 2.00
DOCK_PILOT_BOTTOM = 0.80
DOCK_BOSS = 7.00

RETAINER_CLIP_ARM_T = 1.20
RETAINER_CLIP_W = 8.00
RETAINER_CLIP_OVERLAP = 0.80
RETAINER_CLIP_COUNT = 6
DOCK_SCREW_COUNT = 4

ASSEMBLY_HOLES = ((5.0, 5.0), (135.0, 5.0), (5.0, 107.0), (135.0, 107.0))


def square_frame(mesh: Mesh, cx: float, cy: float, outer: float, inner: float,
                 z: float, depth: float) -> None:
    ox, oy = cx - outer / 2.0, cy - outer / 2.0
    ix, iy = cx - inner / 2.0, cy - inner / 2.0
    mesh.box(ox, oy, z, outer, iy - oy, depth)
    mesh.box(ox, iy + inner, z, outer, oy + outer - (iy + inner), depth)
    mesh.box(ox, iy, z, ix - ox, inner, depth)
    mesh.box(ix + inner, iy, z, ox + outer - (ix + inner), inner, depth)


def plate_with_rect_cutouts(
    mesh: Mesh,
    outer: tuple[float, float, float, float],
    cutouts: list[tuple[float, float, float, float]],
    z: float,
    depth: float,
) -> None:
    """Tile an XY plate without relying on boolean subtraction."""
    ox, oy, ow, oh = outer
    xs = sorted({ox, ox + ow, *(v for x, _, w, _ in cutouts for v in (x, x + w))})
    ys = sorted({oy, oy + oh, *(v for _, y, _, h in cutouts for v in (y, y + h))})
    for x1, x2 in zip(xs, xs[1:]):
        for y1, y2 in zip(ys, ys[1:]):
            if x2 <= ox or x1 >= ox + ow or y2 <= oy or y1 >= oy + oh:
                continue
            cx, cy = (x1 + x2) / 2.0, (y1 + y2) / 2.0
            if any(x <= cx <= x + w and y <= cy <= y + h for x, y, w, h in cutouts):
                continue
            mesh.box(x1, y1, z, x2 - x1, y2 - y1, depth)


def tri_prism_y(mesh: Mesh, points: tuple[tuple[float, float], ...],
                y: float, height: float) -> None:
    """Add a triangular prism; points are (x, z), extrusion is along Y."""
    if len(points) != 3:
        raise ValueError("tri_prism_y requires exactly three points")
    a, b, c = points
    front = ((a[0], y, a[1]), (b[0], y, b[1]), (c[0], y, c[1]))
    back = tuple((x, y + height, z) for x, _, z in front)
    mesh.tri(front[0], front[2], front[1])
    mesh.tri(back[0], back[1], back[2])
    for i, j in ((0, 1), (1, 2), (2, 0)):
        mesh.tri(front[i], front[j], back[j])
        mesh.tri(front[i], back[j], back[i])


def tri_prism_z(mesh: Mesh, points: tuple[tuple[float, float], ...],
                z: float, height: float) -> None:
    """Add a triangular prism; points are (x, y), extrusion is along Z."""
    if len(points) != 3:
        raise ValueError("tri_prism_z requires exactly three points")
    a, b, c = points
    bottom = ((a[0], a[1], z), (b[0], b[1], z), (c[0], c[1], z))
    top = tuple((x, y, z + height) for x, y, _ in bottom)
    mesh.tri(bottom[0], bottom[2], bottom[1])
    mesh.tri(top[0], top[1], top[2])
    for i, j in ((0, 1), (1, 2), (2, 0)):
        mesh.tri(bottom[i], bottom[j], top[j])
        mesh.tri(bottom[i], top[j], top[i])


def add_front_bezel(mesh: Mesh, spec_key: str) -> None:
    spec = LCDS[spec_key]
    cx = CASE_W / 2.0
    cy = CASE_H / 2.0 + spec.window_offset_y
    window = (
        cx - spec.window_w / 2.0,
        cy - spec.window_h / 2.0,
        spec.window_w,
        spec.window_h,
    )
    pin_cutouts = [
        (x - PIN_HOLE / 2.0, y - PIN_HOLE / 2.0, PIN_HOLE, PIN_HOLE)
        for x, y in ASSEMBLY_HOLES
    ]
    plate_with_rect_cutouts(mesh, (0, 0, CASE_W, CASE_H), [window, *pin_cutouts], 0, BEZEL_T)


def add_case_pin_bosses(mesh: Mesh, z: float, depth: float) -> None:
    for x, y in ASSEMBLY_HOLES:
        square_frame(mesh, x, y, 8.0, PIN_HOLE, z, depth)


def add_retainer_snap_hooks(mesh: Mesh) -> None:
    """Six independent arms retain the LCD retainer before case closure."""
    z = BEZEL_T
    arm_h = FRONT_DEPTH - 0.35
    hook_z = BEZEL_T + FRONT_DEPTH - 0.80
    for cy in (37.0, 75.0):
        mesh.box(2.80, cy - RETAINER_CLIP_W / 2, z,
                 RETAINER_CLIP_ARM_T, RETAINER_CLIP_W, arm_h)
        mesh.box(4.00, cy - RETAINER_CLIP_W / 2, hook_z,
                 RETAINER_CLIP_OVERLAP, RETAINER_CLIP_W, 0.80)
        mesh.box(CASE_W - 4.00, cy - RETAINER_CLIP_W / 2, z,
                 RETAINER_CLIP_ARM_T, RETAINER_CLIP_W, arm_h)
        mesh.box(CASE_W - 4.80, cy - RETAINER_CLIP_W / 2, hook_z,
                 RETAINER_CLIP_OVERLAP, RETAINER_CLIP_W, 0.80)
    for cx in (52.0, 88.0):
        mesh.box(cx - RETAINER_CLIP_W / 2, CASE_H - 4.00, z,
                 RETAINER_CLIP_W, RETAINER_CLIP_ARM_T, arm_h)
        mesh.box(cx - RETAINER_CLIP_W / 2, CASE_H - 4.80, hook_z,
                 RETAINER_CLIP_W, RETAINER_CLIP_OVERLAP, 0.80)


def build_front_shell_snap(spec_key: str) -> Mesh:
    spec = LCDS[spec_key]
    mesh = Mesh(f"front_shell_{spec_key}_snap")
    add_front_bezel(mesh, spec_key)
    add_lcd_locators(mesh, spec)
    z = BEZEL_T
    mesh.box(0, 0, z, WALL, CASE_H, FRONT_DEPTH)
    mesh.box(CASE_W - WALL, 0, z, WALL, CASE_H, FRONT_DEPTH)
    mesh.box(WALL, 0, z, CASE_W - 2 * WALL, WALL, FRONT_DEPTH)
    mesh.box(WALL, CASE_H - WALL, z, CASE_W - 2 * WALL, WALL, FRONT_DEPTH)
    add_case_pin_bosses(mesh, 0, BEZEL_T + FRONT_DEPTH)
    add_retainer_snap_hooks(mesh)
    return mesh


def retainer_rectangles(spec_key: str) -> list[tuple[float, float, float, float]]:
    """Return the connected open-frame profile for an LCD retainer."""
    spec = LCDS[spec_key]
    clearance = 0.30
    outer_w = spec.module_w + clearance
    outer_h = spec.module_h + clearance
    inner_w = spec.module_w - 5.0
    inner_h = spec.module_h - 5.0
    outer_x = (CASE_W - outer_w) / 2.0
    outer_y = (CASE_H - outer_h) / 2.0
    inner_x = (CASE_W - inner_w) / 2.0
    inner_y = (CASE_H - inner_h) / 2.0
    gap_left = CASE_W / 2.0 - 40.0
    gap_right = CASE_W / 2.0 + 40.0

    rectangles = [
        (outer_x, inner_y + inner_h, outer_w, outer_y + outer_h - (inner_y + inner_h)),
        (outer_x, inner_y, inner_x - outer_x, inner_h),
        (inner_x + inner_w, inner_y, outer_x + outer_w - (inner_x + inner_w), inner_h),
        (outer_x, outer_y, gap_left - outer_x, inner_y - outer_y),
        (gap_right, outer_y, outer_x + outer_w - gap_right, inner_y - outer_y),
        (9.0, 4.0, 122.0, 4.0),
        (9.0, CASE_H - 8.0, 122.0, 4.0),
        (4.0, 9.0, 4.0, CASE_H - 18.0),
        (132.0, 9.0, 4.0, CASE_H - 18.0),
        (8.0, CASE_H / 2.0 - 3.0, outer_x - 7.0, 6.0),
        (outer_x + outer_w - 1.0, CASE_H / 2.0 - 3.0,
         132.0 - (outer_x + outer_w - 1.0), 6.0),
        (24.0, 8.0, 3.0, outer_y - 7.0),
        (113.0, 8.0, 3.0, outer_y - 7.0),
        (CASE_W / 2.0 - 3.0, outer_y + outer_h - 1.0, 6.0,
         CASE_H - 8.0 - (outer_y + outer_h - 1.0)),
    ]
    return rectangles


def build_retainer_snap(spec_key: str) -> Mesh:
    spec = LCDS[spec_key]
    mesh = Mesh(f"lcd_retainer_{spec_key}_snap")
    mesh.extruded_rect_union(retainer_rectangles(spec_key), 0, spec.retainer_t)
    return mesh


def add_edge_frame_with_pin_holes(mesh: Mesh, z: float, depth: float) -> None:
    mesh.box(9, 0, z, 122, 3, depth)
    mesh.box(9, CASE_H - 3, z, 122, 3, depth)
    mesh.box(0, 9, z, 3, CASE_H - 18, depth)
    mesh.box(CASE_W - 3, 9, z, 3, CASE_H - 18, depth)
    for x, y in ASSEMBLY_HOLES:
        square_frame(mesh, x, y, 8.0, PIN_HOLE, z, depth)


def add_dock_screw_boss(mesh: Mesh, cx: float, cy: float) -> None:
    """Blind square pilot for an M2.5 x 6 screw, printable without bridging."""
    board_bottom = TRAY_T + DOCK_STANDOFF_H
    square_frame(
        mesh, cx, cy, DOCK_BOSS, DOCK_PILOT,
        DOCK_PILOT_BOTTOM, board_bottom - DOCK_PILOT_BOTTOM,
    )
    # A closed 0.8 mm floor prevents the screw entering the LCD volume.
    mesh.box(
        cx - DOCK_PILOT / 2.0, cy - DOCK_PILOT / 2.0, 0,
        DOCK_PILOT, DOCK_PILOT, DOCK_PILOT_BOTTOM,
    )


def add_open_fpc_guide(mesh: Mesh) -> None:
    """Two open rails locate the FPC; tape supplies removable strain relief."""
    mesh.box(44.0, 17.0, TRAY_T, 2.0, 4.0, 1.60)
    mesh.box(94.0, 17.0, TRAY_T, 2.0, 4.0, 1.60)


def build_dock_tray_screw() -> Mesh:
    mesh = Mesh("dock_tray_screw_common")
    add_edge_frame_with_pin_holes(mesh, 0, TRAY_T)
    lower_y = DOCK_HOLES[0][1]
    upper_y = DOCK_HOLES[2][1]
    for row_y in (lower_y, upper_y):
        row_holes = [
            (x - DOCK_PILOT / 2.0, y - DOCK_PILOT / 2.0,
             DOCK_PILOT, DOCK_PILOT)
            for x, y in DOCK_HOLES if y == row_y
        ]
        plate_with_rect_cutouts(
            mesh, (3, row_y - DOCK_BOSS / 2.0, CASE_W - 6, DOCK_BOSS),
            row_holes, 0, TRAY_T,
        )
    for x, y in DOCK_HOLES:
        add_dock_screw_boss(mesh, x, y)
    add_open_fpc_guide(mesh)
    return mesh


def rear_frame_cutouts() -> list[tuple[float, float, float, float]]:
    """Open center, pin paths and dedicated service-cap engagement slots."""
    cutouts = [ACCESS_OPENING]
    cutouts.extend(
        (x - PIN_HOLE / 2.0, y - PIN_HOLE / 2.0, PIN_HOLE, PIN_HOLE)
        for x, y in ASSEMBLY_HOLES
    )
    for x in SERVICE_HOOK_X:
        cutouts.append((x - 0.20, 108.60, SERVICE_HOOK_W + 0.40, 2.80))
        cutouts.append((x - 0.20, 0.60, SERVICE_HOOK_W + 0.40, 2.20))
    return cutouts


def build_rear_access_frame() -> Mesh:
    """Pinned structural frame; its center remains open for board access."""
    mesh = Mesh("rear_access_frame_common")
    plate_with_rect_cutouts(
        mesh, (0, 0, CASE_W, CASE_H), rear_frame_cutouts(), 0, WALL,
    )
    z = WALL
    mesh.box(0, 0, z, WALL, CASE_H, REAR_FRAME_DEPTH - WALL)
    mesh.box(CASE_W - WALL, 0, z, WALL, CASE_H, REAR_FRAME_DEPTH - WALL)
    mesh.box(WALL, CASE_H - WALL, z, CASE_W - 2 * WALL, WALL, REAR_FRAME_DEPTH - WALL)
    # Bottom connector bay remains open between the two short wall segments.
    mesh.box(WALL, 0, z, 15.6 - WALL, WALL, REAR_FRAME_DEPTH - WALL)
    mesh.box(122.0, 0, z, CASE_W - WALL - 122.0, WALL, REAR_FRAME_DEPTH - WALL)
    for x, y in ASSEMBLY_HOLES:
        square_frame(mesh, x, y, 8.0, PIN_HOLE, 0, REAR_FRAME_DEPTH)
    return mesh


def add_service_cap_face(mesh: Mesh) -> None:
    """Ventilated rear face with every first-layer rib connected."""
    mesh.box(0, 0, 0, CASE_W, WALL, WALL)
    mesh.box(0, CASE_H - WALL, 0, CASE_W, WALL, WALL)
    mesh.box(0, WALL, 0, WALL, CASE_H - 2 * WALL, WALL)
    mesh.box(CASE_W - WALL, WALL, 0, WALL, CASE_H - 2 * WALL, WALL)
    for x in (31.5, 68.5, 105.5):
        mesh.box(x, WALL, 0, 3.0, CASE_H - 2 * WALL, WALL)
    mesh.box(WALL, CASE_H / 2.0 - 1.5, 0, CASE_W - 2 * WALL, 3.0, WALL)


def tri_prism_x(mesh: Mesh, points: tuple[tuple[float, float], ...],
                x: float, width: float) -> None:
    """Add a triangular prism; points are (y, z), extrusion is along X."""
    if len(points) != 3:
        raise ValueError("tri_prism_x requires exactly three points")
    a, b, c = points
    left = ((x, a[0], a[1]), (x, b[0], b[1]), (x, c[0], c[1]))
    right = tuple((x + width, y, z) for _, y, z in left)
    mesh.tri(left[0], left[1], left[2])
    mesh.tri(right[0], right[2], right[1])
    for i, j in ((0, 1), (1, 2), (2, 0)):
        mesh.tri(left[i], right[i], right[j])
        mesh.tri(left[i], right[j], left[j])


def build_rear_service_cap() -> Mesh:
    """Tool-less deep cap: insert two upper hooks, then snap two lower tabs."""
    mesh = Mesh("rear_service_cap_common")
    add_service_cap_face(mesh)
    z = WALL
    wall_depth = SERVICE_CAP_DEPTH - WALL
    mesh.box(0, 0, z, WALL, CASE_H, wall_depth)
    mesh.box(CASE_W - WALL, 0, z, WALL, CASE_H, wall_depth)
    mesh.box(WALL, CASE_H - WALL, z, CASE_W - 2 * WALL, WALL, wall_depth)
    # Two 20 mm open-edge cable exits allow PMOD leads to remain connected.
    cursor = WALL
    for exit_x, exit_w in SERVICE_CABLE_EXITS:
        mesh.box(cursor, 0, z, exit_x - cursor, WALL, wall_depth)
        cursor = exit_x + exit_w
    mesh.box(cursor, 0, z, CASE_W - WALL - cursor, WALL, wall_depth)
    for x in SERVICE_HOOK_X:
        # Rigid upper insertion tongue, supported by the top wall below it.
        # It ends at the inner face of the frame plate: the frame top wall
        # starts there and overlaps the tongue in Y. Only the detent, which
        # lies below the wall, reaches SERVICE_HOOK_REACH.
        mesh.box(x, 109.20, z, SERVICE_HOOK_W, SERVICE_TONGUE_T,
                 SERVICE_UPPER_TONGUE_REACH - z)
        tri_prism_x(mesh, (
            (109.20, 20.00),
            (109.20 - SERVICE_DETENT, 22.60),
            (109.20, SERVICE_HOOK_REACH),
        ), x, SERVICE_HOOK_W)
        # Lower flex tab starts at the rear face and is isolated by the cable bay.
        mesh.box(x, 1.00, z, SERVICE_HOOK_W, SERVICE_TONGUE_T,
                 SERVICE_HOOK_REACH - z)
        tri_prism_x(mesh, (
            (2.20, 20.00),
            (2.20 + SERVICE_DETENT, 22.60),
            (2.20, SERVICE_HOOK_REACH),
        ), x, SERVICE_HOOK_W)
    return mesh


def build_case_snap_pin() -> Mesh:
    mesh = Mesh("case_snap_pin")
    cy = PIN_HEAD / 2.0
    # The pin is exported on its side so the flexible prongs follow XY layers.
    mesh.box(0, 0, 0, PIN_HEAD_T, PIN_HEAD, PIN_HEAD)
    shaft_y = cy - PIN_SHAFT / 2.0
    mesh.box(PIN_HEAD_T, shaft_y, 0, 26.1, PIN_SHAFT, PIN_SHAFT)
    gap = 0.60
    prong_w = (PIN_SHAFT - gap) / 2.0
    split_x = 26.8
    mesh.box(split_x, shaft_y, 0, PIN_TIP - split_x, prong_w, PIN_SHAFT)
    mesh.box(split_x, cy + gap / 2.0, 0,
             PIN_TIP - split_x, prong_w, PIN_SHAFT)
    shoulder_x = PIN_HEAD_T + PIN_LATCH_SHOULDER
    tri_prism_z(mesh, (
        (shoulder_x, cy - gap / 2.0),
        (shoulder_x, cy - 2.25),
        (PIN_TIP, cy - PIN_SHAFT / 2.0),
    ), 0, PIN_SHAFT)
    tri_prism_z(mesh, (
        (shoulder_x, cy + gap / 2.0),
        (PIN_TIP, cy + PIN_SHAFT / 2.0),
        (shoulder_x, cy + 2.25),
    ), 0, PIN_SHAFT)
    return mesh


def build_fit_coupon() -> Mesh:
    """Coupon for the case pin and M2.5 printed-pilot fit."""
    mesh = Mesh("fit_coupon")
    plate_with_rect_cutouts(
        mesh,
        (0, 0, 20, 20),
        [(10 - PIN_HOLE / 2.0, 10 - PIN_HOLE / 2.0, PIN_HOLE, PIN_HOLE)],
        0,
        3.0,
    )
    mesh.box(30, 0, 0, 20, 20, DOCK_PILOT_BOTTOM)
    square_frame(
        mesh, 40, 10, 12.0, DOCK_PILOT,
        DOCK_PILOT_BOTTOM, 5.60 - DOCK_PILOT_BOTTOM,
    )
    mesh.box(
        40 - DOCK_PILOT / 2.0, 10 - DOCK_PILOT / 2.0, 0,
        DOCK_PILOT, DOCK_PILOT, DOCK_PILOT_BOTTOM,
    )
    return mesh


def generate(out_dir: Path) -> list[dict[str, object]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    meshes = [
        build_front_shell_snap("43"),
        build_retainer_snap("43"),
        build_front_shell_snap("50"),
        build_retainer_snap("50"),
        build_dock_tray_screw(),
        build_rear_access_frame(),
        build_rear_service_cap(),
        build_case_snap_pin(),
        build_fit_coupon(),
    ]
    stats: list[dict[str, object]] = []
    for mesh in meshes:
        path = out_dir / f"{mesh.name}.stl"
        mesh.write_stl(path)
        stats.append(stl_stats(path))
    manifest = {
        "design": "Tang Primer 20K integrated LCD enclosure release R4",
        "version": PROJECT_VERSION,
        "units": "mm",
        "status": "prototype - physical fit required before production use",
        "case": {
            "width": CASE_W,
            "height": CASE_H,
            "structural_depth": STRUCTURAL_DEPTH,
            "service_extension_depth": SERVICE_CAP_DEPTH,
            "assembled_depth_nominal": CASE_DEPTH,
        },
        "retention": {
            "lcd": "pocket plus six PETG cantilever hooks and edge retainer",
            "dock": "four M2.5 x 6 screws through official corner holes into printed blind pilots",
            "core": "Dock SODIMM connector latches",
            "fpc": "open 50 mm guide with removable polyimide tape strain relief",
            "case": "four removable printed split snap pins to the structural access frame",
            "rear_service": "two rigid upper hooks plus two push-release lower PETG tabs",
        },
        "print_quantities": {
            "case_snap_pin.stl": 4,
            "selected_front_shell": 1,
            "selected_lcd_retainer": 1,
            "dock_tray_screw_common.stl": 1,
            "rear_access_frame_common.stl": 1,
            "rear_service_cap_common.stl": 1,
            "fit_coupon.stl": 1,
        },
        "snap_fit": {
            "case_hole": PIN_HOLE,
            "case_pin_shaft": PIN_SHAFT,
            "case_pin_head": PIN_HEAD,
            "case_latch_shoulder": PIN_LATCH_SHOULDER,
            "dock_board_thickness_step": 1.590,
            "dock_screw": "M2.5 x 6 pan head",
            "dock_pilot_square": DOCK_PILOT,
            "dock_pilot_depth": TRAY_T + DOCK_STANDOFF_H - DOCK_PILOT_BOTTOM,
        },
        "dock": {
            "pcb": [DOCK_W, DOCK_H],
            "hole_pitch": [87.0, 65.0],
            "origin_in_case": [DOCK_X, DOCK_Y],
        },
        "printability": {
            "orientation": "all STL files are delivered in intended print orientation",
            "support": "none",
            "rear_access_frame": "open rear flange on bed; vertical walls and no roof",
            "rear_service_cap": "rear lattice face on bed; vertical walls and two 40-degree detents",
            "dock_tray": "flat tray face on bed; open FPC guide has no roof",
            "maximum_designed_bridge": 0.0,
        },
        "viewer_references": {
            "complete_assembly_43": "Tang_Primer_20K_Case_R4_Complete_Assembly_43.stl",
            "complete_assembly_50": "Tang_Primer_20K_Case_R4_Complete_Assembly_50.stl",
            "printable": False,
            "note": "contains LCD, Dock/Core envelope, screws, access frame and service cap; FPC omitted",
        },
        "lcd": {key: asdict(value) for key, value in LCDS.items()},
        "files": stats,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return stats


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("output/release"))
    args = parser.parse_args(argv)
    for item in generate(args.out):
        print(f"{item['file']}: {item['triangles']} triangles, {item['min_mm']} .. {item['max_mm']} mm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
