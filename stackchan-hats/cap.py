"""Common push-on cap for the StackChan head, millimetres.

The cap is modelled in head coordinates (see head.py) and exported upside
down: its top surface is the print bed, so it needs no supports. Decorations
plug into the nine through-slots in the top plate. Variants add integral
features through ``make_cap(extras)``.
"""

import math

import cadquery as cq

import head


CLEARANCE = 0.3              # radial gap between head and cap
PLATE = 3.0                  # top plate thickness, also the slot depth
SKIRT = 1.6                  # side skirt thickness
SKIRT_BOTTOM = -13.0         # skirt lower edge, 1 mm above the head hole bottom
SKIRT_Y = (0.5, 44.2)        # skirts stay on the shell, clear of the CoreS3
FRONT = -11.0                # brim front edge over the CoreS3 top
CORE_RECESS = 0.6            # extra gap over the CoreS3 top
LIP_HALF_WIDTH = 16.0
LIP_BOTTOM = -3.5
LEAD_IN = 0.8                # chamfer on the skirt's inner lower edge
PLAN_RADIUS = 4.0            # plan-view corner radius
END_CHAMFER = 1.0            # front and rear top edge chamfer, 45 degrees
OUTER_RADIUS = 5.0           # side top edge, followed by a 45 degree flank

# Detent: a 0.6 mm spherical bump on a slotted flexure enters the middle
# side hole. The slots make a 10 mm wide, 8.5 mm long tongue in the skirt.
DETENT_HEIGHT = 0.6
DETENT_SPHERE = 3.0
FLEX_HALF_WIDTH = 5.5
FLEX_SLIT = 1.0
FLEX_TOP = -4.5

LIGHT_WINDOW_WIDTH = 2.6
LIGHT_WINDOW_Y = (5.0, 35.5)

TAB_LENGTH = 12.0            # topper tab length along x
TAB_THICKNESS = 3.2          # equals the topper plate thickness
TAB_DEPTH = PLATE - 0.3      # tab stops short of the head surface
SLOT_LENGTH = TAB_LENGTH + 0.3
SLOT_WIDTH = TAB_THICKNESS + 0.2
# (row, position) -> (x, y, rotation about z in degrees). Rotation 0 puts
# the slot length along x; the tail slot runs along y.
SLOTS = {(row, position): (x, y, 0.0)
         for row, y in (("front", 12.0), ("rear", 32.0))
         for position, x in (("left", -16.0), ("centre", 0.0), ("right", 16.0))}
SLOTS |= {("wing", "left"): (-16.0, 44.0, 0.0), ("wing", "right"): (16.0, 44.0, 0.0),
          ("tail", "centre"): (0.0, 40.7, 90.0)}

INNER_HALF = head.HEAD_WIDTH / 2 + CLEARANCE      # 27.3
OUTER_HALF = INNER_HALF + SKIRT                   # 28.9
TOP = CLEARANCE + PLATE                           # 3.3, cap top surface
REAR = head.SHELL_DEPTH + CLEARANCE + SKIRT       # 48.6, lip outer face


def outer_profile() -> cq.Workplane:
    """x-z section: vertical skirt, R5 arc to 45 degrees, flank to the top."""
    centre_x = OUTER_HALF - OUTER_RADIUS
    centre_z = -1.2
    diagonal = OUTER_RADIUS * math.sqrt(0.5)
    flank = (centre_x + diagonal, centre_z + diagonal)
    top_x = flank[0] - (TOP - flank[1])
    mid = (centre_x + OUTER_RADIUS * math.cos(math.radians(22.5)),
           centre_z + OUTER_RADIUS * math.sin(math.radians(22.5)))
    return (cq.Workplane("XZ")
            .moveTo(-OUTER_HALF, SKIRT_BOTTOM)
            .lineTo(OUTER_HALF, SKIRT_BOTTOM)
            .lineTo(OUTER_HALF, centre_z)
            .threePointArc(mid, flank)
            .lineTo(top_x, TOP)
            .lineTo(-top_x, TOP)
            .lineTo(-flank[0], flank[1])
            .threePointArc((-mid[0], mid[1]), (-OUTER_HALF, centre_z))
            .close())


def box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> cq.Solid:
    return cq.Solid.makeBox(x1 - x0, y1 - y0, z1 - z0, cq.Vector(x0, y0, z0))


def span(a: float, b: float) -> tuple[float, float]:
    return min(a, b), max(a, b)


def prism_x(points: list[tuple[float, float]], half: float = 40.0) -> cq.Solid:
    """Prism along x from a y-z polygon."""
    return (cq.Workplane("YZ", origin=(-half, 0, 0))
            .polyline(points).close().extrude(2 * half).val())


def prism_y(points: list[tuple[float, float]], y0: float, y1: float) -> cq.Solid:
    """Prism along y from an x-z polygon."""
    return head.extrude_y(cq.Workplane("XZ").polyline(points).close(), y0, y1)


