# ram_mesh_import

Turns a DXF drawn on the **BBR layers** into a RAM Concept model with the
Mesh Input layer already traced, so the engineer opens the `.cpt` and goes
straight to loads and design strips.

```
DXF / DWG (with xrefs)
   │  1. prep       bind xrefs, keep BBR layers          (accoreconsole / ODA / ezdxf)
   ▼
flat DXF
   │  2. extract    polylines -> slab, opening, column, wall, beam, drop panel
   │  3. validate   closed? overlapping? column off the slab? duplicates?
   ▼
geometry.json + report.txt
   │  4. build      RAM Concept Python API -> Mesh Input objects -> generate mesh
   ▼
LEVEL03.cpt
```

## Layer convention

Everything is drawn as polylines, in millimetres, in model space.

| Layer             | Draw                                                  | Becomes                                   |
|-------------------|-------------------------------------------------------|-------------------------------------------|
| `BBR-Slabs`       | closed polyline round each slab area                   | Slab area (thickness from config)         |
| `BBR-Opening`     | closed polyline                                       | Slab opening                              |
| `BBR-Drop Panels` | closed polyline                                       | Thicker slab area with higher priority    |
| `BBR-Columns`     | closed rectangle (size and rotation read from it), or a circle / point | Column below slab      |
| `BBR-Walls`       | closed rectangle outline, or an open polyline centreline | Wall along the long axis, thickness from the short side (or config) |
| `BBR-Beams`       | open polyline centreline (one beam per segment), or a rectangle outline | Beam                     |

Rules the validator enforces: slab and opening polylines must be closed
and not self-intersecting, slab areas must not overlap each other (draw one
outline and use openings), and no two columns may sit on the same point.
Warnings (not fatal): columns, walls or beams that do not touch a slab,
openings outside every slab, very short edges, and ignored entities such as
text. Arcs in polylines are flattened automatically.

## Install

```
pip install -r requirements.txt
```

The RAM Concept API (`ram_concept`) ships with RAM Concept CONNECT Edition
and is not on PyPI. On the machine that runs the build step, add its folder
to `PYTHONPATH`, for example:

```
set PYTHONPATH=C:\Program Files\Bentley\Engineering\RAM Concept CONNECT Edition\RAM Concept\python
```

The `--dry-run` mode needs only `ezdxf` and `shapely` and works anywhere.

## Quick start on Windows (batch files)

| File          | What it does                                                                 |
|---------------|------------------------------------------------------------------------------|
| `setup.bat`   | Run once. Installs the Python packages, copies `config.json`, runs the tests. |
| `dry_run.bat` | Drag a DXF **or a folder of DXFs** onto it. Checks the drawing(s) and opens the dashboard. RAM Concept is not started. |
| `build.bat`   | Drag a DXF or a folder onto it. Validates, builds the `.cpt` model(s), generates the mesh, opens the dashboard. Edit `CONCEPT_PY` inside it once to point at your RAM Concept install. |

Both drag-and-drop files read `config.json` from the same folder when it
exists.

## Dashboard

Every run writes `<drawing>_dashboard.html` next to the output (in the
`*_work` folder). It shows:

- a plan view of everything extracted: slab, drop panels, openings, columns
  (with size and rotation), walls and beams, hover any object for its CAD
  handle;
- object counts and whether the model was built;
- every validation error and warning, each naming the CAD handle and layer
  of the object so it can be found in AutoCAD.

Batch mode also writes `index.html`, one row per drawing with its status,
linking to each drawing's dashboard.

## Command line

```
# 1. check the drawing without touching RAM Concept
python -m ram_mesh_import LEVEL03.dxf --config config.json --dry-run --open

# 2. build the model
python -m ram_mesh_import LEVEL03.dxf --config config.json --out LEVEL03.cpt

# 3. every DXF in a folder -> <folder>\concept\*.cpt plus index.html
python -m ram_mesh_import C:\jobs\dxf --batch --config config.json

# what layers are in this file?
python -m ram_mesh_import LEVEL03.dxf --list-layers
```

Outputs land in `<out>_work/`: the flattened DXF, `*_geometry.json` (what
will be created, in model units), `*_report.txt` and `*_dashboard.html`.
The exit code is 1 when validation fails, so the command can sit in a
scheduled job.

Copy `examples/config.example.json` per project and edit slab thickness,
concrete names, column size defaults, mesh size and the tool paths.
Set `cad_to_model_scale` to `0.001` for mm drawings into an SI model, or
`0.00328084` for mm into a US-units model.

## Xrefs and DWG input

`ezdxf` reads DXF only, and it does not follow external references unless
told to. Three ways to get a flat DXF, chosen automatically from the config:

1. `tools.accoreconsole` set: headless AutoCAD binds every xref, keeps only
   the BBR layers, purges and exports a DXF. Works for DWG or DXF input.
2. `tools.oda_file_converter` set: the free ODA File Converter turns the DWG
   into DXF, then `ezdxf` merges any xrefs that are DXF files next to it.
3. Neither set: the input must already be a DXF. Xrefs that are DXF files
   are merged; DWG xrefs are reported and skipped.

Simplest workflow for drafters: put the BBR layers in the structural
drawing itself (not in the architectural xref), then `SAVEAS` DXF.

## Adapting to a RAM Concept version

Every Concept property is set through the `PROPERTY_NAMES` table at the top
of `ram_mesh_import/concept_builder.py`. If the log shows
`... has no attribute ...`, look up the name in the API help installed with
Concept and change it in that table only.

## Tests

```
python -m pytest tests -q
```

`examples/make_sample_dxf.py` writes `examples/sample_level.dxf`, a small
L-shaped floor on the BBR layers, used by the tests and handy for a first
dry run.
