import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))  # the generators import each other as top-level modules


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


r4 = load("generate_case_r4_test", "generate_case_r4.py")
drawings = load("generate_release_drawings_test", "generate_release_drawings.py")
design = load("generate_design_spec_r4_test", "generate_design_spec_r4.py")
assembly = load("assembly_r4_test", "assembly_r4.py")
reference_3mf = load("generate_reference_3mf_r4_test", "generate_reference_3mf_r4.py")
assembled_stl = load("generate_assembled_stl_r4_test", "generate_assembled_stl_r4.py")
verify = load("verify_release_test", "verify_release.py")


class ReleaseGeometryTest(unittest.TestCase):
    def test_generate_complete_release_set(self):
        with tempfile.TemporaryDirectory() as directory:
            stats = r4.generate(Path(directory))
            self.assertEqual(len(stats), 9)
            names = {item["file"] for item in stats}
            self.assertIn("case_snap_pin.stl", names)
            self.assertIn("dock_tray_screw_common.stl", names)
            self.assertIn("rear_access_frame_common.stl", names)
            self.assertIn("rear_service_cap_common.stl", names)
            self.assertIn("fit_coupon.stl", names)
            self.assertEqual(r4.PROJECT_VERSION, "1.0.3")

    def test_retention_count_and_clearance(self):
        self.assertEqual(r4.RETAINER_CLIP_COUNT, 6)
        self.assertEqual(r4.DOCK_SCREW_COUNT, 4)
        self.assertEqual(r4.SERVICE_HOOK_COUNT, 2)
        self.assertEqual(r4.SERVICE_LATCH_COUNT, 2)
        self.assertAlmostEqual(r4.PIN_HOLE - r4.PIN_SHAFT, 0.80)
        self.assertAlmostEqual(r4.PIN_LATCH_SHOULDER, 33.80)
        self.assertAlmostEqual(r4.CASE_DEPTH, 53.80)
        self.assertAlmostEqual(r4.CASE_H, 112.00)

    def test_snap_pin_is_exported_flat(self):
        bounds = r4.build_case_snap_pin().bounds()
        spans = tuple(bounds[1][i] - bounds[0][i] for i in range(3))
        self.assertAlmostEqual(spans[0], r4.PIN_TIP)
        self.assertAlmostEqual(spans[1], 7.5)
        self.assertAlmostEqual(spans[2], 7.5)

    def test_retainer_clears_front_shell_corner_bosses(self):
        for key in ("43", "50"):
            mesh = r4.build_retainer_snap(key)
            for triangle in mesh.triangles:
                cx = sum(point[0] for point in triangle) / 3.0
                cy = sum(point[1] for point in triangle) / 3.0
                in_left = cx < 9.0
                in_right = cx > r4.CASE_W - 9.0
                in_lower = cy < 9.0
                in_upper = cy > r4.CASE_H - 9.0
                self.assertFalse((in_left or in_right) and (in_lower or in_upper))

    def test_retainers_are_single_watertight_manifold_parts(self):
        for key in ("43", "50"):
            topology = verify.mesh_topology(r4.build_retainer_snap(key).triangles)
            self.assertEqual(topology, {
                "surface_components": 1,
                "boundary_edges": 0,
                "non_manifold_edges": 0,
                "inconsistent_winding_edges": 0,
                "duplicate_triangles": 0,
            })

    def test_topology_check_detects_separate_closed_shells(self):
        mesh = r4.Mesh("separate_shells")
        mesh.box(0, 0, 0, 1, 1, 1)
        mesh.box(2, 0, 0, 1, 1, 1)
        topology = verify.mesh_topology(mesh.triangles)
        self.assertEqual(topology["surface_components"], 2)
        self.assertEqual(topology["boundary_edges"], 0)
        self.assertEqual(topology["non_manifold_edges"], 0)
        self.assertEqual(topology["inconsistent_winding_edges"], 0)

    def test_official_dock_pitch_is_preserved(self):
        holes = r4.DOCK_HOLES
        self.assertAlmostEqual(holes[1][0] - holes[0][0], 87.0)
        self.assertAlmostEqual(holes[2][1] - holes[0][1], 65.0)

    def test_m2p5_screw_does_not_bottom(self):
        pilot_depth = r4.TRAY_T + r4.DOCK_STANDOFF_H - r4.DOCK_PILOT_BOTTOM
        plastic_engagement = r4.DOCK_SCREW_LENGTH - r4.DOCK_PCB_T_NOMINAL
        self.assertAlmostEqual(pilot_depth, 4.80)
        self.assertAlmostEqual(plastic_engagement, 4.41)
        self.assertGreater(pilot_depth - plastic_engagement, 0.35)

    def test_bridge_free_release_features(self):
        self.assertEqual(r4.DOCK_PILOT, 2.00)
        self.assertEqual(r4.DOCK_BOSS, 7.00)
        self.assertFalse(hasattr(r4, "add_fpc_tunnel"))
        self.assertFalse(hasattr(r4, "add_dock_snap_peg"))
        self.assertEqual(verify.unsupported_box_bases(r4.build_dock_tray_screw().triangles), [])
        self.assertEqual(verify.unsupported_box_bases(r4.build_rear_access_frame().triangles), [])

    def test_official_step_has_rear_clearance(self):
        dock_bounds = assembly.official_global_bounds(
            assembly.DOCK_STEP_BOUNDS_LOCAL, assembly.DOCK_STEP_OFFSET
        )
        rear_inner = assembly.CASE_DEPTH - 2.40
        self.assertAlmostEqual(assembly.CASE_DEPTH, 53.80)
        self.assertAlmostEqual(rear_inner - dock_bounds[1][2], 21.23455, places=4)

    def test_rear_frame_and_service_cap_assembly_transforms(self):
        frame = assembly.transform(
            r4.build_rear_access_frame().triangles,
            lambda p: (p[0], p[1], r4.STRUCTURAL_DEPTH - p[2]),
            reflected=True,
        )
        lower, upper = assembly.bounds(frame)
        self.assertAlmostEqual(lower[2], 11.80)
        self.assertAlmostEqual(upper[2], 33.80)
        cap = assembly.transform(
            r4.build_rear_service_cap().triangles,
            lambda p: (p[0], p[1], r4.CASE_DEPTH - p[2]),
            reflected=True,
        )
        lower, upper = assembly.bounds(cap)
        self.assertAlmostEqual(lower[2], 30.80)
        self.assertAlmostEqual(upper[2], 53.80)

    def test_service_cap_stays_clear_of_the_frame_top_wall(self):
        # The frame top wall spans Y >= CASE_H - WALL in front of the frame
        # plate; nothing on the seated cap may enter that volume.
        cap = assembly.transform(
            r4.build_rear_service_cap().triangles,
            lambda p: (p[0], p[1], r4.CASE_DEPTH - p[2]),
            reflected=True,
        )
        wall_inner_y = r4.CASE_H - r4.WALL
        plate_inner_z = r4.STRUCTURAL_DEPTH - r4.WALL
        for triangle in cap:
            for point in triangle:
                if point[1] > wall_inner_y + 1e-6:
                    self.assertGreaterEqual(point[2], plate_inner_z - 1e-6)

    def test_service_opening_and_cable_exits(self):
        self.assertEqual(r4.ACCESS_OPENING, (10.0, 10.0, 120.0, 92.0))
        self.assertEqual(r4.SERVICE_CABLE_EXITS, ((35.0, 20.0), (85.0, 20.0)))
        self.assertAlmostEqual(r4.SERVICE_HOOK_REACH - r4.SERVICE_CAP_DEPTH, 3.0)
        dock = assembly.official_global_bounds(
            assembly.DOCK_STEP_BOUNDS_LOCAL, assembly.DOCK_STEP_OFFSET
        )
        ox, oy, ow, oh = r4.ACCESS_OPENING
        self.assertLess(ox, dock[0][0])
        self.assertGreater(ox + ow, dock[1][0])
        self.assertLess(oy, dock[0][1])
        self.assertGreater(oy + oh, dock[1][1])
        self.assertLess(2.20 + r4.SERVICE_DETENT, dock[0][1])
        self.assertGreater(109.20 - r4.SERVICE_DETENT, dock[1][1])

    def test_reference_3mf_is_valid_package(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / "stl"
            r4.generate(out)
            dock_ref = root / "dock_ref.stl"
            r4.build_dock_tray_screw().write_stl(dock_ref)
            result = root / "assembly.3mf"
            reference_3mf.generate(result, out, dock_ref, "43")
            with zipfile.ZipFile(result) as archive:
                self.assertEqual(
                    set(archive.namelist()),
                    {"[Content_Types].xml", "_rels/.rels", "3D/3dmodel.model"},
                )

    def test_complete_assembly_stl_contains_all_modeled_parts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / "stl"
            r4.generate(out)
            dock_ref = root / "dock_ref.stl"
            r4.build_dock_tray_screw().write_stl(dock_ref)
            result = root / "complete.stl"
            metadata = assembled_stl.generate(result, out, dock_ref, "43")
            triangles = assembly.read_binary_stl(result)
            self.assertEqual(len(metadata["parts"]), 9)
            self.assertEqual(len(triangles), metadata["triangles"])
            self.assertEqual(metadata["removed_degenerate_triangles"], 0)
            self.assertAlmostEqual(metadata["bounds_min_mm"][2], -1.80)
            self.assertAlmostEqual(metadata["bounds_max_mm"][2], 53.80)


class ReleaseDocumentTest(unittest.TestCase):
    def test_release_drawing_is_a3_and_thirteen_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            out = root / "stl"
            r4.generate(out)
            dock_ref = root / "dock_ref.stl"
            r4.build_dock_tray_screw().write_stl(dock_ref)
            path = root / "drawing.pdf"
            drawings.generate(path, out, dock_ref)
            reader = PdfReader(path)
            self.assertEqual(len(reader.pages), 13)
            for page in reader.pages:
                self.assertAlmostEqual(float(page.mediabox.width) / drawings.MM, 420.0, places=2)
                self.assertAlmostEqual(float(page.mediabox.height) / drawings.MM, 297.0, places=2)

    def test_design_spec_is_a4(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "design.pdf"
            design.generate(path)
            reader = PdfReader(path)
            self.assertGreaterEqual(len(reader.pages), 7)
            self.assertAlmostEqual(float(reader.pages[0].mediabox.width), 595.28, places=1)
            self.assertAlmostEqual(float(reader.pages[0].mediabox.height), 841.89, places=1)


if __name__ == "__main__":
    unittest.main()
