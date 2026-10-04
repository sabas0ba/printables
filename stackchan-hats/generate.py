"""Export the cap and all decoration sets, and verify fit and printability.

Writes STL files in print orientation to ``stl/`` and the measured results to
``validation.json``. Any failed check aborts with a non-zero exit status.
"""

import json
from pathlib import Path
import struct
from typing import Any

import cadquery as cq
import numpy as np

import cap
import head
import toppers


DIRECTORY = Path(__file__).resolve().parent
OUTPUT = DIRECTORY / "stl"
REPORT = DIRECTORY / "validation.json"
TOLERANCE = 0.1
ANGULAR_TOLERANCE = 0.3
LAYOUT_GAP = 4.0
PLA_DENSITY = 1.24                 # g/cm3, solid material
OVERHANG_NORMAL_Z = -0.7072        # steeper than 45 degrees from vertical
OVERHANG_LIMIT_MM2 = 1.0
HEAD_GAP = 0.5                     # minimum distance from decorations to head
EPSILON_VOLUME = 0.05              # mm3, numerical contact allowance


def box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> cq.Solid:
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def layout(shapes: list[cq.Shape]) -> list[cq.Shape]:
    """Place print-oriented pieces side by side along x on the bed."""
    placed, cursor = [], 0.0
    for shape in shapes:
        bb = shape.BoundingBox()
        moved = shape.translate(cq.Vector(cursor - bb.xmin, -bb.ymin, 0))
        placed.append(moved)
        cursor += bb.xlen + LAYOUT_GAP
    width = cursor - LAYOUT_GAP
    return [shape.translate(cq.Vector(-width / 2, 0, 0)) for shape in placed]


def read_stl(path: Path) -> np.ndarray:
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + 50 * count:
        raise ValueError(f"{path.name}: expected a binary STL")
    records = np.frombuffer(data, dtype=np.dtype([("normal", "<f4", (3,)),
                                                  ("vertices", "<f4", (3, 3)),
                                                  ("attribute", "<u2")]), offset=84)
    return records["vertices"].astype(np.float64)


def normalise_stl(path: Path) -> None:
    """Rewrite the STL in a canonical order with normals from the vertices.

    OCC's parallel mesher emits the same triangles in a run-dependent order,
    and its normals vary in the last bits; both would defeat the byte-for-byte
    check. Each triangle is rotated so that its smallest vertex comes first
    (winding kept), and the triangles are sorted.
    """
    data = path.read_bytes()
    count = struct.unpack_from("<I", data, 80)[0]
    dtype = np.dtype([("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)),
                      ("attribute", "<u2")])
    records = np.frombuffer(data, dtype=dtype, offset=84, count=count).copy()
    vertices = records["vertices"]
    first = np.array([min(range(3), key=lambda i: tuple(tri[i])) for tri in vertices])
    order = (np.arange(3)[None, :] + first[:, None]) % 3
    vertices = np.take_along_axis(vertices, order[:, :, None], axis=1)
    flat = vertices.reshape(len(vertices), 9)
    vertices = vertices[np.lexsort(flat.T[::-1])]
    v = vertices.astype(np.float64)
    normal = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-30)
    records["vertices"] = vertices
    records["normal"] = (np.round(normal, 6) + 0.0).astype(np.float32)
    records["attribute"] = 0
    path.write_bytes(data[:84] + records.tobytes())


def inspect_mesh(path: Path) -> dict[str, Any]:
    """Mesh facts for the report, including the support-free check."""
    triangles = read_stl(path)
    edges = np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0])
    areas = np.linalg.norm(edges, axis=1) / 2
    normals = edges / np.maximum(2 * areas[:, None], 1e-12)
    lowest = triangles[:, :, 2].min(axis=1)
    overhang = (normals[:, 2] < OVERHANG_NORMAL_Z) & (lowest > 0.3)
    bed = (normals[:, 2] < -0.999) & (np.abs(triangles[:, :, 2]).max(axis=1) < 1e-4)
    points = triangles.reshape(-1, 3)
    return {
        "triangles": int(len(triangles)),
        "size_mm": [round(float(v), 2) for v in np.ptp(points, axis=0)],
        "min_z_mm": round(float(points[:, 2].min()), 4),
        "bed_contact_mm2": round(float(areas[bed].sum()), 1),
        "overhang_mm2": round(float(areas[overhang].sum()), 2),
    }


def solid_facts(shape: cq.Shape) -> dict[str, Any]:
    volume = shape.Volume()
    return {"solids": len(shape.Solids()), "valid": bool(shape.isValid()),
            "volume_cm3": round(volume / 1000, 2),
            "mass_g": round(volume / 1000 * PLA_DENSITY, 1)}


