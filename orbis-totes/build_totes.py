"""Parametric 3D models of ORBIS Stakpak straight-wall totes NXO1215-5 and NXO1215-7.

Published specs (ORBIS / distributors):
  NXO1215-5: outside 12" L x 15" W x 5" H,   inside bottom 9.4" x 13", product clearance 4.4", 1.8 lb
  NXO1215-7: outside 12" L x 15" W x 7.5" H, inside bottom 9.4" x 13", product clearance 6.8", 2.3 lb

Everything else (rim, ribs, stacking foot, hand grips, label pads, fillets) is an
approximation of the molded part, not ORBIS CAD data. Output is in millimetres.

Usage: python build_totes.py   -> writes STEP + STL for each model into ./models
"""
from pathlib import Path

import cadquery as cq

IN = 25.4  # mm per inch

# Shared geometry (inches). X = 12" length, Y = 15" width, Z = height.
L, W = 12.0, 15.0
CORNER_R = 0.5          # outside vertical corner radius
RIM_H = 0.45            # full-size top rim band
BODY_INSET = 0.08       # body wall sits this far inside the rim (ribs come back out)
FOOT_H = 0.25           # stacking foot that drops into the tote below
TOP_OPEN = (10.4, 14.0) # inside opening at the rim
BOTTOM_IN = (9.4, 13.0) # inside floor (published)
FOOT = (TOP_OPEN[0] - 0.12, TOP_OPEN[1] - 0.12)
CAVITY_R = 0.6
RIB_T = 0.25
GRIP_W, GRIP_H, GRIP_D = 5.5, 1.0, 0.4
LABEL_W, LABEL_H, LABEL_D = 5.0, 2.0, 0.04

MODELS = {
    "NXO1215-5": {"height": 5.0, "clearance": 4.4},
    "NXO1215-7": {"height": 7.5, "clearance": 6.8},
}


def rounded_box(x, y, z, r, z0=0.0):
    return (
        cq.Workplane("XY").workplane(offset=z0)
        .rect(x, y).extrude(z)
        .edges("|Z").fillet(r)
    )


def rounded_rect_wire(x, y, r, z):
    return cq.Workplane("XY").workplane(offset=z).sketch().rect(x, y).vertices().fillet(r).finalize()


def build(height, clearance):
    H = height
    floor_z = H - clearance - FOOT_H  # stacked tote's foot eats FOOT_H of the opening
    body_h = H - RIM_H - FOOT_H

    rim = rounded_box(L, W, RIM_H, CORNER_R, H - RIM_H)
    body = rounded_box(L - 2 * BODY_INSET, W - 2 * BODY_INSET, body_h, CORNER_R - BODY_INSET, FOOT_H)
    foot = rounded_box(*FOOT, FOOT_H, CORNER_R)
    tote = rim.union(body).union(foot)

    # Vertical stiffening ribs, flush with the rim.
    for xr in (-3.5, 3.5):
        for sy in (-1, 1):
            rib = cq.Workplane("XY").box(RIB_T, BODY_INSET + 0.05, body_h, centered=(True, True, False)) \
                .translate((xr, sy * (W / 2 - (BODY_INSET + 0.05) / 2), FOOT_H))
            tote = tote.union(rib)
    for yr in (-4.5, 4.5):
        for sx in (-1, 1):
            rib = cq.Workplane("XY").box(BODY_INSET + 0.05, RIB_T, body_h, centered=(True, True, False)) \
                .translate((sx * (L / 2 - (BODY_INSET + 0.05) / 2), yr, FOOT_H))
            tote = tote.union(rib)

    # Drafted inner cavity: published floor size up to the rim opening.
    cavity = (
        cq.Workplane("XY").workplane(offset=floor_z)
        .rect(*BOTTOM_IN)
        .workplane(offset=H - floor_z + 0.01)
        .rect(*TOP_OPEN)
        .loft()
    )
    vertical_edges = [e for e in cavity.edges().vals()
                      if abs(e.startPoint().z - e.endPoint().z) > 1e-6]
    cavity = cavity.newObject(vertical_edges).fillet(CAVITY_R)
    cavity = cavity.faces("<Z").edges().fillet(0.15)
    tote = tote.cut(cavity)

    # Hand-grip pockets under the rim on the 15" end walls.
    for sx in (-1, 1):
        grip = cq.Workplane("XY").box(GRIP_D * 2, GRIP_W, GRIP_H, centered=True) \
            .edges("|X").fillet(0.3) \
            .translate((sx * (L / 2 - BODY_INSET), 0, H - RIM_H - GRIP_H / 2))
        tote = tote.cut(grip)

    # Shallow label pads on the 12" side walls.
    label_z = FOOT_H + body_h * 0.45
    for sy in (-1, 1):
        label = cq.Workplane("XY").box(LABEL_W, LABEL_D * 2, LABEL_H, centered=True) \
            .edges("|Y").fillet(0.15) \
            .translate((0, sy * (W / 2 - BODY_INSET), label_z))
        tote = tote.cut(label)

    return tote.val().scale(IN)  # inches -> mm


if __name__ == "__main__":
    out = Path(__file__).parent / "models"
    out.mkdir(exist_ok=True)
    for name, p in MODELS.items():
        solid = build(p["height"], p["clearance"])
        cq.exporters.export(solid, str(out / f"{name}.step"))
        cq.exporters.export(solid, str(out / f"{name}.stl"), tolerance=0.1, angularTolerance=0.1)
        verts, _ = solid.tessellate(0.05)  # OCCT bounding boxes are loose on filleted faces
        size = [(max(getattr(v, a) for v in verts) - min(getattr(v, a) for v in verts)) / IN for a in "xyz"]
        print(f"{name}: {size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f} in, "
              f"valid={solid.isValid()}, volume={solid.Volume()/IN**3:.1f} in^3")
