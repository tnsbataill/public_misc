"""Parametric 3D models of ORBIS Stakpak straight-wall totes NXO1215-5 and NXO1215-7.

Published specs (ORBIS / distributors):
  NXO1215-5: outside 12" L x 15" W x 5" H,   inside bottom 9.4" x 13", product clearance 4.4", 1.8 lb
  NXO1215-7: outside 12" L x 15" W x 7.5" H, inside bottom 9.4" x 13", product clearance 6.8", 2.3 lb
  Features: reinforced external ribbing, fingertip handles, molded-in continuous bumper,
  textured label areas, drain holes in the bumper and handles.

The part is modeled as a thin-wall HDPE molding: a drafted inner bin, a top bumper channel
(open underneath), a stacking foot band, tapered external ribs that tie the foot to the
bumper, fingertip handle pockets on all four sides, and textured label pads on the 15" sides.
Feature sizes not in the spec sheet are estimates, not ORBIS CAD data. Output is in millimetres.

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
BOTTOM_IN = (9.4, 13.0, 0.6)   # inside floor L, W, corner radius (published size)
TOP_IN = (10.5, 14.1, 0.75)    # inside opening at the rim
CORNER_R = 0.6                 # bumper outside corner radius

BUMPER_H = 0.55       # continuous bumper: deck plus downturned skirt
DECK_T = 0.13
FOOT = (10.3, 13.9, 0.6)       # stacking foot band, drops inside the rim of the tote below
FOOT_H = 0.3

RIB_T = 0.12
RIB_LAND = 0.2        # rib toe sticks out past the foot so the ribs land on the lower tote's bumper
X_FACE_RIBS = (-5.6, -3.7, 0.0, 3.7, 5.6)   # y positions on the 12"-wide ends (0 runs under the handle)
Y_FACE_RIBS = (-3.3, 3.3)                     # x positions on the 15"-long sides

GRIP = {"x": 5.5, "y": 5.0}   # fingertip handle width on the X faces / Y faces
GRIP_H = 0.75         # finger opening height below the bumper skirt
GRIP_BACK = (0.0, 0.15)  # how far the pocket reaches behind the wall line (ends, sides)
DRAIN = (0.5, 0.14)   # drain slot length x width

PAD_W, PAD_T = 4.6, 0.035      # textured label pad on the Y faces
GROOVE_PITCH, GROOVE_H, GROOVE_D = 0.1, 0.04, 0.02

MODELS = {
    "NXO1215-5": {"height": 5.0, "clearance": 4.4, "weight": 1.8},
    "NXO1215-7": {"height": 7.5, "clearance": 6.8, "weight": 2.3},
}


def rr_slab(x, y, r, z0, z1):
    return cq.Workplane("XY").workplane(offset=z0).sketch().rect(x, y).vertices().fillet(r).finalize().extrude(z1 - z0)


def rr_loft(bottom, top, z0, z1):
    s0 = cq.Sketch().rect(bottom[0], bottom[1]).vertices().fillet(bottom[2])
    s1 = cq.Sketch().rect(top[0], top[1]).vertices().fillet(top[2])
    return cq.Workplane("XY").placeSketch(
        s0.moved(cq.Location(cq.Vector(0, 0, z0))), s1.moved(cq.Location(cq.Vector(0, 0, z1)))
    ).loft()


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
    floor_z = H - clearance - FOOT_H      # a stacked tote's foot takes FOOT_H of the opening
    depth = H - floor_z
    slope = [(TOP_IN[i] - BOTTOM_IN[i]) / 2 / depth for i in (0, 1)]

    def wall_out(axis, z):
        """Outer surface of the drafted wall, as distance from centre."""
        return BOTTOM_IN[axis] / 2 + T + slope[axis] * (z - floor_z)

    half = (L / 2, W / 2)
    z_skirt = H - BUMPER_H               # underside of the bumper skirt
    z_deck = H - DECK_T                  # underside of the bumper deck

    # Drafted bin: outer loft minus the cavity loft leaves walls of T and a floor of FLOOR_T.
    zb = floor_z - FLOOR_T
    outer_b = tuple(wall_out(i, zb) * 2 for i in (0, 1)) + (BOTTOM_IN[2] + T,)
    outer_t = tuple(wall_out(i, H) * 2 for i in (0, 1)) + (TOP_IN[2] + T,)
    tote = rr_loft(outer_b, outer_t, zb, H)

    # Continuous bumper: full-footprint deck with a skirt turned down around the outside.
    tote = tote.union(rr_slab(L, W, CORNER_R, z_deck, H))
    skirt = rr_slab(L, W, CORNER_R, z_skirt, H).cut(rr_slab(L - 2 * T, W - 2 * T, CORNER_R - T, z_skirt - 1, H + 1))
    tote = tote.union(skirt)

    # Stacking foot: a band of wall around the base, capped by a deck that ties into the bin.
    foot = rr_slab(*FOOT[:2], FOOT[2], 0, FOOT_H).cut(
        rr_slab(FOOT[0] - 2 * T, FOOT[1] - 2 * T, FOOT[2] - T, -1, FOOT_H - T))
    tote = tote.union(foot)

    # Underside grid ribs under the floor.
    grid = None
    fx, fy = FOOT[0] / 2 - T, FOOT[1] / 2 - T
    for gx in (-3.0, 0.0, 3.0):
        g = box(gx - 0.05, gx + 0.05, -fy, fy, 0, FOOT_H - T + 0.01)
        grid = g if grid is None else grid.union(g)
    for gy in (-4.5, -1.5, 1.5, 4.5):
        grid = grid.union(box(-fx, fx, gy - 0.05, gy + 0.05, 0, FOOT_H - T + 0.01))
    tote = tote.union(grid)

    # Tapered external ribs from the foot to the bumper. The toe overhangs the foot so a
    # stacked tote rests on the bumper deck of the one below.
    grip_bottom = z_skirt - GRIP_H - T

    def rib(axis, sign, t_pos, z_top, out_top):
        z0 = FOOT_H - 0.01
        n_in0, n_in1 = wall_out(axis, z0) - 0.05, wall_out(axis, z_top) - 0.05
        n_out0 = FOOT[axis] / 2 + RIB_LAND
        pts = [(n_in0, z0), (n_out0, z0), (out_top, z_top), (n_in1, z_top)]
        pts = [(sign * n, z) for n, z in pts]
        plane = "XZ" if axis == 0 else "YZ"
        r = cq.Workplane(plane).polyline(pts).close().extrude(RIB_T / 2, both=True)
        return r.translate((0, t_pos, 0) if axis == 0 else (t_pos, 0, 0))

    for axis, sign in faces():
        positions = X_FACE_RIBS if axis == 0 else Y_FACE_RIBS
        for p in positions:
            if p == 0.0:   # short rib that carries the handle housing
                tote = tote.union(rib(axis, sign, p, grip_bottom + 0.02, half[axis] - 0.02))
            else:
                tote = tote.union(rib(axis, sign, p, z_deck + 0.02, half[axis] - 0.02))

    # Corner ribs on the diagonals. The wall corners all lie in one vertical plane per corner
    # (draft is equal on both axes), so each rib is drawn in that plane.
    r0, r1 = BOTTOM_IN[2] + T, TOP_IN[2] + T
    k = 1 - 1 / math.sqrt(2)

    def corner_pt(z, sx, sy):
        r = r0 + (r1 - r0) * (z - zb) / (H - zb)
        return cq.Vector(sx * (wall_out(0, z) - r * k), sy * (wall_out(1, z) - r * k), 0)

    for sx in (1, -1):
        for sy in (1, -1):
            u = cq.Vector(sx, sy, 0).normalized()
            z0, z1 = FOOT_H - 0.01, z_deck + 0.02
            q = corner_pt(0, sx, sy)
            s_of = lambda pt: (pt - q).dot(u)
            foot_c = cq.Vector(sx * (FOOT[0] / 2 - FOOT[2] * k), sy * (FOOT[1] / 2 - FOOT[2] * k), 0)
            bump_c = cq.Vector(sx * (L / 2 - CORNER_R * k), sy * (W / 2 - CORNER_R * k), 0)
            pts = [(s_of(corner_pt(z0, sx, sy)) - 0.05, z0), (s_of(foot_c) + RIB_LAND, z0),
                   (s_of(bump_c) - 0.1, z1), (s_of(corner_pt(z1, sx, sy)) - 0.05, z1)]
            plane = cq.Plane(origin=q, xDir=u, normal=u.cross(cq.Vector(0, 0, 1)))
            tote = tote.union(cq.Workplane(plane).polyline(pts).close().extrude(RIB_T / 2, both=True))

    # Inner cavity.
    cavity = rr_loft(BOTTOM_IN, TOP_IN, floor_z, H + 0.01)
    try:
        cavity = cavity.faces("<Z").edges().fillet(0.15)
    except Exception:
        pass
    tote = tote.cut(cavity)

    # Fingertip handles on all four sides: a housing that bulges into the bin, a rounded
    # finger pocket under the bumper deck, and drain slots through the pocket floor.
    for axis, sign in faces():
        w = GRIP["x"] if axis == 0 else GRIP["y"]
        n_back = wall_out(axis, z_deck) - T - GRIP_BACK[axis]
        housing = orient(axis, sign, n_back - T, half[axis] - 0.02, -w / 2 - T, w / 2 + T, grip_bottom, z_deck + 0.01)
        tote = tote.union(housing)
        pocket = orient(axis, sign, n_back, half[axis] + 0.5, -w / 2, w / 2, grip_bottom + T, z_deck)
        try:
            pocket = pocket.edges("|X" if axis == 0 else "|Y").fillet(0.3)
        except Exception:
            pass
        tote = tote.cut(pocket)
        n_mid = (n_back + half[axis]) / 2
        for tp in (-w / 3, 0.0, w / 3):
            slot = orient(axis, sign, n_mid - DRAIN[1] / 2, n_mid + DRAIN[1] / 2,
                          tp - DRAIN[0] / 2, tp + DRAIN[0] / 2, grip_bottom - 0.1, grip_bottom + T + 0.05)
            tote = tote.cut(slot)

    # Drain notches in the bumper skirt at each corner run.
    for axis, sign in faces():
        for tp in ((-4.6, 4.6) if axis == 0 else (-4.8, 4.8)):
            tote = tote.cut(orient(axis, sign, half[axis] - T - 0.05, half[axis] + 0.05, tp - 0.2, tp + 0.2,
                                   z_skirt - 0.01, z_skirt + 0.12))

    # Textured label pads on the 15" sides: a thin raised panel following the wall draft,
    # with fine horizontal grooves for the label-release texture.
    pad_z0, pad_z1 = FOOT_H + 0.35, grip_bottom - 0.3
    if pad_z1 - pad_z0 > 0.8:
        grown = rr_loft((outer_b[0] + 2 * PAD_T, outer_b[1] + 2 * PAD_T, outer_b[2] + PAD_T),
                        (outer_t[0] + 2 * PAD_T, outer_t[1] + 2 * PAD_T, outer_t[2] + PAD_T), zb, H)
        for sign in (1, -1):
            region = orient(1, sign, 0, half[1], -PAD_W / 2, PAD_W / 2, pad_z0, pad_z1)
            pad = grown.intersect(region).cut(rr_loft(outer_b, outer_t, zb, H))
            grooves = None
            z = pad_z0 + 0.12
            while z < pad_z1 - 0.12:
                n = wall_out(1, z) + PAD_T - GROOVE_D
                g = orient(1, sign, n, n + 0.2, -PAD_W / 2 + 0.12, PAD_W / 2 - 0.12, z - GROOVE_H / 2, z + GROOVE_H / 2)
                grooves = g if grooves is None else grooves.union(g)
                z += GROOVE_PITCH
            tote = tote.union(pad.cut(grooves))

    return tote.val().scale(IN)  # inches -> mm


if __name__ == "__main__":
    out = Path(__file__).parent / "models"
    out.mkdir(exist_ok=True)
    for name, p in MODELS.items():
        solid = build(p["height"], p["clearance"])
        cq.exporters.export(solid, str(out / f"{name}.step"))
        cq.exporters.export(solid, str(out / f"{name}.stl"), tolerance=0.05, angularTolerance=0.1)
        verts, _ = solid.tessellate(0.05)  # OCCT bounding boxes are loose on filleted faces
        size = [(max(getattr(v, a) for v in verts) - min(getattr(v, a) for v in verts)) / IN for a in "xyz"]
        vol = solid.Volume() / IN**3
        print(f"{name}: {size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f} in, valid={solid.isValid()}, "
              f"volume={vol:.1f} in^3, est. weight {vol * HDPE:.2f} lb (spec {p['weight']} lb)")
