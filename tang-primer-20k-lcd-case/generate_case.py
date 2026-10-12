#!/usr/bin/env python3
"""Generate a printable Tang Primer 20K Dock + RGB LCD enclosure.

The generator intentionally uses only the Python standard library.  Each STL
contains a small set of closed, intersecting shells.  Modern slicers merge the
shells during slicing, which avoids depending on a CAD/CSG kernel.
"""

from __future__ import annotations

import argparse
import json
import math
import struct
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence


Vec3 = tuple[float, float, float]
Triangle = tuple[Vec3, Vec3, Vec3]


@dataclass(frozen=True)
class LcdSpec:
    key: str
    module_w: float
    module_h: float
    module_t: float
    window_w: float
    window_h: float
    window_offset_y: float
    retainer_t: float


LCDS = {
    "43": LcdSpec(
        key="43",
        module_w=105.40,
        module_h=67.10,
        module_t=2.90,
        window_w=97.00,
        window_h=55.00,
        window_offset_y=2.45,
        retainer_t=4.00,
    ),
    "50": LcdSpec(
        key="50",
        module_w=120.70,
        module_h=75.90,
        module_t=3.05,
        window_w=110.00,
        window_h=66.00,
        window_offset_y=2.20,
        retainer_t=3.85,
    ),
}


CASE_W = 140.0
CASE_H = 112.0
BEZEL_T = 2.40
FRONT_DEPTH = 7.00
WALL = 2.40
TRAY_T = 2.40
REAR_DEPTH = 18.0
ASSEMBLY_HOLES = ((5.0, 5.0), (135.0, 5.0), (5.0, 107.0), (135.0, 107.0))

DOCK_W = 95.0
DOCK_H = 73.0
DOCK_X = (CASE_W - DOCK_W) / 2.0
DOCK_Y = 14.5
DOCK_HOLES = (
    (DOCK_X + 4.0, DOCK_Y + 4.0),
    (DOCK_X + 91.0, DOCK_Y + 4.0),
    (DOCK_X + 4.0, DOCK_Y + 69.0),
    (DOCK_X + 91.0, DOCK_Y + 69.0),
)


