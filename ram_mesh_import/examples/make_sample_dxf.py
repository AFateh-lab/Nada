"""Write examples/sample_level.dxf: a small floor drawn on the BBR layers
in millimetres, as an engineer would draw it (all polylines)."""

from pathlib import Path

import ezdxf

LAYERS = ["BBR-Slabs", "BBR-Opening", "BBR-Drop Panels", "BBR-Columns", "BBR-Walls", "BBR-Beams"]


def rect(msp, layer, x, y, w, h):
    msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)],
                       close=True, dxfattribs={"layer": layer})


def build(path: Path) -> Path:
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 4  # millimetres
    for name in LAYERS:
        doc.layers.add(name)
    msp = doc.modelspace()

    # L-shaped slab 24 m x 16 m with a notch
    msp.add_lwpolyline([(0, 0), (24000, 0), (24000, 10000), (16000, 10000),
                        (16000, 16000), (0, 16000)], close=True,
                       dxfattribs={"layer": "BBR-Slabs"})
    # stair opening and a lift shaft
    rect(msp, "BBR-Opening", 9000, 6000, 3000, 5000)
    rect(msp, "BBR-Opening", 3000, 12000, 2400, 2400)
    # columns on an 8 m grid, drawn as 400x400 squares
    for gx in (0, 8000, 16000, 24000):
        for gy in (0, 8000, 16000):
            if gx == 24000 and gy == 16000:
                continue
            rect(msp, "BBR-Columns", gx - 200, gy - 200, 400, 400)
    # one rotated rectangular column 600x300
    msp.add_lwpolyline([(20000, 3000), (20520, 3300), (20370, 3560), (19850, 3260)],
                       close=True, dxfattribs={"layer": "BBR-Columns"})
    # drop panels at two interior columns
    rect(msp, "BBR-Drop Panels", 8000 - 1500, 8000 - 1500, 3000, 3000)
    rect(msp, "BBR-Drop Panels", 16000 - 1500, 8000 - 1500, 3000, 3000)
    # lift shaft walls as 200 mm outlines
    rect(msp, "BBR-Walls", 2800, 11800, 200, 2800)
    rect(msp, "BBR-Walls", 5400, 11800, 200, 2800)
    rect(msp, "BBR-Walls", 3000, 14400, 2400, 200)
    # edge beam along the bottom as a polyline centreline
    msp.add_lwpolyline([(0, 0), (24000, 0)], dxfattribs={"layer": "BBR-Beams"})
    # a beam drawn as an outline (400 wide)
    rect(msp, "BBR-Beams", 15800, 10000, 400, 6000)
    # stray text that must be ignored
    msp.add_text("LEVEL 03", dxfattribs={"layer": "BBR-Slabs"}).set_placement((100, 100))

    doc.saveas(str(path))
    return path


if __name__ == "__main__":
    out = Path(__file__).with_name("sample_level.dxf")
    print(build(out))
