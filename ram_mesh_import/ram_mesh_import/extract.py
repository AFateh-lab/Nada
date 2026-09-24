"""Read a DXF and turn the BBR layers into a :class:`Structure`.

Rules applied per layer (all objects are expected to be polylines):

* BBR-Slabs        closed polyline  -> slab area
* BBR-Opening      closed polyline  -> slab opening
* BBR-Drop Panels  closed polyline  -> drop panel (thicker slab area)
* BBR-Columns      closed rectangle -> column at centre, size from rectangle
                   circle / point   -> column at centre, size from config
* BBR-Walls        closed rectangle -> wall along the long axis, thickness
                                       from the short side
                   open polyline    -> wall centreline, thickness from config
* BBR-Beams        open polyline    -> one beam per segment
                   closed rectangle -> beam along the long axis
"""

from __future__ import annotations

import fnmatch
import math
from pathlib import Path
from typing import Iterable, List, Optional

import ezdxf
from ezdxf.entities import DXFEntity

from .config import Config
from .geometry import (
    Beam,
    Column,
    DropPanel,
    Point,
    SlabArea,
    SlabOpening,
    Structure,
    Wall,
    clean_ring,
    dist,
    rectangle_axes,
    rectangle_centreline,
)

_CLOSED_TYPES = ("LWPOLYLINE", "POLYLINE")


def _layer_matches(layer: str, patterns: Iterable[str]) -> bool:
    layer_l = layer.lower()
    return any(fnmatch.fnmatchcase(layer_l, p.lower()) for p in patterns)


def _kind_for_layer(layer: str, cfg: Config) -> Optional[str]:
    lm = cfg.layers
    for kind, patterns in (
        ("slab", lm.slab),
        ("opening", lm.opening),
        ("drop_panel", lm.drop_panel),
        ("column", lm.column),
        ("wall_cl", lm.wall_centreline),
        ("wall", lm.wall),
        ("beam", lm.beam),
    ):
        if _layer_matches(layer, patterns):
            return kind
    return None


def _polyline_points(e: DXFEntity, scale: float) -> tuple[List[Point], bool]:
    """Vertices (scaled) and closed flag for LWPOLYLINE / POLYLINE / LINE."""
    t = e.dxftype()
    if t == "LWPOLYLINE":
        pts = [(float(x) * scale, float(y) * scale) for x, y, *_ in e.get_points()]
        return pts, bool(e.closed)
    if t == "POLYLINE":
        pts = [(v.dxf.location.x * scale, v.dxf.location.y * scale) for v in e.vertices]
        return pts, bool(e.is_closed)
    if t == "LINE":
        return (
            [(e.dxf.start.x * scale, e.dxf.start.y * scale),
             (e.dxf.end.x * scale, e.dxf.end.y * scale)],
            False,
        )
    raise TypeError(t)


def _has_arcs(e: DXFEntity) -> bool:
    if e.dxftype() == "LWPOLYLINE":
        return any(abs(b) > 1e-9 for *_, b in e.get_points(format="xyseb"))
    return False


def _flatten(e: DXFEntity, scale: float, seg_len_cad: float) -> tuple[List[Point], bool]:
    """Polyline with bulges -> straight segments."""
    from ezdxf.math import ConstructionArc, bulge_to_arc
    closed = bool(e.closed)
    raw = list(e.get_points(format="xyb"))
    if closed:
        raw.append(raw[0])
    pts: List[Point] = []
    for (x0, y0, bulge), (x1, y1, _) in zip(raw[:-1], raw[1:]):
        pts.append((float(x0) * scale, float(y0) * scale))
        if abs(bulge) > 1e-9:
            centre, start_a, end_a, radius = bulge_to_arc((x0, y0), (x1, y1), bulge)
            arc = ConstructionArc(centre, radius, math.degrees(start_a), math.degrees(end_a))
            n = max(2, int(abs(arc.angle_span) / 15.0))     # one vertex per 15 deg
            inner = [v for v in arc.vertices(arc.angles(n))]
            if bulge < 0:                                     # clockwise: walk backwards
                inner.reverse()
            for v in inner[1:-1]:
                pts.append((float(v.x) * scale, float(v.y) * scale))
    if not closed:
        pts.append((float(raw[-1][0]) * scale, float(raw[-1][1]) * scale))
    return pts, closed


