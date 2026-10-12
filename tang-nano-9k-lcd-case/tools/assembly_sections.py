#!/usr/bin/env python3
"""Exact 2-D assembly sections derived from the rectilinear STL solids."""

from __future__ import annotations

import itertools
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Iterable, Literal

from tools import generate_stl as model
from tools.profiles import CaseProfile


Plane = Literal["x", "y"]


@dataclass(frozen=True)
class SectionPart:
    name: str
    solid: model.RectilinearSolid
    fill_key: str


@dataclass(frozen=True)
class SectionDefinition:
    code: str
    plane: Plane
    coordinate: float
    title: str
    purpose: str


def section_definitions(profile: CaseProfile) -> tuple[SectionDefinition, ...]:
    """Return cutting planes positioned on the profile's actual features."""
    retainer_hook_y = profile.retainer_y + profile.retainer_hook_centres[0]
    return (
        SectionDefinition(
            "A-A", "x", profile.pcb_x + profile.section_a_offset,
            "LONGITUDINAL Y-Z SECTION",
            "USB-C / HDMI, PCB end stop, LCD, FPC route and rear cover",
        ),
        SectionDefinition(
            "B-B", "y", profile.pcb_y + 19.50, "PCB RETENTION X-Z SECTION",
            "fixed lip, support shelf, PCB and flexible clip",
        ),
        SectionDefinition(
            "C-C", "y", retainer_hook_y, "LCD HOOK X-Z SECTION",
            "retainer cantilevers, stepped heads and chassis windows",
        ),
        SectionDefinition(
            "D-D", "y", profile.pcb_y + model.PCB_H / 2.0,
            "MICROSD SERVICE X-Z SECTION",
            "PCB underside, service aperture and rear clearance",
        ),
        SectionDefinition(
            "E-E", "y",
            profile.pcb_y + model.PCB_H - model.PCB_MOUNT_HOLE_EDGE_OFFSET,
            "HDMI-END M2 BOSS X-Z SECTION",
            "two HDMI-end mounting bosses, pilot bores, PCB and deep rear shell",
        ),
    )


def _box_transform(
    box: model.Box,
    *,
    dx: float = 0.0,
    dy: float = 0.0,
    z_map: Callable[[float], float] | None = None,
) -> model.Box:
    z_fn = z_map or (lambda value: value)
    z0, z1 = sorted((z_fn(box.z0), z_fn(box.z1)))
    return model.Box(box.x0 + dx, box.y0 + dy, z0, box.x1 + dx, box.y1 + dy, z1)


def transformed(
    source: model.RectilinearSolid,
    name: str,
    *,
    dx: float = 0.0,
    dy: float = 0.0,
    z_map: Callable[[float], float] | None = None,
) -> model.RectilinearSolid:
    result = model.RectilinearSolid(name)
    result.additions = [
        _box_transform(box, dx=dx, dy=dy, z_map=z_map)
        for box in source.additions
    ]
    result.subtractions = [
        _box_transform(box, dx=dx, dy=dy, z_map=z_map)
        for box in source.subtractions
    ]
    return result


def assembly_parts(
    profile: CaseProfile,
    panel_t: float = 2.0,
    rear_clearance: float = model.STANDARD_REAR_CLEARANCE,
) -> tuple[SectionPart, ...]:
    """Return all verified mechanical solids in assembled global coordinates."""
    retainer_z = model.retainer_assembly_z(profile)
    retainer = transformed(
        model.lcd_retainer(profile),
        "assembled-lcd-retainer",
        dx=profile.retainer_x,
        dy=profile.retainer_y,
        z_map=lambda value: retainer_z + value,
    )
    depth = model.overall_depth(rear_clearance)
    cover = transformed(
        model.rear_cover(profile, rear_clearance),
        "assembled-rear-cover",
        dx=profile.cover_x,
        dy=profile.cover_y,
        z_map=lambda value: depth - value,
    )
    return (
        SectionPart("Front chassis", model.front_chassis(profile, panel_t),
                    "chassis"),
        SectionPart("LCD reference body", model.lcd_proxy(profile), "lcd"),
        SectionPart("LCD retainer", retainer, "retainer"),
        SectionPart("Tang Nano 9K PCB", model.pcb_proxy(profile), "pcb"),
        SectionPart("Rear cover + carrier", cover, "cover"),
    )


