"""Command line entry point.

    python -m ram_mesh_import LEVEL03.dxf --config config.json --out LEVEL03.cpt
    python -m ram_mesh_import LEVEL03.dxf --dry-run          # no RAM Concept needed
    python -m ram_mesh_import LEVEL03.dxf --list-layers
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .config import Config
from .extract import list_layers, read_structure
from .prep import prepare
from .validate import validate


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ram_mesh_import",
                                 description="DXF/DWG (BBR layers) -> RAM Concept Mesh Input")
    ap.add_argument("drawing", help="input .dxf or .dwg")
    ap.add_argument("--config", "-c", help="JSON config (defaults used when omitted)")
    ap.add_argument("--out", "-o", help="output .cpt path (default: next to the drawing)")
    ap.add_argument("--work-dir", help="folder for the flattened DXF and reports (default: <out>_work)")
    ap.add_argument("--dry-run", action="store_true",
                    help="extract + validate only, write geometry JSON, do not start RAM Concept")
    ap.add_argument("--list-layers", action="store_true", help="print the layer names in the drawing and exit")
    ap.add_argument("--skip-prep", action="store_true",
                    help="read the DXF as-is (no xref binding / conversion)")
    ap.add_argument("--allow-warnings", action="store_true", default=True,
                    help="continue to Concept when only warnings are found (default)")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--show-ui", action="store_true", help="run RAM Concept with its window visible")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args(argv)

    logging.basicConfig(level=args.log_level.upper(), format="%(levelname)-7s %(name)s: %(message)s")
    log = logging.getLogger("ram_mesh_import")

    drawing = Path(args.drawing)
    if not drawing.exists():
        log.error("drawing not found: %s", drawing)
        return 2

    cfg = Config.load(args.config) if args.config else Config()
    out = Path(args.out) if args.out else drawing.with_suffix(".cpt")
    work = Path(args.work_dir) if args.work_dir else out.with_name(out.stem + "_work")
    work.mkdir(parents=True, exist_ok=True)

    if args.list_layers:
        for name in list_layers(drawing):
            print(name)
        return 0

    flat = drawing if args.skip_prep else prepare(drawing, cfg, work)
    log.info("reading %s", flat)
    st = read_structure(flat, cfg)
    log.info("found %s", st.counts())

    rep = validate(st, cfg)
    report_path = work / (drawing.stem + "_report.txt")
    report_path.write_text(rep.text() + "\n", encoding="utf-8")
    print(rep.text())
    geom_path = work / (drawing.stem + "_geometry.json")
    st.to_json(str(geom_path))
    log.info("geometry written to %s", geom_path)

    if not rep.ok or (args.strict and rep.warnings):
        log.error("validation failed; fix the drawing and run again (report: %s)", report_path)
        return 1

    if args.dry_run:
        log.info("dry run complete; RAM Concept not started")
        return 0

    from .concept_builder import build_model
    build_model(st, cfg, str(out), headless=not args.show_ui)
    print(f"RAM Concept model written: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