class Mesh:
    def __init__(self, name: str) -> None:
        self.name = name
        self.triangles: list[Triangle] = []

    def tri(self, a: Vec3, b: Vec3, c: Vec3) -> None:
        self.triangles.append((a, b, c))

    def box(self, x: float, y: float, z: float, w: float, h: float, d: float) -> None:
        if min(w, h, d) <= 0:
            return
        p = [
            (x, y, z),
            (x + w, y, z),
            (x + w, y + h, z),
            (x, y + h, z),
            (x, y, z + d),
            (x + w, y, z + d),
            (x + w, y + h, z + d),
            (x, y + h, z + d),
        ]
        faces = (
            (0, 2, 1), (0, 3, 2),
            (4, 5, 6), (4, 6, 7),
            (0, 1, 5), (0, 5, 4),
            (1, 2, 6), (1, 6, 5),
            (2, 3, 7), (2, 7, 6),
            (3, 0, 4), (3, 4, 7),
        )
        for i, j, k in faces:
            self.tri(p[i], p[j], p[k])

    def extruded_rect_union(
        self,
        rectangles: Sequence[tuple[float, float, float, float]],
        z: float,
        depth: float,
    ) -> None:
        """Extrude the geometric union of axis-aligned XY rectangles."""
        if depth <= 0:
            raise ValueError("extrusion depth must be positive")
        valid = [(x, y, w, h) for x, y, w, h in rectangles if w > 0 and h > 0]
        if not valid:
            raise ValueError("rectangle union must contain positive-area geometry")

        xs = sorted({value for x, _, w, _ in valid for value in (x, x + w)})
        ys = sorted({value for _, y, _, h in valid for value in (y, y + h)})
        occupied = {
            (xi, yi)
            for xi, (x1, x2) in enumerate(zip(xs, xs[1:]))
            for yi, (y1, y2) in enumerate(zip(ys, ys[1:]))
            if any(
                x <= (x1 + x2) / 2.0 <= x + w
                and y <= (y1 + y2) / 2.0 <= y + h
                for x, y, w, h in valid
            )
        }

        pending = set(occupied)
        components = 0
        while pending:
            components += 1
            stack = [pending.pop()]
            while stack:
                xi, yi = stack.pop()
                for neighbor in ((xi - 1, yi), (xi + 1, yi), (xi, yi - 1), (xi, yi + 1)):
                    if neighbor in pending:
                        pending.remove(neighbor)
                        stack.append(neighbor)
        if components != 1:
            raise ValueError(f"rectangle union contains {components} separate parts")

        top = z + depth
        for xi, yi in sorted(occupied):
            x1, x2 = xs[xi], xs[xi + 1]
            y1, y2 = ys[yi], ys[yi + 1]
            bottom_points = (
                (x1, y1, z), (x2, y1, z), (x2, y2, z), (x1, y2, z),
            )
            top_points = tuple((x, y, top) for x, y, _ in bottom_points)
            self.tri(bottom_points[0], bottom_points[2], bottom_points[1])
            self.tri(bottom_points[0], bottom_points[3], bottom_points[2])
            self.tri(top_points[0], top_points[1], top_points[2])
            self.tri(top_points[0], top_points[2], top_points[3])

            if (xi - 1, yi) not in occupied:
                self.tri(bottom_points[0], top_points[0], top_points[3])
                self.tri(bottom_points[0], top_points[3], bottom_points[3])
            if (xi + 1, yi) not in occupied:
                self.tri(bottom_points[1], bottom_points[2], top_points[2])
                self.tri(bottom_points[1], top_points[2], top_points[1])
            if (xi, yi - 1) not in occupied:
                self.tri(bottom_points[0], bottom_points[1], top_points[1])
                self.tri(bottom_points[0], top_points[1], top_points[0])
            if (xi, yi + 1) not in occupied:
                self.tri(bottom_points[3], top_points[3], top_points[2])
                self.tri(bottom_points[3], top_points[2], bottom_points[2])

    def ring(
        self,
        cx: float,
        cy: float,
        z: float,
        outer_r: float,
        inner_r: float,
        depth: float,
        segments: int = 48,
    ) -> None:
        if not (outer_r > inner_r > 0 and depth > 0):
            raise ValueError("invalid ring dimensions")
        for i in range(segments):
            a0 = 2.0 * math.pi * i / segments
            a1 = 2.0 * math.pi * (i + 1) / segments
            ob0 = (cx + outer_r * math.cos(a0), cy + outer_r * math.sin(a0), z)
            ob1 = (cx + outer_r * math.cos(a1), cy + outer_r * math.sin(a1), z)
            ot0 = (ob0[0], ob0[1], z + depth)
            ot1 = (ob1[0], ob1[1], z + depth)
            ib0 = (cx + inner_r * math.cos(a0), cy + inner_r * math.sin(a0), z)
            ib1 = (cx + inner_r * math.cos(a1), cy + inner_r * math.sin(a1), z)
            it0 = (ib0[0], ib0[1], z + depth)
            it1 = (ib1[0], ib1[1], z + depth)
            self.tri(ob0, ob1, ot1)
            self.tri(ob0, ot1, ot0)
            self.tri(ib0, it1, ib1)
            self.tri(ib0, it0, it1)
            self.tri(ot0, ot1, it1)
            self.tri(ot0, it1, it0)
            self.tri(ob0, ib1, ob1)
            self.tri(ob0, ib0, ib1)

    def frame(
        self,
        outer_x: float,
        outer_y: float,
        outer_w: float,
        outer_h: float,
        inner_x: float,
        inner_y: float,
        inner_w: float,
        inner_h: float,
        z: float,
        depth: float,
    ) -> None:
        self.box(outer_x, outer_y, z, outer_w, inner_y - outer_y, depth)
        self.box(outer_x, inner_y + inner_h, z, outer_w,
                 outer_y + outer_h - (inner_y + inner_h), depth)
        self.box(outer_x, inner_y, z, inner_x - outer_x, inner_h, depth)
        self.box(inner_x + inner_w, inner_y, z,
                 outer_x + outer_w - (inner_x + inner_w), inner_h, depth)

    def bounds(self) -> tuple[Vec3, Vec3]:
        points = [p for tri in self.triangles for p in tri]
        return (
            tuple(min(p[i] for p in points) for i in range(3)),
            tuple(max(p[i] for p in points) for i in range(3)),
        )  # type: ignore[return-value]

    def validate(self) -> None:
        if not self.triangles:
            raise ValueError(f"{self.name}: empty mesh")
        for index, (a, b, c) in enumerate(self.triangles):
            ux, uy, uz = (b[i] - a[i] for i in range(3))
            vx, vy, vz = (c[i] - a[i] for i in range(3))
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            if nx * nx + ny * ny + nz * nz < 1e-12:
                raise ValueError(f"{self.name}: degenerate triangle {index}")
            if not all(math.isfinite(v) for p in (a, b, c) for v in p):
                raise ValueError(f"{self.name}: non-finite coordinate")

    def write_stl(self, path: Path) -> None:
        self.validate()
        header = f"Tang Primer 20K case: {self.name}".encode("ascii")[:80].ljust(80, b"\0")
        with path.open("wb") as stream:
            stream.write(header)
            stream.write(struct.pack("<I", len(self.triangles)))
            for a, b, c in self.triangles:
                ux, uy, uz = (b[i] - a[i] for i in range(3))
                vx, vy, vz = (c[i] - a[i] for i in range(3))
                nx = uy * vz - uz * vy
                ny = uz * vx - ux * vz
                nz = ux * vy - uy * vx
                length = math.sqrt(nx * nx + ny * ny + nz * nz)
                normal = (nx / length, ny / length, nz / length)
                stream.write(struct.pack("<12fH", *(normal + a + b + c), 0))