def section_cells(
    solid: model.RectilinearSolid,
    plane: Plane,
    coordinate: float,
) -> list[tuple[float, float, float, float]]:
    """Return occupied section cells as (horizontal0, vertical0, w, h)."""
    boxes = solid.additions + solid.subtractions
    if plane == "x":
        crossing = [box for box in boxes if box.x0 < coordinate < box.x1]
        horizontal = sorted({value for box in crossing for value in (box.y0, box.y1)})
    elif plane == "y":
        crossing = [box for box in boxes if box.y0 < coordinate < box.y1]
        horizontal = sorted({value for box in crossing for value in (box.x0, box.x1)})
    else:
        raise ValueError(plane)
    vertical = sorted({value for box in crossing for value in (box.z0, box.z1)})
    if len(horizontal) < 2 or len(vertical) < 2:
        return []

    result: list[tuple[float, float, float, float]] = []
    for h0, h1 in zip(horizontal, horizontal[1:]):
        for v0, v1 in zip(vertical, vertical[1:]):
            hm, vm = (h0 + h1) / 2.0, (v0 + v1) / 2.0
            occupied = (
                solid.contains(coordinate, hm, vm)
                if plane == "x"
                else solid.contains(hm, coordinate, vm)
            )
            if occupied:
                result.append((h0, v0, h1 - h0, v1 - v0))
    return result


def section_by_code(profile: CaseProfile, code: str) -> SectionDefinition:
    return next(
        section for section in section_definitions(profile)
        if section.code == code
    )


def mechanical_cells(
    section: SectionDefinition,
    parts: Iterable[SectionPart],
) -> list[tuple[SectionPart, list[tuple[float, float, float, float]]]]:
    return [
        (part, section_cells(part.solid, section.plane, section.coordinate))
        for part in parts
    ]


@dataclass(frozen=True)
class Interference:
    first: str
    second: str
    box: model.Box

    @property
    def thickness(self) -> float:
        """Smallest overlap extent; contact preloads are only a few 0.01 mm."""
        return min(self.box.x1 - self.box.x0, self.box.y1 - self.box.y0,
                   self.box.z1 - self.box.z0)


def _bucket_keys(box: model.Box, size: float) -> Iterable[tuple[int, int, int]]:
    return itertools.product(
        range(int(box.x0 // size), int(box.x1 // size) + 1),
        range(int(box.y0 // size), int(box.y1 // size) + 1),
        range(int(box.z0 // size), int(box.z1 // size) + 1),
    )


def interferences(parts: Iterable[SectionPart],
                  bucket: float = 4.0) -> list[Interference]:
    """Return every volumetric overlap between two assembled parts."""
    cells = {part.name: part.solid.cells() for part in parts}
    found: list[Interference] = []
    for first, second in itertools.combinations(cells, 2):
        index: dict[tuple[int, int, int], list[model.Box]] = defaultdict(list)
        for box in cells[second]:
            for key in _bucket_keys(box, bucket):
                index[key].append(box)
        seen: set[tuple[model.Box, model.Box]] = set()
        for a in cells[first]:
            for key in _bucket_keys(a, bucket):
                for b in index.get(key, ()):
                    if (a, b) in seen:
                        continue
                    seen.add((a, b))
                    x0, x1 = max(a.x0, b.x0), min(a.x1, b.x1)
                    y0, y1 = max(a.y0, b.y0), min(a.y1, b.y1)
                    z0, z1 = max(a.z0, b.z0), min(a.z1, b.z1)
                    if x1 - x0 > 1e-6 and y1 - y0 > 1e-6 and z1 - z0 > 1e-6:
                        found.append(Interference(
                            first, second, model.Box(x0, y0, z0, x1, y1, z1)
                        ))
    return found
