"""Run with:  python -m pytest tests -q   (from the ram_mesh_import folder)"""

import sys
from pathlib import Path

import ezdxf
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))

from make_sample_dxf import build  # noqa: E402
from ram_mesh_import.config import Config  # noqa: E402
from ram_mesh_import.extract import read_structure  # noqa: E402
from ram_mesh_import.validate import validate  # noqa: E402


@pytest.fixture
def sample(tmp_path):
    return build(tmp_path / "sample.dxf")


def test_sample_extracts_everything(sample):
    st = read_structure(sample, Config())
    assert st.counts() == {"slabs": 1, "openings": 2, "drop_panels": 2,
                           "columns": 12, "walls": 3, "beams": 2, "skipped": 1}
    assert st.slabs[0].points[1] == (24.0, 0.0)          # mm -> m
    rot = [c for c in st.columns if c.angle_deg > 1][0]
    assert (round(rot.b, 2), round(rot.d, 2), round(rot.angle_deg)) == (0.6, 0.3, 30)
    w = st.walls[0]
    assert round(w.thickness, 3) == 0.2 and round(w.start[0], 3) == 2.9


def test_sample_validates_clean(sample):
    cfg = Config()
    rep = validate(read_structure(sample, cfg), cfg)
    assert rep.ok
    assert all("skipped TEXT" in w for w in rep.warnings)


def test_layer_matching_is_case_insensitive_and_wildcard(tmp_path):
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (5000, 0), (5000, 5000), (0, 5000)], close=True,
                       dxfattribs={"layer": "bbr-slabs"})
    msp.add_lwpolyline([(1000, 1000), (1400, 1000), (1400, 1400), (1000, 1400)], close=True,
                       dxfattribs={"layer": "BBR-COLUMNS-LEVEL3"})
    p = tmp_path / "t.dxf"
    doc.saveas(p)
    cfg = Config.from_dict({"layers": {"column": ["BBR-Columns*"]}})
    st = read_structure(p, cfg)
    assert len(st.slabs) == 1 and len(st.columns) == 1


def test_open_slab_polyline_is_rejected(tmp_path):
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (5000, 0), (5000, 5000), (0, 5000)], close=False,
                       dxfattribs={"layer": "BBR-Slabs"})
    p = tmp_path / "t.dxf"
    doc.saveas(p)
    cfg = Config()
    st = read_structure(p, cfg)
    assert not st.slabs and st.skipped
    rep = validate(st, cfg)
    assert not rep.ok and "no slab areas" in rep.errors[0]


def test_overlapping_slabs_and_duplicate_columns_are_errors(tmp_path):
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    for x in (0, 3000):
        msp.add_lwpolyline([(x, 0), (x + 5000, 0), (x + 5000, 5000), (x, 5000)], close=True,
                           dxfattribs={"layer": "BBR-Slabs"})
    for _ in range(2):
        msp.add_circle((1000, 1000), 200, dxfattribs={"layer": "BBR-Columns"})
    p = tmp_path / "t.dxf"
    doc.saveas(p)
    cfg = Config()
    rep = validate(read_structure(p, cfg), cfg)
    assert any("overlaps" in e for e in rep.errors)
    assert any("duplicates" in e for e in rep.errors)


def test_self_intersecting_opening_is_error(tmp_path):
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (9000, 0), (9000, 9000), (0, 9000)], close=True,
                       dxfattribs={"layer": "BBR-Slabs"})
    msp.add_lwpolyline([(1000, 1000), (3000, 3000), (3000, 1000), (1000, 3000)], close=True,
                       dxfattribs={"layer": "BBR-Opening"})
    p = tmp_path / "t.dxf"
    doc.saveas(p)
    cfg = Config()
    rep = validate(read_structure(p, cfg), cfg)
    assert any("self-intersecting" in e for e in rep.errors)


def test_column_outside_slab_is_warning(tmp_path):
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (9000, 0), (9000, 9000), (0, 9000)], close=True,
                       dxfattribs={"layer": "BBR-Slabs"})
    msp.add_point((20000, 20000), dxfattribs={"layer": "BBR-Columns"})
    p = tmp_path / "t.dxf"
    doc.saveas(p)
    cfg = Config()
    rep = validate(read_structure(p, cfg), cfg)
    assert rep.ok and any("not under any slab" in w for w in rep.warnings)


def test_wall_from_open_polyline_and_arcs(tmp_path):
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (9000, 0), (9000, 9000), (0, 9000)], close=True,
                       dxfattribs={"layer": "BBR-Slabs"})
    msp.add_lwpolyline([(1000, 1000), (5000, 1000), (5000, 4000)], dxfattribs={"layer": "BBR-Walls"})
    # slab edge with a bulge (arc) on the opening layer
    msp.add_lwpolyline([(6000, 6000, 0, 0, 1.0), (8000, 6000, 0, 0, 0), (8000, 8000, 0, 0, 0)],
                       format="xyseb", close=True, dxfattribs={"layer": "BBR-Opening"})
    p = tmp_path / "t.dxf"
    doc.saveas(p)
    cfg = Config()
    st = read_structure(p, cfg)
    assert len(st.walls) == 2 and st.walls[0].thickness == cfg.wall.thickness
    assert len(st.openings) == 1 and len(st.openings[0].points) > 4   # arc flattened


def test_config_rejects_unknown_keys():
    with pytest.raises(KeyError):
        Config.from_dict({"slab": {"thicknes": 0.3}})
