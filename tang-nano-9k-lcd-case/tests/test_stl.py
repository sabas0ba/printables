#!/usr/bin/env python3
"""Structural checks for generated binary STL meshes."""

from __future__ import annotations

import math
import struct
import subprocess
import sys
import tempfile
import unittest
from collections import Counter, defaultdict, deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import generate_stl as model  # noqa: E402
from tools.assembly_sections import (  # noqa: E402
    assembly_parts,
    interferences,
    section_cells,
    section_definitions,
)
from tools.profiles import PROFILES  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def read_stl(path: Path):
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + count * 50:
        raise AssertionError(f"invalid STL byte count: {path}")
    triangles = []
    offset = 84
    for _ in range(count):
        values = struct.unpack_from("<12fH", data, offset)
        triangles.append((values[3:6], values[6:9], values[9:12]))
        offset += 50
    return triangles


def key(point):
    return tuple(round(value, 5) for value in point)


# Expected outer bounds per profile: (x0, x1, y0, y1, z0, z1).  These are
# literal values so that a change to a derived profile dimension is visible.
EXPECTED_BOUNDS = {
    "4p3in": {
        "front": (0.0, 118.0, 0.0, 81.0, 0.0, 27.0),
        "retainer": (-0.6, 108.2, 0.0, 70.6, 0.0, 6.5),
        "cover": (0.0, 111.6, 0.0, 74.6, 0.0, 11.2),
        "cover_20": (0.0, 111.6, 0.0, 74.6, 0.0, 24.2),
        "cover_30": (0.0, 111.6, 0.0, 74.6, 0.0, 34.2),
    },
    "5p0in": {
        "front": (0.0, 131.8, 0.0, 87.0, 0.0, 27.0),
        "retainer": (-0.6, 122.0, 0.0, 76.6, 0.0, 6.5),
        # The HDMI bulkhead free end at global z=14.6 is the highest feature.
        "cover": (0.0, 125.4, 0.0, 80.6, 0.0, 14.4),
        "cover_20": (0.0, 125.4, 0.0, 80.6, 0.0, 27.4),
        "cover_30": (0.0, 125.4, 0.0, 80.6, 0.0, 37.4),
    },
}


def mesh_bounds(triangles):
    points = [point for tri in triangles for point in tri]
    return tuple(
        value
        for axis in range(3)
        for value in (
            min(point[axis] for point in points),
            max(point[axis] for point in points),
        )
    )


def signed_volume(triangles):
    volume = 0.0
    for a, b, c in triangles:
        volume += (
            a[0] * (b[1] * c[2] - b[2] * c[1])
            - a[1] * (b[0] * c[2] - b[2] * c[0])
            + a[2] * (b[0] * c[1] - b[1] * c[0])
        ) / 6.0
    return volume