def add_slotted_bezel_plate(mesh: Mesh, spec: LcdSpec) -> None:
    cx = CASE_W / 2.0
    cy = CASE_H / 2.0 + spec.window_offset_y
    ix = cx - spec.window_w / 2.0
    iy = cy - spec.window_h / 2.0
    mesh.frame(0, 0, CASE_W, CASE_H, ix, iy, spec.window_w, spec.window_h, 0, BEZEL_T)


def add_lcd_locators(mesh: Mesh, spec: LcdSpec) -> None:
    clearance = 0.50
    pocket_w = spec.module_w + clearance
    pocket_h = spec.module_h + clearance
    x = (CASE_W - pocket_w) / 2.0
    y = (CASE_H - pocket_h) / 2.0
    rail = 1.25
    height = 3.60
    z = BEZEL_T
    mesh.box(x - rail, y, z, rail, pocket_h, height)
    mesh.box(x + pocket_w, y, z, rail, pocket_h, height)
    mesh.box(x - rail, y + pocket_h, z, pocket_w + 2 * rail, rail, height)
    fpc_gap = 80.0
    left_end = CASE_W / 2.0 - fpc_gap / 2.0
    right_start = CASE_W / 2.0 + fpc_gap / 2.0
    mesh.box(x - rail, y - rail, z, max(0.0, left_end - (x - rail)), rail, height)
    mesh.box(right_start, y - rail, z, max(0.0, x + pocket_w + rail - right_start), rail, height)


def build_front_shell(spec: LcdSpec) -> Mesh:
    mesh = Mesh(f"front_shell_{spec.key}")
    add_slotted_bezel_plate(mesh, spec)
    add_lcd_locators(mesh, spec)
    z = BEZEL_T
    mesh.box(0, 0, z, WALL, CASE_H, FRONT_DEPTH)
    mesh.box(CASE_W - WALL, 0, z, WALL, CASE_H, FRONT_DEPTH)
    mesh.box(WALL, 0, z, CASE_W - 2 * WALL, WALL, FRONT_DEPTH)
    mesh.box(WALL, CASE_H - WALL, z, CASE_W - 2 * WALL, WALL, FRONT_DEPTH)
    for x, y in ASSEMBLY_HOLES:
        # 4.1 mm pilot for a typical M3 heat-set insert with 4.6 mm OD.
        mesh.ring(x, y, z, 4.0, 2.05, FRONT_DEPTH, segments=56)
    return mesh