def read_structure(dxf_path: str | Path, cfg: Config) -> Structure:
    doc = ezdxf.readfile(str(dxf_path))
    msp = doc.modelspace()
    scale = cfg.cad_to_model_scale
    tol = cfg.tolerance
    st = Structure()

    entities: List[DXFEntity] = []
    for e in msp:
        if e.dxftype() == "INSERT" and cfg.explode_blocks:
            # Explode into a virtual list so we do not modify the file.
            entities.extend(e.virtual_entities())
        else:
            entities.append(e)

    for e in entities:
        layer = e.dxf.layer
        kind = _kind_for_layer(layer, cfg)
        if kind is None:
            continue
        src = f"{e.dxftype()} {e.dxf.handle} on {layer}"
        t = e.dxftype()

        # ---- points / circles: columns only -------------------------------
        if t in ("CIRCLE", "POINT"):
            if kind != "column":
                st.skipped.append(f"{src}: {t} not allowed on this layer")
                continue
            c = e.dxf.center if t == "CIRCLE" else e.dxf.location
            st.columns.append(_column_from_point((c.x * scale, c.y * scale), src, cfg))
            continue

        if t not in (*_CLOSED_TYPES, "LINE"):
            st.skipped.append(f"{src}: unsupported entity type")
            continue

        if t == "LWPOLYLINE" and _has_arcs(e):
            pts, closed = _flatten(e, scale, max(tol / scale * 20, 1.0))
        else:
            pts, closed = _polyline_points(e, scale)

        if len(pts) >= 2 and dist(pts[0], pts[-1]) <= tol:
            closed = True

        if kind in ("slab", "opening", "drop_panel"):
            ring = clean_ring(pts, tol)
            if not closed or len(ring) < 3:
                st.skipped.append(f"{src}: must be a closed polyline with >= 3 vertices")
                continue
            if kind == "slab":
                st.slabs.append(SlabArea(ring, cfg.slab.thickness, cfg.slab.concrete,
                                         cfg.slab.toc, cfg.slab.priority, src))
            elif kind == "opening":
                st.openings.append(SlabOpening(ring, cfg.opening.priority, src))
            else:
                st.drop_panels.append(DropPanel(ring, cfg.drop_panel.thickness,
                                                cfg.drop_panel.concrete,
                                                cfg.drop_panel.priority, src))

        elif kind == "column":
            ring = clean_ring(pts, tol)
            rect = rectangle_axes(ring) if closed else None
            if rect and cfg.column.size_from_outline:
                (cx, cy), l1, l2, ang = rect
                st.columns.append(_column_from_point((cx, cy), src, cfg, b=l1, d=l2, angle=ang))
            elif closed and len(ring) >= 3:
                cx = sum(p[0] for p in ring) / len(ring)
                cy = sum(p[1] for p in ring) / len(ring)
                st.columns.append(_column_from_point((cx, cy), src, cfg))
                st.skipped.append(f"{src}: non-rectangular column outline, used centroid and default size")
            else:
                st.skipped.append(f"{src}: column must be a closed polyline, circle or point")

        elif kind == "wall":
            ring = clean_ring(pts, tol)
            cl = rectangle_centreline(ring) if closed else None
            if cl:
                start, end, thick = cl
                length = dist(start, end)
                if thick <= 0 or length / thick < cfg.wall.min_aspect_ratio:
                    st.skipped.append(f"{src}: outline too square to be a wall (aspect < {cfg.wall.min_aspect_ratio})")
                    continue
                st.walls.append(_wall(start, end, thick, src, cfg))
            elif not closed:
                for a, b in zip(pts[:-1], pts[1:]):
                    if dist(a, b) > tol:
                        st.walls.append(_wall(a, b, cfg.wall.thickness, src, cfg))
            else:
                st.skipped.append(f"{src}: closed wall outline is not a rectangle; draw its centreline instead")

        elif kind == "wall_cl":
            seq = pts + ([pts[0]] if closed else [])
            for a, b in zip(seq[:-1], seq[1:]):
                if dist(a, b) > tol:
                    st.walls.append(_wall(a, b, cfg.wall.thickness, src, cfg))

        elif kind == "beam":
            ring = clean_ring(pts, tol)
            cl = rectangle_centreline(ring) if closed else None
            if cl:
                start, end, width = cl
                st.beams.append(Beam(start, end, width, cfg.beam.thickness,
                                     cfg.beam.concrete, cfg.beam.priority, src))
            elif not closed:
                for a, b in zip(pts[:-1], pts[1:]):
                    if dist(a, b) > tol:
                        st.beams.append(Beam(a, b, cfg.beam.width, cfg.beam.thickness,
                                             cfg.beam.concrete, cfg.beam.priority, src))
            else:
                st.skipped.append(f"{src}: closed beam outline is not a rectangle; draw its centreline instead")

    return st


def _column_from_point(c: Point, src: str, cfg: Config, b: float | None = None,
                       d: float | None = None, angle: float = 0.0) -> Column:
    cc = cfg.column
    return Column(
        centre=c,
        b=b if b is not None else cc.b,
        d=d if d is not None else cc.d,
        angle_deg=angle,
        height=cc.height,
        concrete=cc.concrete,
        below_slab=cc.below_slab,
        above_slab=cc.above_slab,
        fixed_near=cc.fixed_near,
        fixed_far=cc.fixed_far,
        source=src,
    )


def _wall(start: Point, end: Point, thick: float, src: str, cfg: Config) -> Wall:
    return Wall(start, end, thick, cfg.wall.height, cfg.wall.concrete,
                cfg.wall.below_slab, cfg.wall.above_slab, src)


def list_layers(dxf_path: str | Path) -> List[str]:
    doc = ezdxf.readfile(str(dxf_path))
    return sorted(l.dxf.name for l in doc.layers)
