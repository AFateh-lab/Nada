"""Turn the engineer's input drawing into a flat DXF that ezdxf can read.

Three cases:

1. Input is already a DXF with no xrefs -> returned unchanged.
2. Input is a DWG/DXF and ``tools.accoreconsole`` is set -> headless AutoCAD
   binds all xrefs, keeps only the BBR layers, purges, and writes a DXF.
3. Input is a DWG and only ``tools.oda_file_converter`` is set -> the ODA
   converter produces a DXF; xrefs referenced by that DXF are then merged
   into the model space by ezdxf.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import ezdxf

from .config import Config

log = logging.getLogger(__name__)


def _accore_script(dxf_out: Path, layers: list[str]) -> str:
    keep = ",".join(layers)
    # Each line is one AutoCAD command; blank lines are Enter.
    return "\n".join([
        "-XREF B *",                 # bind every xref
        "",
        "-LAYER T * ",               # thaw everything so bind results are visible
        "-LAYER S 0 ",               # current layer 0 so we can turn others off
        "-LAYER OFF * N ",           # turn all layers off ('N' = do not turn off current)
        f"-LAYER ON {keep} ",
        "",
        "-PURGE A * N",
        "-PURGE A * N",
        f'DXFOUT "{dxf_out}" V 2018 16',
        "QUIT Y",
        "",
    ])


def _run_accoreconsole(exe: str, dwg: Path, dxf_out: Path, layers: list[str]) -> Path:
    with tempfile.TemporaryDirectory() as td:
        scr = Path(td) / "prep.scr"
        scr.write_text(_accore_script(dxf_out, layers), encoding="ascii")
        cmd = [exe, "/i", str(dwg), "/s", str(scr)]
        log.info("running %s", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        log.debug(proc.stdout)
        if not dxf_out.exists():
            raise RuntimeError("accoreconsole did not produce a DXF:\n" + proc.stdout[-2000:])
    return dxf_out


def _run_oda(exe: str, dwg: Path, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [exe, str(dwg.parent), str(out_dir), "ACAD2018", "DXF", "0", "1", dwg.name]
    log.info("running %s", " ".join(cmd))
    subprocess.run(cmd, check=True, timeout=600)
    dxf = out_dir / (dwg.stem + ".dxf")
    if not dxf.exists():
        raise RuntimeError("ODA File Converter did not produce " + str(dxf))
    return dxf


def _merge_xrefs(dxf: Path, out: Path) -> Path:
    """Merge the model space of every attached xref into ``dxf``."""
    doc = ezdxf.readfile(str(dxf))
    try:
        from ezdxf import xref
    except ImportError:
        log.warning("ezdxf %s cannot resolve xrefs; bind them in AutoCAD first", ezdxf.__version__)
        return dxf
    xref_blocks = [b for b in doc.blocks if b.block_record.is_xref]
    if not xref_blocks:
        return dxf
    msp = doc.modelspace()
    for insert in list(msp.query("INSERT")):
        block = doc.blocks.get(insert.dxf.name)
        if block is None or not block.block_record.is_xref:
            continue
        path = Path(block.block_record.dxf.xref_path)
        if not path.is_absolute():
            path = dxf.parent / path
        if path.suffix.lower() != ".dxf":
            alt = path.with_suffix(".dxf")
            if not alt.exists():
                log.warning("xref %s is a DWG; convert it to DXF next to the host first", path)
                continue
            path = alt
        if not path.exists():
            log.warning("xref file not found: %s", path)
            continue
        log.info("merging xref %s", path)
        src = ezdxf.readfile(str(path))
        loader = xref.Loader(src, doc)
        loader.load_modelspace(msp)
        loader.execute()
        msp.delete_entity(insert)
    doc.saveas(str(out))
    return out


def prepare(input_path: str | Path, cfg: Config, work_dir: str | Path) -> Path:
    src = Path(input_path)
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    flat = work / (src.stem + "_flat.dxf")
    layers = cfg.layers.all_layers()

    if cfg.tools.accoreconsole:
        exe = cfg.tools.accoreconsole
        if not Path(exe).exists():
            raise FileNotFoundError(exe)
        return _run_accoreconsole(exe, src, flat, layers)

    if src.suffix.lower() == ".dwg":
        if not cfg.tools.oda_file_converter:
            raise RuntimeError("input is a DWG but neither accoreconsole nor oda_file_converter "
                               "is configured; save the drawing as DXF or set tools in the config")
        dxf = _run_oda(cfg.tools.oda_file_converter, src, work)
    else:
        dxf = work / src.name
        if src.resolve() != dxf.resolve():
            shutil.copy(src, dxf)

    return _merge_xrefs(dxf, flat)