def make_cap(extras: list[cq.Shape] | None = None) -> cq.Solid:
    """Build the cap; extras are fused before slots and windows are cut."""
    cap = head.extrude_y(outer_profile(), FRONT, REAR)

    # Plan-view rounding of the four corners.
    plan = (cq.Workplane("XY", origin=(0, (FRONT + REAR) / 2, -20))
            .sketch().rect(2 * OUTER_HALF, REAR - FRONT)
            .vertices().fillet(PLAN_RADIUS).finalize()
            .extrude(40).val())
    cap = cap.intersect(plan)

    cap = cap.cut(head.envelope(CLEARANCE, holes=False))
    cap = cap.cut(box(-40, 40, FRONT - 1, SKIRT_Y[0], -20,
                      CLEARANCE + CORE_RECESS))
    cap = cap.cut(box(-40, 40, SKIRT_Y[1], REAR + 1, -20, CLEARANCE))
    cap = cap.fuse(box(-LIP_HALF_WIDTH, LIP_HALF_WIDTH,
                       head.SHELL_DEPTH + CLEARANCE, REAR,
                       LIP_BOTTOM, CLEARANCE + 0.01))

    # 45 degree chamfers on the front and rear top edges print without support.
    e = END_CHAMFER
    cap = cap.cut(prism_x([(FRONT - 1, TOP + 1), (FRONT + e + 1, TOP + 1),
                           (FRONT - 1, TOP - e - 1)]))
    cap = cap.cut(prism_x([(REAR + 1, TOP + 1), (REAR - e - 1, TOP + 1),
                           (REAR + 1, TOP - e - 1)]))

    for extra in extras or []:
        cap = cap.fuse(extra)
    if extras:
        cap = cap.cut(head.envelope(CLEARANCE, holes=False))

    for side in (-1, 1):
        inner = side * INNER_HALF
        # Lead-in chamfer along the skirt's inner lower edge.
        cap = cap.cut(prism_y([(inner - side * 0.01, SKIRT_BOTTOM - 0.01),
                               (inner + side * LEAD_IN, SKIRT_BOTTOM - 0.01),
                               (inner - side * 0.01, SKIRT_BOTTOM + LEAD_IN)],
                              SKIRT_Y[0] - 1, SKIRT_Y[1] + 1))
        # Flexure slits around the detent, with rounded upper ends.
        hole_y = head.SIDE_HOLE_Y[1]
        for dy in (-FLEX_HALF_WIDTH, FLEX_HALF_WIDTH):
            y = hole_y + dy
            cap = cap.cut(box(*span(inner - side * 1, inner + side * (SKIRT + 0.4)),
                              y - FLEX_SLIT / 2, y + FLEX_SLIT / 2,
                              SKIRT_BOTTOM - 1, FLEX_TOP))
            cap = cap.cut(cq.Solid.makeCylinder(
                FLEX_SLIT / 2, SKIRT + 1.9, cq.Vector(inner - side * 1.5, y, FLEX_TOP),
                cq.Vector(side, 0, 0)))
        # Spherical detent on the inner skirt face.
        centre = cq.Vector(inner + side * (DETENT_SPHERE - DETENT_HEIGHT),
                           hole_y, head.SIDE_HOLE_Z)
        sphere = cq.Solid.makeSphere(DETENT_SPHERE, centre, angleDegrees1=-90,
                                     angleDegrees2=90)
        limit = box(*span(inner - side * (DETENT_HEIGHT + 0.1), inner + side * 0.05),
                    hole_y - 4, hole_y + 4, -15, -5)
        cap = cap.fuse(sphere.intersect(limit))
        # Windows over the LED light guides.
        window = (cq.Workplane("XY", origin=(side * head.LIGHT_SLOT_X,
                                             sum(LIGHT_WINDOW_Y) / 2, -3))
                  .slot2D(LIGHT_WINDOW_Y[1] - LIGHT_WINDOW_Y[0],
                          LIGHT_WINDOW_WIDTH, angle=90)
                  .extrude(10).val())
        cap = cap.cut(window)

    for x, y, angle in SLOTS.values():
        slot = box(-SLOT_LENGTH / 2, SLOT_LENGTH / 2, -SLOT_WIDTH / 2, SLOT_WIDTH / 2,
                   -1, TOP + 1)
        slot = slot.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), angle)
        cap = cap.cut(slot.translate(cq.Vector(x, y, 0)))
    if not cap.isValid() or len(cap.Solids()) != 1:
        raise ValueError("The cap is not a valid single solid")
    return cap


def to_print(shape: cq.Shape) -> cq.Shape:
    """Turn the cap upside down so that its top surface lies on z = 0."""
    return shape.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), 180).translate(
        cq.Vector(0, 0, TOP))
