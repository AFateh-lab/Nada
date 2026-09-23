"""Plain geometry containers passed from the DXF reader to the Concept builder.

All coordinates are in model units (metres for SI, feet for US) after the
``cad_to_model_scale`` factor has been applied.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from typing import List, Optional, Tuple

Point = Tuple[float, float]


@dataclass
class SlabArea:
    points: List[Point]
    thickness: float
    concrete: str
    toc: float
    priority: int
    source: str = ""          # CAD handle / layer for error messages


@dataclass
class SlabOpening:
    points: List[Point]
    priority: int
    source: str = ""


@dataclass
class DropPanel:
    points: List[Point]
    thickness: float
    concrete: str
    priority: int
    source: str = ""


@dataclass
class Column:
    centre: Point
    b: float
    d: float
    angle_deg: float
    height: float
    concrete: str
    below_slab: bool
    above_slab: bool
    fixed_near: bool
    fixed_far: bool
    source: str = ""


@dataclass
class Wall:
    start: Point
    end: Point
    thickness: float
    height: float
    concrete: str
    below_slab: bool
    above_slab: bool
    source: str = ""


@dataclass
class Beam:
    start: Point
    end: Point
    width: float
    thickness: float
    concrete: str
    priority: int
    source: str = ""


@dataclass
class Structure:
    slabs: List[SlabArea] = field(default_factory=list)
    openings: List[SlabOpening] = field(default_factory=list)
    drop_panels: List[DropPanel] = field(default_factory=list)
    columns: List[Column] = field(default_factory=list)
    walls: List[Wall] = field(default_factory=list)
    beams: List[Beam] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)   # entities ignored, with reason

    def counts(self) -> dict:
        return {
            "slabs": len(self.slabs),
            "openings": len(self.openings),
            "drop_panels": len(self.drop_panels),
            "columns": len(self.columns),
            "walls": len(self.walls),
            "beams": len(self.beams),
            "skipped": len(self.skipped),
        }

    def to_json(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(asdict(self), fh, indent=2)


# --------------------------------------------------------------------------
# Small helpers shared by the extractor and validator
# --------------------------------------------------------------------------

def dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def clean_ring(points: List[Point], tol: float) -> List[Point]:
    """Drop duplicate / near-duplicate consecutive vertices and a closing
    vertex that repeats the first one. Returns an open ring (first != last)."""
    out: List[Point] = []
    for p in points:
        if not out or dist(out[-1], p) > tol:
            out.append(p)
    while len(out) > 1 and dist(out[0], out[-1]) <= tol:
        out.pop()
    # remove collinear intermediate vertices
    if len(out) >= 3:
        keep: List[Point] = []
        n = len(out)
        for i in range(n):
            a, b, c = out[i - 1], out[i], out[(i + 1) % n]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if abs(cross) > tol * tol:
                keep.append(b)
        out = keep
    return out


def rectangle_axes(points: List[Point]) -> Optional[Tuple[Point, float, float, float]]:
    """If ``points`` is a 4-vertex parallelogram close to a rectangle, return
    (centre, length_along_first_edge, width, angle_deg). Otherwise None."""
    if len(points) != 4:
        return None
    p0, p1, p2, p3 = points
    e1 = (p1[0] - p0[0], p1[1] - p0[1])
    e2 = (p3[0] - p0[0], p3[1] - p0[1])
    l1, l2 = math.hypot(*e1), math.hypot(*e2)
    if l1 == 0 or l2 == 0:
        return None
    cos = (e1[0] * e2[0] + e1[1] * e2[1]) / (l1 * l2)
    if abs(cos) > 0.05:          # ~87 deg or worse: not a rectangle
        return None
    cx = sum(p[0] for p in points) / 4
    cy = sum(p[1] for p in points) / 4
    angle = math.degrees(math.atan2(e1[1], e1[0]))
    return (cx, cy), l1, l2, angle


def rectangle_centreline(points: List[Point]) -> Optional[Tuple[Point, Point, float]]:
    """Centreline of a rectangular outline along its long axis.
    Returns (start, end, thickness) or None."""
    rect = rectangle_axes(points)
    if rect is None:
        return None
    (cx, cy), l1, l2, angle = rect
    if l1 >= l2:
        length, thick, ang = l1, l2, math.radians(angle)
    else:
        length, thick, ang = l2, l1, math.radians(angle + 90.0)
    dx, dy = math.cos(ang) * length / 2, math.sin(ang) * length / 2
    return (cx - dx, cy - dy), (cx + dx, cy + dy), thick