def export(shape: cq.Shape, name: str) -> dict[str, Any]:
    path = OUTPUT / f"{name}.stl"
    cq.exporters.export(shape, str(path), tolerance=TOLERANCE,
                        angularTolerance=ANGULAR_TOLERANCE)
    normalise_stl(path)
    facts = solid_facts(shape) | inspect_mesh(path)
    if facts["min_z_mm"] != 0.0 or facts["bed_contact_mm2"] <= 0:
        raise SystemExit(f"{name}: not resting on the bed")
    if facts["overhang_mm2"] > OVERHANG_LIMIT_MM2:
        raise SystemExit(f"{name}: {facts['overhang_mm2']} mm2 needs support")
    return facts


def check_cap(solid: cq.Shape) -> dict[str, Any]:
    if not solid.isValid() or len(solid.Solids()) != 1:
        raise SystemExit("cap: not a valid single solid")
    interference = solid.intersect(head.envelope(0.0)).Volume()
    detents = solid.intersect(head.envelope(0.0, holes=False)).Volume()
    if interference > EPSILON_VOLUME:
        raise SystemExit(f"cap: {interference:.3f} mm3 interference with the head")
    if detents < 1.0:
        raise SystemExit("cap: detents do not reach into the side holes")
    return {"head_interference_mm3": round(interference, 3),
            "detent_engagement_mm3": round(detents, 2),
            "radial_clearance_mm": cap.CLEARANCE,
            "slot_mm": [cap.SLOT_LENGTH, cap.SLOT_WIDTH, cap.PLATE],
            "slot_x_mm": list(cap.SLOT_X.values()),
            "slot_y_mm": list(cap.SLOT_Y.values())}


def check_piece(piece: toppers.Piece, full: cq.Shape, body: cq.Shape,
                cap_solid: cq.Shape, keepout: cq.Shape) -> dict[str, Any]:
    half = cap.TAB_LENGTH / 2
    foot = box(-half, half, 0, toppers.FOOT_HEIGHT, 0,
               toppers.THICKNESS - toppers.EDGE_RADIUS)
    covered = body.intersect(foot).Volume() / foot.Volume()
    if covered < 0.995:
        raise SystemExit(f"{piece.name}: body does not cover the tab ({covered:.3f})")
    location = toppers.placement(piece)
    worn_full, worn_body = full.moved(location), body.moved(location)
    body_overlap = worn_body.intersect(cap_solid).Volume()
    tab_overlap = worn_full.intersect(cap_solid).Volume()
    head_overlap = worn_full.intersect(keepout).Volume()
    if body_overlap > EPSILON_VOLUME:
        raise SystemExit(f"{piece.name}: body intersects the cap")
    if not 0.05 < tab_overlap < 1.5:
        raise SystemExit(f"{piece.name}: unexpected tab press fit {tab_overlap:.2f} mm3")
    if head_overlap > EPSILON_VOLUME:
        raise SystemExit(f"{piece.name}: closer than {HEAD_GAP} mm to the head")
    return {"slot": f"{piece.row}-{piece.slot}",
            "tab_press_fit_mm3": round(tab_overlap, 2)}


def compatibility(built: dict[str, list[tuple[toppers.Piece, cq.Shape, cq.Shape]]]
                  ) -> dict[str, list[str]]:
    """Centre pieces that can be worn together with each pair set."""
    worn = {key: [body.moved(toppers.placement(piece)) for piece, _, body in items]
            for key, items in built.items()}
    centres = [s.key for s in toppers.SETS if s.pieces[0].slot == "centre"]
    pairs = [s.key for s in toppers.SETS if s.pieces[0].slot != "centre"]
    result = {}
    for pair_key in pairs:
        result[pair_key] = [
            centre_key for centre_key in centres
            if all(a.intersect(b).Volume() <= EPSILON_VOLUME
                   for a in worn[pair_key] for b in worn[centre_key])]
    return result


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    cap_solid = cap.make_cap()
    report: dict[str, Any] = {"cap": check_cap(cap_solid)}
    report["cap"] |= export(cap.to_print(cap_solid), "cap")
    print("cap: ok")

    keepout = head.envelope(HEAD_GAP, holes=False)
    built = {}
    for topper in toppers.SETS:
        items = toppers.build_set(topper)
        built[topper.key] = items
        pieces = {piece.name: check_piece(piece, full, body, cap_solid, keepout)
                  for piece, full, body in items}
        plate = layout([full for _, full, _ in items])
        compound = plate[0] if len(plate) == 1 else cq.Compound.makeCompound(plate)
        facts = export(compound, topper.key)
        if facts["solids"] != len(items) or not facts["valid"]:
            raise SystemExit(f"{topper.key}: invalid plate")
        report[topper.key] = {"title": topper.title, "pieces": pieces} | facts
        print(f"{topper.key}: ok")

    report["compatible_centre_pieces"] = compatibility(built)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