class GeneratedMeshes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory()
        cls.output = Path(cls.tempdir.name)
        subprocess.run(
            [sys.executable, str(ROOT / "tools/generate_stl.py"), "--output", str(cls.output)],
            check=True,
            stdout=subprocess.DEVNULL,
        )

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def check_mesh(self, path, expected_bounds):
        triangles = read_stl(path)
        self.assertGreater(len(triangles), 100)
        points = [point for tri in triangles for point in tri]
        self.assertTrue(all(math.isfinite(value) for point in points for value in point))

        for actual, expected in zip(mesh_bounds(triangles), expected_bounds):
            self.assertAlmostEqual(actual, expected, places=4)

        edges = Counter()
        edge_owners = defaultdict(list)
        for triangle_index, tri in enumerate(triangles):
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                edge = tuple(sorted((key(a), key(b))))
                edges[edge] += 1
                edge_owners[edge].append(triangle_index)
        self.assertEqual({count for count in edges.values()}, {2}, "mesh is not 2-manifold")

        # A manifold STL may still contain several closed shells.  Printing
        # services reject those as multiple parts even when they share one
        # file, so every print-ready STL must have exactly one shell.
        visited = {0}
        pending = deque([0])
        while pending:
            triangle_index = pending.popleft()
            tri = triangles[triangle_index]
            for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
                edge = tuple(sorted((key(a), key(b))))
                for neighbour in edge_owners[edge]:
                    if neighbour not in visited:
                        visited.add(neighbour)
                        pending.append(neighbour)
        self.assertEqual(
            len(visited), len(triangles),
            "mesh contains multiple disconnected printable parts",
        )
        self.assertGreater(signed_volume(triangles), 1.0)

    def test_every_profile_has_expected_bounds(self):
        self.assertEqual(set(EXPECTED_BOUNDS), set(PROFILES))

    def test_front_variants(self):
        for profile in PROFILES.values():
            for name in (
                "front_chassis_panel_1p5mm.stl",
                "front_chassis_panel_2p0mm.stl",
                "front_chassis_panel_3p0mm.stl",
            ):
                with self.subTest(profile=profile.key, name=name):
                    self.check_mesh(self.output / profile.key / name,
                                    EXPECTED_BOUNDS[profile.key]["front"])

    def test_lcd_retainer(self):
        for profile in PROFILES.values():
            with self.subTest(profile=profile.key):
                self.check_mesh(self.output / profile.key / "lcd_retainer.stl",
                                EXPECTED_BOUNDS[profile.key]["retainer"])

    def test_rear_covers(self):
        for profile in PROFILES.values():
            expected = EXPECTED_BOUNDS[profile.key]
            for name, bounds in (
                ("rear_cover.stl", expected["cover"]),
                ("rear_cover_clearance_20mm.stl", expected["cover_20"]),
                ("rear_cover_clearance_30mm.stl", expected["cover_30"]),
            ):
                with self.subTest(profile=profile.key, name=name):
                    self.check_mesh(self.output / profile.key / name, bounds)

    def test_rear_cover_stops_are_buttressed_to_the_rim(self):
        for profile in PROFILES.values():
            if profile.usb_bulkhead is not None:
                continue
            for clearance in (model.STANDARD_REAR_CLEARANCE,
                              *model.EXPANDED_REAR_CLEARANCES):
                cover = model.rear_cover(profile, clearance)
                board_x = (profile.cover_w - model.PCB_W) / 2.0
                board_y = (profile.cover_h - model.PCB_H) / 2.0
                support_z = 7.00 + model.overall_depth(clearance) - model.BODY_D
                for x in (board_x + 6.00, board_x + 20.00):
                    with self.subTest(profile=profile.key, clearance=clearance, x=x):
                        self.assertTrue(cover.contains(x, board_y - 0.40,
                                                       support_z - 0.50))
                        self.assertTrue(cover.contains(x, board_y + model.PCB_H + 0.40,
                                                       support_z - 0.50))

    def bulkhead_cases(self):
        for profile in PROFILES.values():
            if profile.usb_bulkhead is None:
                continue
            centre_x = profile.pcb_x + model.PCB_W / 2.0
            yield profile, centre_x, (
                (profile.usb_bulkhead, profile.usb_opening,
                 profile.pcb_y - model.PCB_AXIAL_CLEARANCE, -1.0),
                (profile.hdmi_bulkhead, profile.hdmi_opening,
                 profile.pcb_y + model.PCB_H + model.PCB_AXIAL_CLEARANCE, 1.0),
            )

    def test_bulkheads_stop_the_pcb_and_keep_the_notch_open(self):
        cases = list(self.bulkhead_cases())
        self.assertTrue(cases, "no profile uses rear-cover bulkheads")
        for profile, centre_x, ends in cases:
            for clearance in (model.STANDARD_REAR_CLEARANCE,
                              *model.EXPANDED_REAR_CLEARANCES):
                parts = {part.name: part.solid for part in assembly_parts(
                    profile, rear_clearance=clearance
                )}
                cover = parts["Rear cover + carrier"]
                pcb = parts["Tang Nano 9K PCB"]
                for bulkhead, _, stop_y, direction in ends:
                    cheek_x = centre_x + (bulkhead.notch.half_w + bulkhead.half_w) / 2.0
                    inside = stop_y + direction * 0.05
                    gap = stop_y - direction * 0.05
                    with self.subTest(profile=profile.key, clearance=clearance,
                                      direction=direction):
                        # Stop face at the PCB plane, 0.30 mm from the PCB end.
                        self.assertTrue(cover.contains(cheek_x, inside, 19.0))
                        self.assertFalse(cover.contains(cheek_x, gap, 19.0))
                        self.assertFalse(pcb.contains(cheek_x, gap, 19.0))
                        # Connector notch is open from the LCD side down to
                        # the compact-profile window bottom.
                        for z in (bulkhead.notch.z0 - 0.5, 19.0,
                                  bulkhead.notch.z1 - 0.05):
                            self.assertFalse(cover.contains(centre_x, inside, z))
                        self.assertTrue(cover.contains(
                            centre_x, inside, bulkhead.notch.z1 + 0.05))

    def test_cable_overmould_reaches_bulkhead(self):
        steps = 6
        for profile, centre_x, ends in self.bulkhead_cases():
            parts = assembly_parts(profile)
            for bulkhead, opening, stop_y, direction in ends:
                face_y = stop_y + direction * bulkhead.thickness
                if direction < 0:
                    y_range = (profile.body_y - 0.5, face_y - 0.05)
                else:
                    y_range = (face_y + 0.05, profile.body_y + profile.body_h + 0.5)
                blocked = []
                for i in range(steps + 1):
                    x = centre_x - opening.half_w + 0.05 + (
                        (opening.width - 0.1) * i / steps)
                    for j in range(steps + 1):
                        z = opening.z0 + 0.05 + (opening.height - 0.1) * j / steps
                        for k in range(steps + 1):
                            y = y_range[0] + (y_range[1] - y_range[0]) * k / steps
                            blocked.extend(
                                part.name for part in parts
                                if part.solid.contains(x, y, z)
                            )
                with self.subTest(profile=profile.key, direction=direction):
                    self.assertEqual(blocked, [])

    def test_rear_cover_has_explicit_hatch_cutouts(self):
        for profile in PROFILES.values():
            cover = model.rear_cover(profile)
            for x0 in profile.rear_hatch_xs:
                for y0 in profile.rear_hatch_ys:
                    with self.subTest(profile=profile.key, x=x0, y=y0):
                        self.assertFalse(cover.contains(
                            x0 + model.REAR_HATCH_SLOT_W / 2.0,
                            y0 + model.REAR_HATCH_SLOT_H / 2.0,
                            1.00,
                        ))

            # Webs between adjacent slots and the perimeter frame remain solid.
            x_web = profile.rear_hatch_xs[0] + model.REAR_HATCH_SLOT_W + 1.0
            y_mid = profile.rear_hatch_ys[0] + model.REAR_HATCH_SLOT_H / 2.0
            with self.subTest(profile=profile.key, web="x"):
                self.assertTrue(cover.contains(x_web, y_mid, 1.00))
                self.assertTrue(cover.contains(profile.rear_hatch_xs[0] - 3.0,
                                               y_mid, 1.00))

    def test_retainer_hook_capture_clearance(self):
        max_step = len(model.RETAINER_HOOK_PROJECTIONS) - 1
        for profile in PROFILES.values():
            window_z0, window_z1 = model.retainer_window_z(profile)
            head_z0 = (
                model.retainer_assembly_z(profile)
                + model.RETAINER_HOOK_STEP_Z0
                + max_step * model.RETAINER_HOOK_STEP_H
            )
            head_z1 = head_z0 + model.RETAINER_HOOK_STEP_H
            with self.subTest(profile=profile.key):
                self.assertAlmostEqual(head_z0 - window_z0, 0.10, places=4)
                self.assertAlmostEqual(window_z1 - head_z1, 0.10, places=4)

    def test_pcb_nominal_clearances(self):
        self.assertAlmostEqual(model.PCB_SIDE_CLEARANCE, 0.25, places=4)
        self.assertAlmostEqual(model.PCB_AXIAL_CLEARANCE, 0.30, places=4)

    def test_hdmi_end_m2_bosses(self):
        for profile in PROFILES.values():
            cover = model.rear_cover(profile, 20.0)
            board_x = (profile.cover_w - model.PCB_W) / 2.0
            board_y = (profile.cover_h - model.PCB_H) / 2.0
            support_z = 22.0
            hole_y = board_y + model.PCB_H - model.PCB_MOUNT_HOLE_EDGE_OFFSET
            for hole_x in (
                board_x + model.PCB_MOUNT_HOLE_EDGE_OFFSET,
                board_x + model.PCB_W - model.PCB_MOUNT_HOLE_EDGE_OFFSET,
            ):
                with self.subTest(profile=profile.key, hole_x=hole_x):
                    self.assertFalse(cover.contains(hole_x, hole_y, support_z - 1.0))
                    self.assertTrue(cover.contains(hole_x - 2.0, hole_y, support_z - 1.0))

    def test_deep_cover_preserves_pcb_plane(self):
        for profile in PROFILES.values():
            pcb_probe = (profile.pcb_x + model.PCB_W / 2.0,
                         profile.pcb_y + model.PCB_H / 2.0 - 0.5)
            # Solid web outside the first hatch slot, in global coordinates.
            plate_probe = (profile.cover_x + 6.8, profile.cover_y + 6.8)
            for clearance in model.EXPANDED_REAR_CLEARANCES:
                parts = {part.name: part.solid for part in assembly_parts(
                    profile, rear_clearance=clearance
                )}
                pcb = parts["Tang Nano 9K PCB"]
                cover = parts["Rear cover + carrier"]
                with self.subTest(profile=profile.key, clearance=clearance):
                    self.assertTrue(pcb.contains(*pcb_probe, 19.0))
                    inner_plate_z = 20.0 + clearance
                    self.assertTrue(cover.contains(*plate_probe, inner_plate_z + 1.0))
                    self.assertFalse(cover.contains(*plate_probe, inner_plate_z - 0.1))

    def test_assembled_parts_do_not_interfere(self):
        # The rear-cover latch bumps rest 0.05 mm into the lower edge of the
        # chassis windows as a seating preload.  Anything thicker is a
        # collision that prevents assembly.
        for profile in PROFILES.values():
            for clearance in (model.STANDARD_REAR_CLEARANCE,
                              *model.EXPANDED_REAR_CLEARANCES):
                hits = [
                    hit for hit in interferences(
                        assembly_parts(profile, rear_clearance=clearance)
                    )
                    if hit.thickness > 0.05 + 1e-6
                ]
                with self.subTest(profile=profile.key, clearance=clearance):
                    self.assertEqual(hits, [])

    def test_rear_latch_bumps_sit_in_chassis_windows(self):
        for profile in PROFILES.values():
            parts = {part.name: part.solid for part in assembly_parts(profile)}
            chassis = parts["Front chassis"]
            cover = parts["Rear cover + carrier"]
            bump_x = profile.body_x + model.WALL + 0.10
            for latch_y in profile.rear_latch_ys:
                y_mid = profile.body_y + latch_y + 3.0
                with self.subTest(profile=profile.key, latch_y=latch_y):
                    self.assertTrue(cover.contains(bump_x, y_mid, 24.0))
                    self.assertFalse(chassis.contains(bump_x, y_mid, 24.0))
                    for y_edge in (profile.body_y + latch_y + 0.05,
                                   profile.body_y + latch_y + 5.95):
                        self.assertTrue(cover.contains(bump_x, y_edge, 24.0))

    def test_rear_cover_seats_on_chassis_rear_edge(self):
        wall_end = model.BODY_D
        for profile in PROFILES.values():
            for clearance in (model.STANDARD_REAR_CLEARANCE,
                              *model.EXPANDED_REAR_CLEARANCES):
                parts = {part.name: part.solid for part in assembly_parts(
                    profile, rear_clearance=clearance
                )}
                chassis = parts["Front chassis"]
                cover = parts["Rear cover + carrier"]
                # The left wall carries a seat at 20 % of the cover height.
                x = profile.body_x + 0.50
                y = profile.cover_y + profile.cover_h * 0.2
                with self.subTest(profile=profile.key, clearance=clearance):
                    self.assertTrue(chassis.contains(x, y, wall_end - 0.05))
                    self.assertTrue(cover.contains(x, y, wall_end + 0.05))

    def test_assembly_reference_meshes(self):
        for profile in PROFILES.values():
            for clearance, overall_depth in ((20.0, 42.0), (30.0, 52.0)):
                path = (self.output / profile.key
                        / f"assembly_reference_clearance_{clearance:.0f}mm.stl")
                triangles = read_stl(path)
                points = [point for triangle in triangles for point in triangle]
                with self.subTest(profile=profile.key, clearance=clearance):
                    self.assertGreater(len(triangles), 10000)
                    self.assertTrue(all(
                        math.isfinite(value) for point in points for value in point
                    ))
                    expected = (0.0, profile.bezel_w, 0.0, profile.bezel_h,
                                0.0, overall_depth)
                    for actual, target in zip(mesh_bounds(triangles), expected):
                        self.assertAlmostEqual(actual, target, places=4)
                    self.assertGreater(signed_volume(triangles), 1.0)

    def test_exact_section_planes_cross_required_features(self):
        for profile in PROFILES.values():
            parts = {part.name: part.solid for part in assembly_parts(profile)}
            cover = parts["Rear cover + carrier"]
            retainer = parts["LCD retainer"]
            chassis = parts["Front chassis"]
            sections = {
                section.code: section for section in section_definitions(profile)
            }
            c_y = sections["C-C"].coordinate
            b_y = sections["B-B"].coordinate
            d_y = sections["D-D"].coordinate

            with self.subTest(profile=profile.key, section="C-C"):
                # C-C crosses a retainer hook head while the matching chassis
                # wall is absent at its engagement window.
                self.assertTrue(retainer.contains(profile.retainer_x - 0.40, c_y, 12.00))
                self.assertFalse(chassis.contains(profile.body_x + 1.00, c_y, 12.00))

            with self.subTest(profile=profile.key, section="B-B"):
                # B-B crosses the left fixed lip and the right flexible clip head.
                self.assertTrue(cover.contains(profile.pcb_x + 0.10, b_y, 18.10))
                self.assertTrue(cover.contains(profile.pcb_x + model.PCB_W + 0.30,
                                               b_y, 18.10))

            with self.subTest(profile=profile.key, section="D-D"):
                # D-D crosses the intentional service aperture under the PCB.
                centre_x = profile.pcb_x + model.PCB_W / 2.0
                self.assertFalse(cover.contains(centre_x, d_y, 26.00))
                self.assertTrue(parts["Tang Nano 9K PCB"].contains(centre_x, d_y, 19.00))

            for code, section in sections.items():
                with self.subTest(profile=profile.key, section=code):
                    self.assertTrue(any(
                        section_cells(part, section.plane, section.coordinate)
                        for part in parts.values()
                    ))


if __name__ == "__main__":
    unittest.main()
