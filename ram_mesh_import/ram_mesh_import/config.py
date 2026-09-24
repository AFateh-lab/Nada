"""Project configuration loaded from a JSON file.

Everything that changes from project to project (layer names, units, slab
thickness, materials, tool paths) lives in the config so the scripts never
need editing.  See ``examples/config.example.json``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List


@dataclass
class LayerMap:
    """CAD layer names for each structural object type.

    Each entry is a list because architectural xrefs often split the same
    object type over several layers (for example S-SLAB-EDGE and A-SLAB).
    Layer matching is case-insensitive and supports ``*`` wildcards.
    """

    slab: List[str] = field(default_factory=lambda: ["BBR-Slabs"])
    opening: List[str] = field(default_factory=lambda: ["BBR-Opening"])
    column: List[str] = field(default_factory=lambda: ["BBR-Columns"])
    wall: List[str] = field(default_factory=lambda: ["BBR-Walls"])
    # Optional: walls drawn as single centrelines instead of outlines.
    wall_centreline: List[str] = field(default_factory=lambda: ["BBR-Walls-CL"])
    beam: List[str] = field(default_factory=lambda: ["BBR-Beams"])
    drop_panel: List[str] = field(default_factory=lambda: ["BBR-Drop Panels"])

    def all_layers(self) -> List[str]:
        out: List[str] = []
        for names in vars(self).values():
            out.extend(names)
        return out


@dataclass
class SlabDefaults:
    thickness: float = 0.250      # model units (m or ft, see units)
    concrete: str = "C40"
    toc: float = 0.0              # top of concrete elevation
    priority: int = 1


@dataclass
class OpeningDefaults:
    priority: int = 2


@dataclass
class ColumnDefaults:
    b: float = 0.400
    d: float = 0.400
    height: float = 3.000
    concrete: str = "C40"
    below_slab: bool = True
    above_slab: bool = False
    fixed_near: bool = True
    fixed_far: bool = True
    # If a column in CAD is a closed rectangle rather than a point, take the
    # size from the rectangle instead of the defaults above.
    size_from_outline: bool = True


@dataclass
class WallDefaults:
    thickness: float = 0.200
    height: float = 3.000
    concrete: str = "C40"
    below_slab: bool = True
    above_slab: bool = False
    # Wall outlines in CAD are converted to a centreline. This is the
    # largest outline aspect ratio still treated as a wall (avoid squares).
    min_aspect_ratio: float = 2.0


@dataclass
class BeamDefaults:
    width: float = 0.400
    thickness: float = 0.600      # total depth including slab
    concrete: str = "C40"
    priority: int = 3


@dataclass
class DropPanelDefaults:
    thickness: float = 0.400
    concrete: str = "C40"
    priority: int = 2


@dataclass
class MeshDefaults:
    element_size: float = 0.300
    generate: bool = True


@dataclass
class ToolPaths:
    # Headless AutoCAD. Leave empty to skip the bind step and read the DXF
    # directly with ezdxf (xrefs are then resolved by ezdxf).
    accoreconsole: str = ""
    # ODA File Converter, used when the input is a DWG and AutoCAD is absent.
    oda_file_converter: str = ""
    # Folder holding the RAM Concept Python API (the "python" folder inside the
    # RAM Concept installation). Also settable with the CONCEPT_PY env var.
    concept_python: str = ""


@dataclass
class Config:
    # Multiply CAD coordinates by this to get model units.
    # mm -> m = 0.001, mm -> ft = 0.00328084, in -> ft = 1/12, m -> m = 1.
    cad_to_model_scale: float = 0.001
    # RAM Concept unit system: "SI" or "US".
    units: str = "SI"
    design_code: str = ""
    # Snap tolerance in model units used when cleaning polylines.
    tolerance: float = 0.005
    layers: LayerMap = field(default_factory=LayerMap)
    slab: SlabDefaults = field(default_factory=SlabDefaults)
    opening: OpeningDefaults = field(default_factory=OpeningDefaults)
    column: ColumnDefaults = field(default_factory=ColumnDefaults)
    wall: WallDefaults = field(default_factory=WallDefaults)
    beam: BeamDefaults = field(default_factory=BeamDefaults)
    drop_panel: DropPanelDefaults = field(default_factory=DropPanelDefaults)
    mesh: MeshDefaults = field(default_factory=MeshDefaults)
    tools: ToolPaths = field(default_factory=ToolPaths)
    # Block names that represent columns when columns are inserted as blocks.
    column_block_names: List[str] = field(default_factory=lambda: ["COL*", "COLUMN*"])
    # Explode block references before reading geometry.
    explode_blocks: bool = True

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        with open(path, "r", encoding="utf-8") as fh:
            raw: Dict = json.load(fh)
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: Dict) -> "Config":
        cfg = cls()
        sections = {
            "layers": LayerMap,
            "slab": SlabDefaults,
            "opening": OpeningDefaults,
            "column": ColumnDefaults,
            "wall": WallDefaults,
            "beam": BeamDefaults,
            "drop_panel": DropPanelDefaults,
            "mesh": MeshDefaults,
            "tools": ToolPaths,
        }
        for key, value in raw.items():
            if key in sections:
                section = sections[key]()
                for k, v in value.items():
                    if not hasattr(section, k):
                        raise KeyError(f"Unknown config key {key}.{k}")
                    setattr(section, k, v)
                setattr(cfg, key, section)
            elif hasattr(cfg, key):
                setattr(cfg, key, value)
            else:
                raise KeyError(f"Unknown config key {key}")
        if cfg.units not in ("SI", "US"):
            raise ValueError("units must be 'SI' or 'US'")
        return cfg
