"""Command line entry point.

    python -m ram_mesh_import LEVEL03.dxf --config config.json --out LEVEL03.cpt
    python -m ram_mesh_import LEVEL03.dxf --dry-run            # no RAM Concept needed
    python -m ram_mesh_import C:\\jobs\\dxf\\ --batch          # every DXF in the folder
    python -m ram_mesh_import LEVEL03.dxf --list-layers

Every run writes a dashboard (HTML) next to the output; --open shows it.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import webbrowser
from pathlib import Path
from typing import List, Optional

from .config import Config
from .extract import list_layers, read_structure
from .prep import prepare
from .report import write_html, write_index
from .validate import validate

log = logging.getLogger("ram_mesh_import")


def _open(path: Path) -> None:
    try:
        if os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.as_uri())
    except Exception as exc:  # noqa: BLE001
        log.warning("could not open %s: %s", path, exc)


def process_one(drawing: Path, cfg: Config, out: Path, work: Path, *, dry_run: bool,
                skip_prep: bool, strict: bool, show_ui: bool) -> dict:
    """Run the pipeline for one drawing. Returns a summary dict for the batch index."""
    work.mkdir(parents=True, exist_ok=True)
    flat = drawing if skip_prep else prepare(drawing, cfg, work)
    log.info("reading %s", flat)
    st = read_structure(flat, cfg)
    log.info("found %s", st.counts())

    rep = validate(st, cfg)
    (work / f"{drawing.stem}_report.txt").write_text(rep.text() + "\n", encoding="utf-8")
    st.to_json(str(work / f"{drawing.stem}_geometry.json"))
    print(rep.text())

    failed = (not rep.ok) or (strict and bool(rep.warnings))
    built = False
    if failed:
        log.error("validation failed for %s; fix the drawing and run again", drawing.name)
    elif dry_run:
        log.info("dry run complete; RAM Concept not started")
    else:
        from .concept_builder import build_model
        build_model(st, cfg, str(out), headless=not show_ui)
        built = True
        print(f"RAM Concept model written: {out}")

    dashboard = write_html(work / f"{drawing.stem}_dashboard.html", drawing.name, st, rep,
                           str(out) if built else None, cfg.units, built)
    log.info("dashboard: %s", dashboard)
    return {
        "name": drawing.name,
        "report": dashboard.name if dashboard.parent == work else str(dashboard),
        "dashboard": dashboard,
        "errors": rep.errors,
        "warnings": rep.warnings,
        "counts": st.counts(),
        "cpt": str(out) if built else None,
        "failed": failed,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="ram_mesh_import",
                                 description="DXF/DWG (BBR layers) -> RAM Concept Mesh Input")
    ap.add_argument("drawing", help="input .dxf/.dwg, or a folder with --batch")
    ap.add_argument("--config", "-c", help="JSON config (defaults used when omitted)")
    ap.add_argument("--out", "-o", help="output .cpt path (single file) or output folder (batch)")
    ap.add_argument("--work-dir", help="folder for the flattened DXF, reports and dashboard")
    ap.add_argument("--batch", action="store_true", help="process every .dxf/.dwg in the folder")
    ap.add_argument("--dry-run", action="store_true",
                    help="extract + validate + dashboard only, do not start RAM Concept")
    ap.add_argument("--list-layers", action="store_true", help="print the layer names and exit")
    ap.add_argument("--skip-prep", action="store_true", help="read the DXF as-is (no xref binding)")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--show-ui", action="store_true", help="run RAM Concept with its window visible")
    ap.add_argument("--open", action="store_true", help="open the dashboard when finished")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args(argv)

    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)-7s %(name)s: %(message)s")

    src = Path(args.drawing)
    if not src.exists():
        log.error("not found: %s", src)
        return 2
    cfg = Config.load(args.config) if args.config else Config()

    if args.list_layers:
        for name in list_layers(src):
            print(name)
        return 0

    common = dict(dry_run=args.dry_run, skip_prep=args.skip_prep, strict=args.strict, show_ui=args.show_ui)

    if args.batch or src.is_dir():
        if not src.is_dir():
            log.error("--batch needs a folder")
            return 2
        drawings = sorted(p for p in src.iterdir() if p.suffix.lower() in (".dxf", ".dwg"))
        if not drawings:
            log.error("no .dxf/.dwg files in %s", src)
            return 2
        out_dir = Path(args.out) if args.out else src / "concept"
        work = Path(args.work_dir) if args.work_dir else out_dir / "work"
        work.mkdir(parents=True, exist_ok=True)
        runs = []
        for d in drawings:
            print(f"\n=== {d.name} ===")
            try:
                runs.append(process_one(d, cfg, out_dir / (d.stem + ".cpt"), work, **common))
            except Exception as exc:  # noqa: BLE001 - keep going with the next drawing
                log.exception("failed on %s", d.name)
                runs.append({"name": d.name, "report": "", "errors": [str(exc)], "warnings": [],
                             "counts": {"slabs": 0, "openings": 0, "columns": 0, "walls": 0, "beams": 0},
                             "cpt": None, "failed": True})
        index = write_index(work / "index.html", runs)
        print(f"\nBatch dashboard: {index}")
        if args.open:
            _open(index)
        return 1 if any(r["failed"] for r in runs) else 0

    out = Path(args.out) if args.out else src.with_suffix(".cpt")
    work = Path(args.work_dir) if args.work_dir else out.with_name(out.stem + "_work")
    result = process_one(src, cfg, out, work, **common)
    print(f"Dashboard: {result['dashboard']}")
    if args.open:
        _open(result["dashboard"])
    return 1 if result["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