def add_open_bottom_ring(
    mesh: Mesh,
    outer_w: float,
    outer_h: float,
    inner_w: float,
    inner_h: float,
    z: float,
    depth: float,
    gap_w: float,
) -> None:
    ox = (CASE_W - outer_w) / 2.0
    oy = (CASE_H - outer_h) / 2.0
    ix = (CASE_W - inner_w) / 2.0
    iy = (CASE_H - inner_h) / 2.0
    mesh.box(ox, iy + inner_h, z, outer_w, oy + outer_h - (iy + inner_h), depth)
    mesh.box(ox, iy, z, ix - ox, inner_h, depth)
    mesh.box(ix + inner_w, iy, z, ox + outer_w - (ix + inner_w), inner_h, depth)
    gap_left = CASE_W / 2.0 - gap_w / 2.0
    gap_right = CASE_W / 2.0 + gap_w / 2.0
    mesh.box(ox, oy, z, max(0.0, gap_left - ox), iy - oy, depth)
    mesh.box(gap_right, oy, z, max(0.0, ox + outer_w - gap_right), iy - oy, depth)


def build_retainer(spec: LcdSpec) -> Mesh:
    mesh = Mesh(f"lcd_retainer_{spec.key}")
    clearance = 0.30
    inner_w = spec.module_w - 5.0
    inner_h = spec.module_h - 5.0
    add_open_bottom_ring(
        mesh,
        spec.module_w + clearance,
        spec.module_h + clearance,
        inner_w,
        inner_h,
        0,
        spec.retainer_t,
        80.0,
    )
    # Common outer pressure ring.  Four spokes transfer tray pressure to the
    # LCD-edge ring without filling the whole aperture with plastic.
    mesh.frame(4.0, 4.0, 132.0, 84.0, 8.0, 8.0, 124.0, 76.0, 0, spec.retainer_t)
    panel_outer_x = (CASE_W - (spec.module_w + clearance)) / 2.0
    panel_outer_y = (CASE_H - (spec.module_h + clearance)) / 2.0
    mesh.box(6.0, CASE_H / 2.0 - 3.0, 0,
             panel_outer_x - 6.0 + 1.0, 6.0, spec.retainer_t)
    mesh.box(panel_outer_x + spec.module_w + clearance - 1.0,
             CASE_H / 2.0 - 3.0, 0,
             134.0 - (panel_outer_x + spec.module_w + clearance - 1.0),
             6.0, spec.retainer_t)
    mesh.box(CASE_W / 2.0 - 3.0, 6.0, 0, 6.0,
             panel_outer_y - 6.0 + 1.0, spec.retainer_t)
    mesh.box(CASE_W / 2.0 - 3.0,
             panel_outer_y + spec.module_h + clearance - 1.0, 0, 6.0,
             86.0 - (panel_outer_y + spec.module_h + clearance - 1.0),
             spec.retainer_t)
    return mesh


def build_dock_tray() -> Mesh:
    mesh = Mesh("dock_tray_common")
    edge = 3.0
    mesh.frame(0, 0, CASE_W, CASE_H, edge, edge,
               CASE_W - 2 * edge, CASE_H - 2 * edge, 0, TRAY_T)
    for x, y in ASSEMBLY_HOLES:
        mesh.ring(x, y, 0, 4.0, 1.70, TRAY_T, segments=56)
    lower_y = DOCK_HOLES[0][1]
    upper_y = DOCK_HOLES[2][1]
    bar_h = 5.0
    # Lower bar is split to leave an 80 mm-wide RGB FPC routing window.
    mesh.box(edge, lower_y - bar_h / 2.0, 0, 27.5, bar_h, TRAY_T)
    mesh.box(109.5, lower_y - bar_h / 2.0, 0,
             CASE_W - edge - 109.5, bar_h, TRAY_T)
    mesh.box(edge, upper_y - bar_h / 2.0, 0,
             CASE_W - 2 * edge, bar_h, TRAY_T)
    for x, y in DOCK_HOLES:
        mesh.ring(x, y, TRAY_T, 4.0, 1.05, 3.20, segments=48)
    return mesh


