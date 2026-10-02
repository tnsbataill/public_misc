"""Parametric 3D models of ORBIS Stakpak straight-wall totes NXO1215-5 and NXO1215-7.

Published specs (ORBIS / distributors):
  NXO1215-5: outside 12" L x 15" W x 5" H,   inside bottom 9.4" x 13", product clearance 4.4", 1.8 lb
  NXO1215-7: outside 12" L x 15" W x 7.5" H, inside bottom 9.4" x 13", product clearance 6.8", 2.3 lb
  Features: vertical (straight) sides, reinforced external ribbing, fingertip handles,
  molded-in continuous bumper, textured label areas, drain holes in the bumper and handles.

The part is modeled as a thin-wall HDPE molding: vertical side walls just inside a top bumper
channel (open underneath), vertical external ribs, a belt rib at the stacking line, and a
beveled base that drops inside the rim of the tote below. The bevel is what makes the inside
floor (9.4" x 13") smaller than the opening. Fingertip handle pockets sit on all four sides
and flat label pads on the 15" sides. All faces are planar (chamfered corners, no fillets) so the STL stays light and imports into
SolidWorks as a solid body. Feature sizes not in the spec sheet are estimates,
not ORBIS CAD data. Output is in millimetres.

Usage: python build_totes.py   -> writes STEP + STL for each model into ./models
"""
import math
from pathlib import Path

import cadquery as cq

IN = 25.4             # mm per inch
HDPE = 0.0347         # lb per cubic inch, for the weight check

# Shared geometry (inches). X = 12" length, Y = 15" width, Z = height.
L, W = 12.0, 15.0
T = 0.10              # nominal wall thickness
FLOOR_T = 0.12
C = 0.5               # 45-degree corner chamfer, shared by bumper, wall and belt so the corners line up

WALL = (11.6, 14.6, C)         # vertical wall, outside L, W, corner chamfer
BOTTOM_IN = (9.4, 13.0, 0.35)   # inside floor (published size)
BASE_OUT = (BOTTOM_IN[0] + 2 * T, BOTTOM_IN[1] + 2 * T, BOTTOM_IN[2] + T)  # bottom of the bevel
BEVEL_TOP = (11.3, 14.3, 0.45) # top of the base bevel; fits inside the rim opening below

BUMPER_H = 0.55       # continuous bumper: deck plus downturned skirt
DECK_T = 0.13
BELT_H = 0.15         # belt rib at the stacking line
BELT = (L - 0.1, W - 0.1, C)

RIB_T = 0.12
X_FACE_RIBS = (-5.4, -3.6, 0.0, 3.6, 5.4)   # y positions on the 12"-wide ends (0 runs under the handle)
Y_FACE_RIBS = (-4.6, -3.0, 3.0, 4.6)        # x positions on the 15"-long sides

GRIP = {"x": 5.5, "y": 5.0}   # fingertip handle width on the X faces / Y faces
GRIP_H = 0.75         # finger opening height below the bumper skirt
GRIP_BACK = 0.45      # how far the pocket reaches behind the wall line
DRAIN = (0.5, 0.14)   # drain slot length x width

PAD_W, PAD_T = 4.6, 0.035      # raised label pad on the Y faces

MODELS = {
    "NXO1215-5": {"height": 5.0, "clearance": 4.4, "weight": 1.8},
    "NXO1215-7": {"height": 7.5, "clearance": 6.8, "weight": 2.3},
}


def octagon(x, y, c):
    """Rectangle x by y with 45-degree corner chamfers of leg c (all faces stay planar)."""
    hx, hy = x / 2, y / 2
    return [(hx, hy - c), (hx - c, hy), (-hx + c, hy), (-hx, hy - c),
            (-hx, -hy + c), (-hx + c, -hy), (hx - c, -hy), (hx, -hy + c)]


def slab(x, y, c, z0, z1):
    return cq.Workplane("XY").workplane(offset=z0).polyline(octagon(x, y, c)).close().extrude(z1 - z0)


