"""Create the Mesh Input layer in RAM Concept from a :class:`Structure`.

Uses the ``ram_concept`` Python API shipped with RAM Concept CONNECT Edition
(install folder ``...\\RAM Concept\\python\\ram_concept``).  The API is only
importable on a Windows machine with RAM Concept installed, so this module
imports it lazily inside :func:`build_model`.

The exact attribute names differ slightly between Concept releases, so every
property is set through :func:`_set`, which logs a warning instead of
crashing when a name is not found.  Run once with ``--log-level DEBUG`` after
installing a new Concept version and fix any names listed in the log in the
``PROPERTY_NAMES`` table below.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from .config import Config
from .geometry import Structure

log = logging.getLogger(__name__)

# API attribute names.  Change here only, not in the code below.
PROPERTY_NAMES: Dict[str, Dict[str, str]] = {
    "slab": {
        "thickness": "thickness",
        "concrete": "concrete",
        "toc": "toc",
        "priority": "priority",
    },
    "opening": {"priority": "priority"},
    "drop_panel": {
        "thickness": "thickness",
        "concrete": "concrete",
        "priority": "priority",
    },
    "column": {
        "b": "b",
        "d": "d",
        "angle": "angle",
        "height": "height",
        "concrete": "concrete",
        "below_slab": "below_slab",
        "fixed_near": "fixed_near",
        "fixed_far": "fixed_far",
    },
    "wall": {
        "thickness": "thickness",
        "height": "height",
        "concrete": "concrete",
        "below_slab": "below_slab",
    },
    "beam": {
        "width": "width",
        "thickness": "thickness",
        "concrete": "concrete",
        "priority": "priority",
    },
}


def _set(obj: Any, kind: str, key: str, value: Any) -> None:
    name = PROPERTY_NAMES[kind].get(key, key)
    if hasattr(obj, name):
        try:
            setattr(obj, name, value)
            return
        except Exception as exc:  # noqa: BLE001 - report and continue
            log.warning("%s.%s = %r failed: %s", kind, name, value, exc)
            return
    log.warning("%s has no attribute %r (API version mismatch); value %r not set",
                kind, name, value)


def _concrete(model: Any, name: str, cache: Dict[str, Any]) -> Any:
    """Return the concrete mix called ``name``, creating it if needed."""
    if name in cache:
        return cache[name]
    concretes = model.concretes
    mix = None
    try:
        mix = concretes.concrete(name)
    except Exception:  # noqa: BLE001
        mix = None
    if mix is None:
        try:
            mix = concretes.add_concrete(name)
            log.warning("concrete mix %r did not exist and was created with default "
                        "properties; check its strength in Concept", name)
        except Exception as exc:  # noqa: BLE001
            log.warning("could not create concrete %r: %s; leaving material default", name, exc)
    cache[name] = mix
    return mix


def build_model(st: Structure, cfg: Config, out_path: str, headless: bool = True) -> None:
    from ram_concept.concept import Concept              # type: ignore
    from ram_concept.line_segment_2D import LineSegment2D  # type: ignore
    from ram_concept.point_2D import Point2D              # type: ignore
    from ram_concept.polygon_2D import Polygon2D          # type: ignore

    def P(pt):  # noqa: N802
        return Point2D(pt[0], pt[1])

    def poly(points):
        return Polygon2D([P(p) for p in points])

    def seg(a, b):
        return LineSegment2D(P(a), P(b))

    log.info("starting RAM Concept (headless=%s)", headless)
    concept = Concept.start_concept(headless=headless)
    try:
        model = concept.new_model()

        # Units. The API exposes an enum on model.units in recent versions.
        try:
            units = model.units
            target = getattr(units, cfg.units, None) or getattr(type(units), cfg.units, None)
            if target is not None:
                model.units = target
            else:
                log.warning("could not set unit system %r; set it in the template instead", cfg.units)
        except Exception as exc:  # noqa: BLE001
            log.warning("units not set: %s", exc)

        layer = model.cad_manager.structure_layer      # the Mesh Input layer
        mixes: Dict[str, Any] = {}

        for s in st.slabs:
            obj = layer.add_slab_area(poly(s.points))
            _set(obj, "slab", "thickness", s.thickness)
            _set(obj, "slab", "toc", s.toc)
            _set(obj, "slab", "priority", s.priority)
            _set(obj, "slab", "concrete", _concrete(model, s.concrete, mixes))

        for o in st.openings:
            obj = layer.add_slab_opening(poly(o.points))
            _set(obj, "opening", "priority", o.priority)

        for d in st.drop_panels:
            # Drop panels are modelled as a higher-priority slab area.
            obj = layer.add_slab_area(poly(d.points))
            _set(obj, "drop_panel", "thickness", d.thickness)
            _set(obj, "drop_panel", "priority", d.priority)
            _set(obj, "drop_panel", "concrete", _concrete(model, d.concrete, mixes))

        for c in st.columns:
            for below in ({True} if c.below_slab and not c.above_slab else
                          {False} if c.above_slab and not c.below_slab else {True, False}):
                obj = layer.add_column(P(c.centre))
                _set(obj, "column", "below_slab", below)
                _set(obj, "column", "b", c.b)
                _set(obj, "column", "d", c.d)
                _set(obj, "column", "angle", c.angle_deg)
                _set(obj, "column", "height", c.height)
                _set(obj, "column", "fixed_near", c.fixed_near)
                _set(obj, "column", "fixed_far", c.fixed_far)
                _set(obj, "column", "concrete", _concrete(model, c.concrete, mixes))

        for w in st.walls:
            for below in ({True} if w.below_slab and not w.above_slab else
                          {False} if w.above_slab and not w.below_slab else {True, False}):
                obj = layer.add_wall(seg(w.start, w.end))
                _set(obj, "wall", "below_slab", below)
                _set(obj, "wall", "thickness", w.thickness)
                _set(obj, "wall", "height", w.height)
                _set(obj, "wall", "concrete", _concrete(model, w.concrete, mixes))

        for b in st.beams:
            obj = layer.add_beam(seg(b.start, b.end))
            _set(obj, "beam", "width", b.width)
            _set(obj, "beam", "thickness", b.thickness)
            _set(obj, "beam", "priority", b.priority)
            _set(obj, "beam", "concrete", _concrete(model, b.concrete, mixes))

        log.info("mesh input objects created: %s", st.counts())

        if cfg.mesh.generate:
            try:
                model.generate_mesh(cfg.mesh.element_size)
            except TypeError:
                # Older API: element size is a model setting, not an argument.
                try:
                    model.element_size = cfg.mesh.element_size
                except Exception:  # noqa: BLE001
                    log.warning("could not set element size %s", cfg.mesh.element_size)
                model.generate_mesh()
            log.info("mesh generated")

        model.save_file(out_path)
        log.info("saved %s", out_path)
    finally:
        concept.shut_down()
