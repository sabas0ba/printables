#!/usr/bin/env python3
"""Shared transforms for the R4 assembled enclosure coordinate system.

Assembly axes are X=width, Y=height and Z=front-to-rear.  The front display
surface is Z=0.  The official Dock STEP is positioned with its PCB bottom at
the four tray supports; it already contains the installed Tang Primer Core.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from generate_case import BEZEL_T, CASE_H, CASE_W, DOCK_HOLES, DOCK_X, DOCK_Y, FRONT_DEPTH, LCDS, TRAY_T
from generate_case_r4 import (
    ASSEMBLY_HOLES, CASE_DEPTH, DOCK_PCB_T_NOMINAL, DOCK_STANDOFF_H,
    PIN_HEAD, PIN_HEAD_T, PIN_TIP, SERVICE_CAP_DEPTH, STRUCTURAL_DEPTH,
)


Vec3 = tuple[float, float, float]
Triangle = tuple[Vec3, Vec3, Vec3]
DOCK_STEP_OFFSET = (DOCK_X, DOCK_Y, BEZEL_T + FRONT_DEPTH + TRAY_T + DOCK_STANDOFF_H)

# Exact placement found in Sipeed's Dock 3713 STEP.  Applying this translation
# to the standalone Core 3690 STEP reproduces the installed Core in that file.
CORE_IN_DOCK_STEP_OFFSET = (48.299, 36.344, 4.180)
CORE_IN_CASE_STEP_OFFSET = tuple(DOCK_STEP_OFFSET[i] + CORE_IN_DOCK_STEP_OFFSET[i] for i in range(3))

# Exact overall bounds measured from the official STEP assemblies.
DOCK_STEP_BOUNDS_LOCAL = (
    (-0.025449679972397363, -2.725449679975399, -1.5854496799724342),
    (98.15544967997243, 73.6654496799724, 15.165449679976817),
)
CORE_STEP_BOUNDS_LOCAL = (
    (-33.806519535640085, -15.006519535640086, -1.656519535640087),
    (33.8065195356407, 15.241517535640144, 3.811519535640104),
)


# Both names contain "Official Dock"; the drawing and render code selects the
# Dock part by that substring.
DOCK_MESH_PART = "Official Dock 3713 + installed Core 3690"
DOCK_ENVELOPE_PART = "Official Dock 3713 + Core 3690 envelope"


@dataclass(frozen=True)
class Part:
    name: str
    triangles: list[Triangle]
    color: str
    alpha: float


def read_binary_stl(path: Path) -> list[Triangle]:
    data = path.read_bytes()
    if len(data) < 84:
        raise ValueError(f"{path}: truncated STL")
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + count * 50:
        raise ValueError(f"{path}: expected {count} binary triangles")
    triangles: list[Triangle] = []
    offset = 84
    for _ in range(count):
        values = struct.unpack_from("<12fH", data, offset)
        triangles.append((values[3:6], values[6:9], values[9:12]))
        offset += 50
    return triangles


def transform(triangles: Iterable[Triangle], fn: Callable[[Vec3], Vec3], reflected: bool = False) -> list[Triangle]:
    result: list[Triangle] = []
    for tri in triangles:
        points = tuple(fn(point) for point in tri)
        if reflected:
            points = (points[0], points[2], points[1])
        result.append(points)  # type: ignore[arg-type]
    return result


def translate(triangles: Iterable[Triangle], dx: float, dy: float, dz: float) -> list[Triangle]:
    return transform(triangles, lambda p: (p[0] + dx, p[1] + dy, p[2] + dz))


def box_triangles(x: float, y: float, z: float, w: float, h: float, d: float) -> list[Triangle]:
    p = [
        (x, y, z), (x + w, y, z), (x + w, y + h, z), (x, y + h, z),
        (x, y, z + d), (x + w, y, z + d), (x + w, y + h, z + d), (x, y + h, z + d),
    ]
    faces = (
        (0, 2, 1), (0, 3, 2), (4, 5, 6), (4, 6, 7),
        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7),
    )
    return [(p[a], p[b], p[c]) for a, b, c in faces]


def cylinder_triangles(cx: float, cy: float, z0: float, z1: float,
                       radius: float, segments: int = 24) -> list[Triangle]:
    """Faceted reference cylinder with its axis on Z."""
    import math

    triangles: list[Triangle] = []
    for i in range(segments):
        a0 = 2.0 * math.pi * i / segments
        a1 = 2.0 * math.pi * (i + 1) / segments
        p0 = (cx + radius * math.cos(a0), cy + radius * math.sin(a0), z0)
        p1 = (cx + radius * math.cos(a1), cy + radius * math.sin(a1), z0)
        q0 = (p0[0], p0[1], z1)
        q1 = (p1[0], p1[1], z1)
        triangles.extend([
            ((cx, cy, z0), p1, p0), ((cx, cy, z1), q0, q1),
            (p0, p1, q1), (p0, q1, q0),
        ])
    return triangles


def dock_envelope_triangles() -> list[Triangle]:
    """Box with the overall bounds of the official Dock STEP, in its local frame.

    The STEP-derived Dock mesh is not distributed with this design, so the
    assembly references show the Dock and the installed Core as this box.
    """
    lower, upper = DOCK_STEP_BOUNDS_LOCAL
    return box_triangles(*lower, *(upper[i] - lower[i] for i in range(3)))


def assembled_parts(input_dir: Path, dock_step_stl: Path | None, spec_key: str) -> list[Part]:
    """Place every modeled part; ``dock_step_stl=None`` selects the Dock envelope box."""
    if spec_key not in LCDS:
        raise ValueError(f"unknown LCD key: {spec_key}")
    spec = LCDS[spec_key]
    front = read_binary_stl(input_dir / f"front_shell_{spec_key}_snap.stl")
    retainer = translate(
        read_binary_stl(input_dir / f"lcd_retainer_{spec_key}_snap.stl"),
        0, 0, BEZEL_T + spec.module_t,
    )
    tray = translate(
        read_binary_stl(input_dir / "dock_tray_screw_common.stl"),
        0, 0, BEZEL_T + FRONT_DEPTH,
    )
    rear_frame = transform(
        read_binary_stl(input_dir / "rear_access_frame_common.stl"),
        lambda p: (p[0], p[1], STRUCTURAL_DEPTH - p[2]),
        reflected=True,
    )
    service_cap = transform(
        read_binary_stl(input_dir / "rear_service_cap_common.stl"),
        lambda p: (p[0], p[1], CASE_DEPTH - p[2]),
        reflected=True,
    )
    if dock_step_stl is None:
        dock_name = DOCK_ENVELOPE_PART
        dock = translate(dock_envelope_triangles(), *DOCK_STEP_OFFSET)
    else:
        dock_name = DOCK_MESH_PART
        dock = translate(read_binary_stl(dock_step_stl), *DOCK_STEP_OFFSET)
    lcd_x = (CASE_W - spec.module_w) / 2.0
    lcd_y = (CASE_H - spec.module_h) / 2.0
    lcd = box_triangles(lcd_x, lcd_y, BEZEL_T, spec.module_w, spec.module_h, spec.module_t)
    pin_source = read_binary_stl(input_dir / "case_snap_pin.stl")
    pins: list[Triangle] = []
    for hole_x, hole_y in ASSEMBLY_HOLES:
        pins.extend(transform(
            pin_source,
            lambda p, hx=hole_x, hy=hole_y: (
                hx + p[1] - PIN_HEAD / 2.0,
                hy + p[2] - PIN_HEAD / 2.0,
                p[0] - PIN_HEAD_T,
            ),
        ))
    screws: list[Triangle] = []
    pcb_bottom = DOCK_STEP_OFFSET[2]
    pcb_top = pcb_bottom + DOCK_PCB_T_NOMINAL
    for hole_x, hole_y in DOCK_HOLES:
        screws.extend(cylinder_triangles(hole_x, hole_y, pcb_top - 6.0, pcb_top, 1.25))
        screws.extend(cylinder_triangles(hole_x, hole_y, pcb_top, pcb_top + 1.70, 2.50))
    return [
        Part("Front shell", front, "#6b7785", 0.20),
        Part(f"{spec_key[0]}.{spec_key[1]}-inch LCD", lcd, "#3b8ed0", 0.88),
        Part("LCD retainer", retainer, "#9aa4ae", 0.34),
        Part("Dock tray", tray, "#8b70c9", 0.42),
        Part(dock_name, dock, "#2f9b63", 0.88),
        Part("4 x M2.5 x 6 pan-head screws", screws, "#58616b", 0.95),
        Part("Rear access frame", rear_frame, "#6b7785", 0.20),
        Part("Rear service cap", service_cap, "#4f6476", 0.14),
        Part("4 snap pins", pins, "#e27b2d", 0.92),
    ]


def exploded_parts(parts: list[Part]) -> list[Part]:
    offsets = {
        "Front shell": -26.0,
        "LCD retainer": 5.0,
        "Dock tray": 17.0,
        DOCK_MESH_PART: 29.0,
        DOCK_ENVELOPE_PART: 29.0,
        "4 x M2.5 x 6 pan-head screws": 34.0,
        "Rear access frame": 47.0,
        "Rear service cap": 65.0,
        "4 snap pins": -26.0,
    }
    result: list[Part] = []
    for part in parts:
        if "inch LCD" in part.name:
            dz = -9.0
        else:
            dz = offsets.get(part.name, 0.0)
        result.append(Part(part.name, translate(part.triangles, 0, 0, dz), part.color, max(part.alpha, 0.62)))
    return result


def bounds(triangles: Iterable[Triangle]) -> tuple[Vec3, Vec3]:
    points = [p for tri in triangles for p in tri]
    return (
        tuple(min(p[i] for p in points) for i in range(3)),
        tuple(max(p[i] for p in points) for i in range(3)),
    )  # type: ignore[return-value]


def section_segments(triangles: Iterable[Triangle], axis: int, value: float, tolerance: float = 1e-8):
    """Intersect triangles with an axis-aligned plane and return 3D segments."""
    segments: list[tuple[Vec3, Vec3]] = []
    for tri in triangles:
        hits: list[Vec3] = []
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            da, db = a[axis] - value, b[axis] - value
            if abs(da) <= tolerance and abs(db) <= tolerance:
                continue
            if (da <= 0 <= db) or (db <= 0 <= da):
                if abs(db - da) <= tolerance:
                    continue
                t = -da / (db - da)
                if -tolerance <= t <= 1 + tolerance:
                    point = tuple(a[i] + t * (b[i] - a[i]) for i in range(3))
                    if not any(sum((point[i] - old[i]) ** 2 for i in range(3)) < 1e-12 for old in hits):
                        hits.append(point)  # type: ignore[arg-type]
        if len(hits) == 2:
            segments.append((hits[0], hits[1]))
    return segments


def official_global_bounds(local_bounds: tuple[Vec3, Vec3], offset: Vec3) -> tuple[Vec3, Vec3]:
    return tuple(tuple(local_bounds[j][i] + offset[i] for i in range(3)) for j in range(2))  # type: ignore[return-value]