def ruled_loft(bottom, top, z0, z1):
    """Frustum between two chamfered rectangles, built from planar faces (no spline surfaces)."""
    lo = [cq.Vector(x, y, z0) for x, y in octagon(*bottom)]
    hi = [cq.Vector(x, y, z1) for x, y in octagon(*top)]
    faces = [cq.Face.makeFromWires(cq.Wire.makePolygon(lo[::-1], close=True)),
             cq.Face.makeFromWires(cq.Wire.makePolygon(hi, close=True))]
    for i in range(8):
        j = (i + 1) % 8
        faces.append(cq.Face.makeFromWires(cq.Wire.makePolygon([lo[i], lo[j], hi[j], hi[i]], close=True)))
    solid = cq.Solid.makeSolid(cq.Shell.makeShell(faces)).fix()
    if solid.Volume() < 0:
        solid = cq.Solid(solid.wrapped.Reversed())
    return cq.Workplane("XY").add(solid)


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0).translate(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))


def faces():
    """(axis index, sign) for the four side walls."""
    return [(0, 1), (0, -1), (1, 1), (1, -1)]


def orient(axis, sign, n0, n1, t0, t1, z0, z1):
    """Box given in face coordinates: n = outward normal distance, t = along the wall."""
    a, b = sorted((sign * n0, sign * n1))
    return box(a, b, t0, t1, z0, z1) if axis == 0 else box(t0, t1, a, b, z0, z1)


