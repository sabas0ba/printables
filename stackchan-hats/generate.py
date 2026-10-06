"""Export the cap and all decoration sets, and verify fit and printability.

Writes STL files in print orientation to ``stl/`` and the measured results to
``validation.json``. Any failed check aborts with a non-zero exit status.
"""

import json
from pathlib import Path
import struct
from typing import Any

import cadquery as cq
from OCP.OSD import OSD_ThreadPool
import numpy as np

import cap
import drapes
import head
import integral
import shells
import toppers


# Parallel booleans and meshing in OCC can split faces differently from run
# to run. One worker thread keeps the outputs byte-for-byte reproducible.
OSD_ThreadPool.DefaultPool_s(1)

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
SAMPLE_SPACING = 1.0               # mm, surface samples for the pitch sweep
MOMENT_LIMIT = 150.0               # g cm about the pitch axis, worn set + cap
SHELL_SKIN = 0.9                   # mm, two 0.45 mm perimeters and skin layers
SHELL_INFILL = 0.10                # sparse infill fraction inside the skin
SHELL_MIN_PITCH_DEG = 30.0         # smallest acceptable look-up range for a shell


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
    # Serial meshing: the parallel mesher can triangulate a face differently
    # from run to run, which reordering alone cannot make reproducible.
    shape.exportStl(str(path), tolerance=TOLERANCE, angularTolerance=ANGULAR_TOLERANCE,
                    ascii=False, relative=True, parallel=False)
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
            "slots": {f"{row}-{position}": list(xya)
                      for (row, position), xya in cap.SLOTS.items()}}


def check_piece(piece: toppers.Piece, full: cq.Shape, body: cq.Shape,
                cap_solid: cq.Shape, keepout: cq.Shape) -> dict[str, Any]:
    half = cap.TAB_LENGTH / 2
    foot = box(-half, half, 0, toppers.FOOT_HEIGHT, 0,
               min(piece.thickness, cap.TAB_THICKNESS) - toppers.EDGE_RADIUS)
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


def surface_samples(shape: cq.Shape) -> np.ndarray:
    """Points on the surface no further apart than SAMPLE_SPACING."""
    vertices, faces = shape.tessellate(0.2, 0.3)
    points = np.array([v.toTuple() for v in vertices], dtype=np.float64)
    triangles = points[np.array(faces, dtype=np.int64)]
    result = [points]
    for tri in triangles:
        longest = max(np.linalg.norm(tri[1] - tri[0]), np.linalg.norm(tri[2] - tri[1]),
                      np.linalg.norm(tri[0] - tri[2]))
        n = int(np.ceil(longest / SAMPLE_SPACING))
        if n > 1:
            a, b = np.meshgrid(np.arange(n + 1), np.arange(n + 1))
            keep = a + b <= n
            result.append(tri[0] + np.outer(a[keep] / n, tri[1] - tri[0])
                          + np.outer(b[keep] / n, tri[2] - tri[0]))
    return np.concatenate(result)


def pitch_moment(shapes: list[cq.Shape]) -> tuple[float, float]:
    """Mass in g and the largest gravity moment about the pitch axis in g cm."""
    volume = sum(s.Volume() for s in shapes)
    mass = volume / 1000 * PLA_DENSITY
    centre = sum((s.Center() * s.Volume() for s in shapes), cq.Vector()) / volume
    com = np.array([[centre.x, centre.y, centre.z]])
    arms = [abs(head.pitch(com, a)[0, 1] - head.PITCH_AXIS[0]) / 10
            for a in np.arange(head.PITCH_RANGE_DEG[0], head.PITCH_RANGE_DEG[1] + 1e-9)]
    return mass, mass * max(arms)


def motion_facts(name: str, shapes: list[cq.Shape], own: list[cq.Shape]) -> dict[str, Any]:
    """Pitch sweep clearance and gravity moments for shapes worn on the head.

    ``own`` are the item's own parts, without the cap it is worn on.
    """
    sweep = head.sweep_clearance(np.concatenate([surface_samples(s) for s in shapes]))
    if sweep["colliding_samples"]:
        raise SystemExit(f"{name}: meets the body, base or desk at "
                         f"{sweep['first_collision_deg']} deg pitch")
    mass, moment = pitch_moment(shapes)
    if moment > MOMENT_LIMIT:
        raise SystemExit(f"{name}: {moment:.0f} g cm exceeds {MOMENT_LIMIT:.0f} g cm")
    return {"lowest_z_in_motion_mm": sweep["lowest_z_mm"],
            "worn_mass_g": round(mass, 1),
            "max_pitch_moment_g_cm": round(moment, 1),
            "own_pitch_moment_g_cm": round(pitch_moment(own)[1], 1)}


