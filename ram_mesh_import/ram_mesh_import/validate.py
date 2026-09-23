"""Geometry checks run before anything is sent to RAM Concept.

Every problem found here would otherwise surface as a failed or ugly mesh
in Concept, where it is much harder to trace back to the CAD object.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from shapely.geometry import LineString, Point as ShPoint, Polygon
from shapely.ops import unary_union

from .config import Config
from .geometry import Structure


@dataclass
class Report:
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def text(self) -> str:
        lines = []
        for e in self.errors:
            lines.append(f"ERROR   {e}")
        for w in self.warnings:
            lines.append(f"WARNING {w}")
        if not lines:
            lines.append("OK      no geometry problems found")
        return "\n".join(lines)


def _poly(points) -> Polygon:
    return Polygon(points)


def validate(st: Structure, cfg: Config) -> Report:
    rep = Report()
    tol = cfg.tolerance

    if not st.slabs:
        rep.errors.append("no slab areas found on the slab layer(s) "
                          f"{cfg.layers.slab}")

    # ---- closed polygons must be simple (no self-intersection) ------------
    slab_polys: List[Polygon] = []
    for name, items in (("slab", st.slabs), ("opening", st.openings),
                        ("drop panel", st.drop_panels)):
        for it in items:
            p = _poly(it.points)
            if not p.is_valid:
                rep.errors.append(f"{name} {it.source}: polygon is self-intersecting or degenerate")
                continue
            if p.area < (10 * tol) ** 2:
                rep.errors.append(f"{name} {it.source}: area is practically zero")
                continue
            if name == "slab":
                slab_polys.append(p)
            # sliver check: very short edges make bad mesh elements
            pts = it.points
            for a, b in zip(pts, pts[1:] + pts[:1]):
                if 0 < LineString([a, b]).length < 5 * tol:
                    rep.warnings.append(f"{name} {it.source}: edge shorter than {5 * tol:g} near {a}")
                    break

    # ---- slab areas must not overlap each other ---------------------------
    for i in range(len(slab_polys)):
        for j in range(i + 1, len(slab_polys)):
            inter = slab_polys[i].intersection(slab_polys[j])
            if inter.area > (10 * tol) ** 2:
                rep.errors.append(
                    f"slab {st.slabs[i].source} overlaps slab {st.slabs[j].source} "
                    f"(overlap area {inter.area:.3f}); use one outline plus openings")

    slab_union = unary_union(slab_polys) if slab_polys else None

    # ---- openings and drop panels should sit inside a slab ----------------
    if slab_union is not None:
        for name, items in (("opening", st.openings), ("drop panel", st.drop_panels)):
            for it in items:
                p = _poly(it.points)
                if not p.is_valid:
                    continue
                outside = p.difference(slab_union.buffer(tol)).area
                if outside > (10 * tol) ** 2:
                    rep.warnings.append(f"{name} {it.source}: extends outside every slab area")

        # ---- columns and walls should touch the slab ----------------------
        for c in st.columns:
            if slab_union.buffer(max(c.b, c.d) / 2 + tol).disjoint(ShPoint(c.centre)):
                rep.warnings.append(f"column {c.source} at {tuple(round(v, 3) for v in c.centre)} is not under any slab")
        for w in st.walls:
            if slab_union.buffer(w.thickness / 2 + tol).disjoint(LineString([w.start, w.end])):
                rep.warnings.append(f"wall {w.source} does not touch any slab")
        for b in st.beams:
            if slab_union.buffer(b.width / 2 + tol).disjoint(LineString([b.start, b.end])):
                rep.warnings.append(f"beam {b.source} does not touch any slab")

    # ---- duplicate columns ------------------------------------------------
    seen = []
    for c in st.columns:
        for other in seen:
            if abs(c.centre[0] - other.centre[0]) <= tol and abs(c.centre[1] - other.centre[1]) <= tol:
                rep.errors.append(f"column {c.source} duplicates column {other.source}")
                break
        seen.append(c)

    # ---- zero-length walls/beams -----------------------------------------
    for name, items in (("wall", st.walls), ("beam", st.beams)):
        for it in items:
            if LineString([it.start, it.end]).length <= tol:
                rep.errors.append(f"{name} {it.source}: zero length")

    for s in st.skipped:
        rep.warnings.append(f"skipped {s}")

    return rep