def build(height, clearance):
    H = height
    floor_z = FLOOR_T
    stack_z = H - clearance - floor_z     # the base below this line drops into the tote underneath
    half = (L / 2, W / 2)
    wall = (WALL[0] / 2, WALL[1] / 2)
    z_skirt = H - BUMPER_H               # underside of the bumper skirt
    z_deck = H - DECK_T                  # underside of the bumper deck
    grip_bottom = z_skirt - GRIP_H - T

    # Shell: beveled base up to the stacking line, then vertical walls to the top.
    tote = ruled_loft(BASE_OUT, BEVEL_TOP, 0, stack_z).union(slab(*WALL, stack_z, H))

    # Continuous bumper: full-footprint deck with a skirt turned down around the outside.
    tote = tote.union(slab(L, W, C, z_deck, H))
    skirt = slab(L, W, C, z_skirt, H).cut(slab(L - 2 * T, W - 2 * T, C - 0.06, z_skirt - 1, H + 1))
    tote = tote.union(skirt)

    # Belt rib at the stacking line. It also closes the step between the bevel and the wall.
    belt = slab(*BELT, stack_z - 0.1, stack_z + BELT_H).cut(
        slab(BEVEL_TOP[0] - 0.3, BEVEL_TOP[1] - 0.3, 0.35, stack_z - 1, H))
    tote = tote.union(belt)

    # Vertical external ribs from the belt to the bumper deck.
    def rib(axis, sign, t_pos, z0, z1):
        return orient(axis, sign, wall[axis] - 0.05, half[axis] - 0.02, t_pos - RIB_T / 2, t_pos + RIB_T / 2, z0, z1)

    for axis, sign in faces():
        for p in (X_FACE_RIBS if axis == 0 else Y_FACE_RIBS):
            z1 = grip_bottom + 0.02 if p == 0.0 else z_deck + 0.02   # centre rib carries the handle
            tote = tote.union(rib(axis, sign, p, stack_z, z1))

    # Corner ribs on the diagonals. Wall and bumper use the same chamfer, so their chamfer
    # faces are parallel and centred on one diagonal; each rib bridges the gap between them.
    gap = (half[0] - wall[0]) * math.sqrt(2)
    for sx in (1, -1):
        for sy in (1, -1):
            m = cq.Vector(sx * (wall[0] - C / 2), sy * (wall[1] - C / 2), 0)
            rib_c = (cq.Workplane("XY").box(gap + 0.03, RIB_T, z_deck + 0.02 - stack_z)
                     .translate(((gap - 0.07) / 2, 0, (stack_z + z_deck + 0.02) / 2))
                     .rotate((0, 0, 0), (0, 0, 1), math.degrees(math.atan2(sy, sx)))
                     .translate(m))
            tote = tote.union(rib_c)

    # Inner cavity: bevel inside the base, vertical above. A small shelf is left at the
    # stacking line where the two meet.
    inner_wall = (WALL[0] - 2 * T, WALL[1] - 2 * T, C - 0.06)
    bevel_in = (BEVEL_TOP[0] - 2 * T, BEVEL_TOP[1] - 2 * T, BEVEL_TOP[2] - 0.06)
    cavity = ruled_loft(BOTTOM_IN, bevel_in, floor_z, stack_z + 0.001)
    cavity = cavity.union(slab(*inner_wall, stack_z, H + 0.01))
    tote = tote.cut(cavity)

    # Fingertip handles on all four sides: a housing that bulges into the bin, a rounded
    # finger pocket under the bumper deck, and drain slots through the pocket floor.
    for axis, sign in faces():
        w = GRIP["x"] if axis == 0 else GRIP["y"]
        n_back = wall[axis] - T - GRIP_BACK
        housing = orient(axis, sign, n_back - T, half[axis] - 0.02, -w / 2 - T, w / 2 + T, grip_bottom, z_deck + 0.01)
        tote = tote.union(housing)
        pocket = orient(axis, sign, n_back, half[axis] + 0.5, -w / 2, w / 2, grip_bottom + T, z_deck)
        tote = tote.cut(pocket)
        n_mid = (n_back + half[axis]) / 2
        for tp in (-w / 3, 0.0, w / 3):
            slot = orient(axis, sign, n_mid - DRAIN[1] / 2, n_mid + DRAIN[1] / 2,
                          tp - DRAIN[0] / 2, tp + DRAIN[0] / 2, grip_bottom - 0.1, grip_bottom + T + 0.05)
            tote = tote.cut(slot)

    # Drain notches in the bumper skirt between the ribs.
    for axis, sign in faces():
        for tp in ((-4.5, 4.5) if axis == 0 else (-3.8, 3.8)):
            tote = tote.cut(orient(axis, sign, half[axis] - T - 0.05, half[axis] + 0.05, tp - 0.2, tp + 0.2,
                                   z_skirt - 0.01, z_skirt + 0.12))

    # Label pads on the 15" sides: a thin raised flat panel (texture left off to keep the mesh light).
    pad_z0, pad_z1 = stack_z + BELT_H + 0.3, grip_bottom - 0.25
    if pad_z1 - pad_z0 > 0.8:
        for sign in (1, -1):
            tote = tote.union(orient(1, sign, wall[1] - 0.01, wall[1] + PAD_T, -PAD_W / 2, PAD_W / 2, pad_z0, pad_z1))

    return tote.val().scale(IN)  # inches -> mm


if __name__ == "__main__":
    out = Path(__file__).parent / "models"
    out.mkdir(exist_ok=True)
    for name, p in MODELS.items():
        solid = build(p["height"], p["clearance"])
        cq.exporters.export(solid, str(out / f"{name}.step"))
        cq.exporters.export(solid, str(out / f"{name}.stl"), tolerance=0.5, angularTolerance=0.5)
        verts, _ = solid.tessellate(0.05)  # OCCT bounding boxes can be loose
        size = [(max(getattr(v, a) for v in verts) - min(getattr(v, a) for v in verts)) / IN for a in "xyz"]
        vol = solid.Volume() / IN**3
        print(f"{name}: {size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f} in, valid={solid.isValid()}, "
              f"volume={vol:.1f} in^3, est. weight {vol * HDPE:.2f} lb (spec {p['weight']} lb)")