def printed_mass(shape: cq.Shape) -> tuple[float, np.ndarray]:
    """Mass in g and centre of mass for a print with skin and sparse infill.

    The skin is the surface area times SHELL_SKIN, placed at the surface
    centroid; the rest of the volume is filled to SHELL_INFILL.
    """
    volume = shape.Volume()
    faces = shape.Faces()
    area = sum(f.Area() for f in faces)
    skin_centre = sum((f.Center() * f.Area() for f in faces), cq.Vector()) / area
    skin = min(volume, area * SHELL_SKIN)
    core = (volume - skin) * SHELL_INFILL
    if volume - skin > 1e-9:
        core_centre = (shape.Center() * volume - skin_centre * skin) / (volume - skin)
    else:
        core_centre = skin_centre
    centre = (skin_centre * skin + core_centre * core) / (skin + core)
    return (skin + core) / 1000 * PLA_DENSITY, np.array(centre.toTuple())


def check_shell(name: str, solid: cq.Shape) -> dict[str, Any]:
    if not solid.isValid() or len(solid.Solids()) != 1:
        raise SystemExit(f"{name}: not a valid single solid")
    interference = solid.intersect(head.envelope(0.0)).Volume()
    detents = solid.intersect(head.envelope(0.0, holes=False)).Volume()
    if interference > EPSILON_VOLUME:
        raise SystemExit(f"{name}: {interference:.3f} mm3 interference with the head")
    if detents < 0.1:
        raise SystemExit(f"{name}: detents do not reach into the side holes")
    return {"head_interference_mm3": round(interference, 3),
            "detent_engagement_mm3": round(detents, 2)}


def shell_motion(name: str, solid: cq.Shape) -> dict[str, Any]:
    """Largest look-up angle with clearance and the moment within the limit.

    Shells cover the head's rear, so instead of the full pitch range the
    angle up to which both conditions hold from 0 degrees is reported.
    """
    points = surface_samples(solid)
    exposed = ~head.shielded(points)
    mass, centre = printed_mass(solid)
    allowed, moment, lowest, reason = None, 0.0, np.inf, "full range"
    for angle in np.arange(head.PITCH_RANGE_DEG[0], head.PITCH_RANGE_DEG[1] + 1e-9):
        moved = head.pitch(points, angle)
        arm = abs(head.pitch(centre[None], angle)[0, 1] - head.PITCH_AXIS[0]) / 10
        if head.collisions(moved, exposed).any():
            reason = "clearance"
            break
        if mass * arm > MOMENT_LIMIT:
            reason = "moment"
            break
        allowed, moment = float(angle), max(moment, mass * arm)
        lowest = min(lowest, float(moved[:, 2].min()))
    if allowed is None or allowed < SHELL_MIN_PITCH_DEG:
        raise SystemExit(f"{name}: looks up only to {allowed} deg ({reason})")
    return {"allowed_pitch_deg": allowed, "pitch_limited_by": reason,
            "printed_mass_g": round(mass, 1),
            "max_pitch_moment_g_cm": round(float(moment), 1),
            "lowest_z_in_motion_mm": round(lowest, 2)}


def cap_variants():
    """(key, title, solid) of every part that replaces the cap and keeps its slots."""
    for variant in integral.VARIANTS:
        yield variant.key, variant.title, integral.build(variant)
    for drape in drapes.DRAPES:
        yield drape.key, drape.title, drapes.build(drape)


