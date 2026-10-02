"""Convert models/*.stl (binary) to ASCII STL .txt files the viewer page can be published with."""
import struct
from pathlib import Path

here = Path(__file__).parent
for src in sorted((here.parent / "models").glob("*.stl")):
    d = src.read_bytes()
    count = struct.unpack("<I", d[80:84])[0]
    out = [f"solid {src.stem}"]
    for i in range(count):
        f = struct.unpack("<12f", d[84 + 50 * i:84 + 50 * i + 48])
        out.append(f" facet normal {f[0]:.4g} {f[1]:.4g} {f[2]:.4g}\n  outer loop")
        out += [f"   vertex {f[k]:.3f} {f[k+1]:.3f} {f[k+2]:.3f}" for k in (3, 6, 9)]
        out.append("  endloop\n endfacet")
    out.append(f"endsolid {src.stem}")
    (here / f"{src.stem}.stl.txt").write_text("\n".join(out) + "\n")