def add_rear_face(mesh: Mesh) -> None:
    edge = 3.0
    mesh.frame(0, 0, CASE_W, CASE_H, edge, edge,
               CASE_W - 2 * edge, CASE_H - 2 * edge, 0, WALL)
    for x, y in ASSEMBLY_HOLES:
        mesh.ring(x, y, 0, 4.0, 1.70, WALL, segments=56)
    # Vent bars.  Gaps at x=26..37 and x=108..120 expose the button and
    # switch columns shown on the Dock 3713 dimensional drawing.
    for y in (16.0, 24.0, 32.0, 40.0, 48.0, 56.0, 64.0, 72.0):
        mesh.box(10.0, y, 0, 16.0, 2.0, WALL)
        mesh.box(37.0, y, 0, 71.0, 2.0, WALL)
        mesh.box(120.0, y, 0, 10.0, 2.0, WALL)
    mesh.box(68.5, 8.0, 0, 3.0, 76.0, WALL)


def build_rear_cover() -> Mesh:
    mesh = Mesh("rear_cover_common")
    add_rear_face(mesh)
    z = WALL
    mesh.box(0, 0, z, WALL, CASE_H, REAR_DEPTH - WALL)
    mesh.box(CASE_W - WALL, 0, z, WALL, CASE_H, REAR_DEPTH - WALL)
    mesh.box(WALL, CASE_H - WALL, z,
             CASE_W - 2 * WALL, WALL, REAR_DEPTH - WALL)
    # Bottom connector bay: DC, Ethernet, USB-OTG and USB-JTAG remain exposed.
    mesh.box(WALL, 0, z, 15.6, WALL, REAR_DEPTH - WALL)
    mesh.box(122.0, 0, z, CASE_W - WALL - 122.0, WALL, REAR_DEPTH - WALL)
    for x, y in ASSEMBLY_HOLES:
        mesh.ring(x, y, 0, 4.0, 1.70, REAR_DEPTH, segments=56)
    return mesh


def stl_stats(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"{path.name}: truncated STL")
    count = struct.unpack_from("<I", data, 80)[0]
    expected = 84 + count * 50
    if len(data) != expected:
        raise ValueError(f"{path.name}: STL size mismatch")
    mins = [float("inf")] * 3
    maxs = [float("-inf")] * 3
    offset = 84
    for _ in range(count):
        values = struct.unpack_from("<12fH", data, offset)
        for base in (3, 6, 9):
            for axis in range(3):
                value = values[base + axis]
                mins[axis] = min(mins[axis], value)
                maxs[axis] = max(maxs[axis], value)
        offset += 50
    return {
        "file": path.name,
        "triangles": count,
        "size_bytes": len(data),
        "min_mm": [round(v, 3) for v in mins],
        "max_mm": [round(v, 3) for v in maxs],
    }


def generate(out_dir: Path) -> list[dict[str, object]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    meshes = [
        build_front_shell(LCDS["43"]),
        build_retainer(LCDS["43"]),
        build_front_shell(LCDS["50"]),
        build_retainer(LCDS["50"]),
        build_dock_tray(),
        build_rear_cover(),
    ]
    stats: list[dict[str, object]] = []
    for mesh in meshes:
        path = out_dir / f"{mesh.name}.stl"
        mesh.write_stl(path)
        stats.append(stl_stats(path))
    manifest = {
        "design": "Tang Primer 20K Dock + Sipeed RGB LCD enclosure",
        "units": "mm",
        "case": {
            "width": CASE_W,
            "height": CASE_H,
            "assembled_depth_nominal": BEZEL_T + FRONT_DEPTH + TRAY_T + REAR_DEPTH,
        },
        "dock": {
            "pcb": [DOCK_W, DOCK_H],
            "hole_pitch": [87.0, 65.0],
            "mounting": "M2.5 x 4; 2.1 mm printed pilot holes",
        },
        "lcd": {key: asdict(value) for key, value in LCDS.items()},
        "assembly": "M3 x 25 mm x4 plus M3 heat-set inserts (OD <= 4.6 mm)",
        "files": stats,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return stats


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("output"))
    args = parser.parse_args(argv)
    stats = generate(args.out)
    for item in stats:
        print(
            f"{item['file']}: {item['triangles']} triangles, "
            f"{item['min_mm']} .. {item['max_mm']} mm"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