def worst_combination(report: dict[str, Any], groups: dict[str, str]) -> dict[str, Any]:
    """Upper bound for any combination: one cap and one set per slot group.

    The moment of a sum never exceeds the sum of the parts' largest moments.
    """
    caps = (["cap"] + [v.key for v in integral.VARIANTS]
            + [d.key for d in drapes.DRAPES])
    heaviest_cap = max(caps, key=lambda k: report[k]["own_pitch_moment_g_cm"])
    chosen: dict[str, str] = {}
    for key, group in groups.items():
        best = chosen.get(group)
        if best is None or (report[key]["own_pitch_moment_g_cm"]
                            > report[best]["own_pitch_moment_g_cm"]):
            chosen[group] = key
    bound = report[heaviest_cap]["own_pitch_moment_g_cm"] + sum(
        report[k]["own_pitch_moment_g_cm"] for k in chosen.values())
    if bound > MOMENT_LIMIT:
        raise SystemExit(f"worst combination bound {bound:.0f} g cm exceeds the limit")
    return {"items": [heaviest_cap, *sorted(chosen.values())],
            "moment_bound_g_cm": round(bound, 1), "limit_g_cm": MOMENT_LIMIT}


def conflicts(worn: dict[str, list[cq.Shape]],
              slots: dict[str, set[str]]) -> list[list[str]]:
    """Pairs of items in different slots whose parts overlap when worn.

    Items sharing a slot are exclusive anyway and are not listed.
    """
    keys = list(worn)
    boxes = {k: [s.BoundingBox() for s in worn[k]] for k in keys}
    result = []
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if slots[a] & slots[b]:
                continue
            hit = False
            for sa, ba in zip(worn[a], boxes[a]):
                for sb, bb in zip(worn[b], boxes[b]):
                    if (ba.xmin > bb.xmax or bb.xmin > ba.xmax or ba.ymin > bb.ymax
                            or bb.ymin > ba.ymax or ba.zmin > bb.zmax
                            or bb.zmin > ba.zmax):
                        continue
                    if sa.intersect(sb).Volume() > EPSILON_VOLUME:
                        hit = True
                        break
                if hit:
                    break
            if hit:
                result.append([a, b])
    return result


def main() -> None:
    OUTPUT.mkdir(exist_ok=True)
    # Remove previous exports so that a renamed or dropped set leaves no
    # stale file behind for the regeneration check to accept.
    for stale in OUTPUT.glob("*.stl"):
        stale.unlink()
    cap_solid = cap.make_cap()
    report: dict[str, Any] = {"cap": check_cap(cap_solid)}
    report["cap"] |= export(cap.to_print(cap_solid), "cap")
    report["cap"] |= motion_facts("cap", [cap_solid], [cap_solid])
    print("cap: ok")

    # Integral parts of a variant, for overlap checks with plug-in sets.
    worn: dict[str, list[cq.Shape]] = {}
    slots: dict[str, set[str]] = {}
    for key, title, solid in cap_variants():
        facts = check_cap(solid) | export(cap.to_print(solid), key)
        report[key] = {"title": title} | facts | motion_facts(key, [solid], [solid])
        worn[key] = [solid.cut(cap_solid)]
        slots[key] = {"variant"}
        print(f"{key}: ok")

    keepout = head.envelope(HEAD_GAP, holes=False)
    for topper in toppers.SETS:
        items = toppers.build_set(topper)
        pieces = {piece.name: check_piece(piece, full, body, cap_solid, keepout)
                  for piece, full, body in items}
        plate = layout([full for _, full, _ in items])
        compound = plate[0] if len(plate) == 1 else cq.Compound.makeCompound(plate)
        facts = export(compound, topper.key)
        if facts["solids"] != len(items) or not facts["valid"]:
            raise SystemExit(f"{topper.key}: invalid plate")
        placed = [full.moved(toppers.placement(piece)) for piece, full, _ in items]
        motion = motion_facts(topper.key, [cap_solid, *placed], placed)
        report[topper.key] = {"title": topper.title, "pieces": pieces} | facts | motion
        worn[topper.key] = [body.moved(toppers.placement(piece))
                            for piece, _, body in items]
        slots[topper.key] = {f"{piece.row}-{piece.slot}" for piece, _, _ in items}
        print(f"{topper.key}: ok")

    for shell in shells.SHELLS:
        solid = shells.build(shell)
        facts = check_shell(shell.key, solid) | export(shells.to_print(solid), shell.key)
        report[shell.key] = ({"title": shell.title} | facts
                             | shell_motion(shell.key, solid))
        print(f"{shell.key}: ok")

    report["conflicting_pairs"] = conflicts(worn, slots)
    groups = {t.key: "-".join(sorted({p.row for p in t.pieces})) + (
        "-centre" if t.pieces[0].slot == "centre" else "-pair") for t in toppers.SETS}
    report["worst_combination"] = worst_combination(report, groups)
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
