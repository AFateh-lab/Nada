"""HTML dashboard written after every run.

One self-contained file, no internet needed: a plan view of everything the
tool extracted (slab, openings, drop panels, columns, walls, beams), the
object counts, and the validation errors / warnings with the CAD handle of
the offending object so it can be found in AutoCAD with ``SELECT`` + handle.
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .geometry import Structure
from .validate import Report

_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--muted:#5d6b7a;--line:#d9dee5;
--slab:#cfd8e3;--open:#fff;--drop:#a9b8c9;--col:#1f5fbf;--wall:#8a2d2d;--beam:#b8860b;
--ok:#1e7f4f;--err:#b3261e;--warn:#9a6700}
@media(prefers-color-scheme:dark){:root{--bg:#14181e;--card:#1c222b;--ink:#e6eaf0;--muted:#98a4b3;
--line:#2c3540;--slab:#33404f;--open:#14181e;--drop:#4a5a6e;--col:#6ea8ff;--wall:#ff8a80;--beam:#ffd166}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.45 system-ui,Segoe UI,Roboto,sans-serif}
header{padding:20px 24px 8px}h1{margin:0;font-size:22px}h1 small{color:var(--muted);font-weight:400;font-size:14px;margin-left:10px}
.wrap{display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,1fr);gap:16px;padding:0 24px 24px}
@media(max-width:900px){.wrap{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.card h2{margin:0 0 10px;font-size:15px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.status{display:inline-block;padding:4px 10px;border-radius:999px;font-weight:600;color:#fff}
.status.ok{background:var(--ok)}.status.err{background:var(--err)}.status.warn{background:var(--warn)}
table{width:100%;border-collapse:collapse}td,th{padding:6px 4px;border-bottom:1px solid var(--line);text-align:left}
td.n{text-align:right;font-variant-numeric:tabular-nums}
ul.msgs{margin:0;padding:0;list-style:none}ul.msgs li{padding:6px 8px;border-left:3px solid var(--line);margin-bottom:6px;font-size:13.5px}
ul.msgs li.err{border-color:var(--err)}ul.msgs li.warn{border-color:var(--warn)}
svg{width:100%;height:auto;background:var(--card);border-radius:6px}
.legend span{display:inline-block;margin:0 12px 4px 0;font-size:13px}
.legend i{display:inline-block;width:12px;height:12px;border-radius:2px;vertical-align:-1px;margin-right:5px}
code{font-size:12.5px;color:var(--muted)}
"""


def _svg_plan(st: Structure) -> str:
    xs: List[float] = []
    ys: List[float] = []
    for group in (st.slabs, st.openings, st.drop_panels):
        for it in group:
            xs += [p[0] for p in it.points]
            ys += [p[1] for p in it.points]
    for c in st.columns:
        xs.append(c.centre[0]); ys.append(c.centre[1])
    for it in (*st.walls, *st.beams):
        xs += [it.start[0], it.end[0]]; ys += [it.start[1], it.end[1]]
    if not xs:
        return "<p>Nothing to draw.</p>"
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    w, h = max(maxx - minx, 1e-6), max(maxy - miny, 1e-6)
    pad = 0.05 * max(w, h)
    vb = f"{minx - pad:.3f} {-(maxy + pad):.3f} {w + 2 * pad:.3f} {h + 2 * pad:.3f}"
    sw = max(w, h) / 400          # stroke width scaled to the drawing

    def pts(points):
        return " ".join(f"{x:.3f},{-y:.3f}" for x, y in points)

    out = [f'<svg viewBox="{vb}" xmlns="http://www.w3.org/2000/svg">']
    for s in st.slabs:
        out.append(f'<polygon points="{pts(s.points)}" fill="var(--slab)" stroke="var(--ink)" stroke-width="{sw:.4f}">'
                   f'<title>slab {html.escape(s.source)} t={s.thickness}</title></polygon>')
    for d in st.drop_panels:
        out.append(f'<polygon points="{pts(d.points)}" fill="var(--drop)" stroke="var(--ink)" stroke-width="{sw / 2:.4f}">'
                   f'<title>drop panel {html.escape(d.source)} t={d.thickness}</title></polygon>')
    for o in st.openings:
        out.append(f'<polygon points="{pts(o.points)}" fill="var(--open)" stroke="var(--ink)" stroke-width="{sw:.4f}" stroke-dasharray="{sw * 4:.3f} {sw * 2:.3f}">'
                   f'<title>opening {html.escape(o.source)}</title></polygon>')
    for b in st.beams:
        out.append(f'<line x1="{b.start[0]:.3f}" y1="{-b.start[1]:.3f}" x2="{b.end[0]:.3f}" y2="{-b.end[1]:.3f}" '
                   f'stroke="var(--beam)" stroke-width="{b.width:.3f}" stroke-linecap="butt" opacity=".85">'
                   f'<title>beam {html.escape(b.source)} {b.width}x{b.thickness}</title></line>')
    for wl in st.walls:
        out.append(f'<line x1="{wl.start[0]:.3f}" y1="{-wl.start[1]:.3f}" x2="{wl.end[0]:.3f}" y2="{-wl.end[1]:.3f}" '
                   f'stroke="var(--wall)" stroke-width="{wl.thickness:.3f}" stroke-linecap="butt">'
                   f'<title>wall {html.escape(wl.source)} t={wl.thickness}</title></line>')
    for c in st.columns:
        x, y = c.centre
        out.append(f'<rect x="{x - c.b / 2:.3f}" y="{-y - c.d / 2:.3f}" width="{c.b:.3f}" height="{c.d:.3f}" '
                   f'fill="var(--col)" transform="rotate({-c.angle_deg:.2f} {x:.3f} {-y:.3f})">'
                   f'<title>column {html.escape(c.source)} {c.b:.2f}x{c.d:.2f} @ {c.angle_deg:.0f}deg</title></rect>')
    out.append("</svg>")
    return "".join(out)


def write_html(path: str | Path, drawing_name: str, st: Structure, rep: Report,
               out_cpt: Optional[str], units: str, built: bool) -> Path:
    counts = st.counts()
    if rep.errors:
        status, label = "err", f"{len(rep.errors)} error(s) - fix the drawing"
    elif rep.warnings:
        status, label = "warn", f"OK with {len(rep.warnings)} warning(s)"
    else:
        status, label = "ok", "OK"
    unit = "m" if units == "SI" else "ft"

    rows = "".join(f"<tr><td>{k.replace('_', ' ')}</td><td class=n>{v}</td></tr>"
                   for k, v in counts.items() if k != "skipped")
    msgs = "".join(f'<li class="err">{html.escape(m)}</li>' for m in rep.errors)
    msgs += "".join(f'<li class="warn">{html.escape(m)}</li>' for m in rep.warnings)
    if not msgs:
        msgs = "<li>No problems found.</li>"

    result = ("<p>RAM Concept model written: <code>" + html.escape(out_cpt or "") + "</code></p>" if built
              else "<p>Dry run: RAM Concept was not started.</p>" if rep.ok
              else "<p>Model not built because of errors.</p>")

    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(drawing_name)} - mesh import</title><style>{_CSS}</style></head><body>
<header><h1>{html.escape(drawing_name)}<small>{datetime.now():%Y-%m-%d %H:%M}</small></h1>
<p><span class="status {status}">{label}</span></p></header>
<div class="wrap">
<section class="card"><h2>Plan ({unit})</h2>{_svg_plan(st)}
<p class="legend"><span><i style="background:var(--slab)"></i>slab</span><span><i style="background:var(--drop)"></i>drop panel</span>
<span><i style="background:var(--open);border:1px dashed var(--ink)"></i>opening</span><span><i style="background:var(--col)"></i>column</span>
<span><i style="background:var(--wall)"></i>wall</span><span><i style="background:var(--beam)"></i>beam</span></p>
<p><code>Hover an object for its CAD handle. In AutoCAD: (handent "HANDLE") or SELECT then type the handle.</code></p></section>
<div>
<section class="card"><h2>Objects</h2><table>{rows}</table>{result}</section>
<section class="card" style="margin-top:16px"><h2>Checks</h2><ul class="msgs">{msgs}</ul></section>
</div></div></body></html>"""
    p = Path(path)
    p.write_text(doc, encoding="utf-8")
    return p


def write_index(path: str | Path, runs: List[dict]) -> Path:
    """Summary page for batch mode: one row per drawing."""
    rows = []
    for r in runs:
        cls = "err" if r["errors"] else "warn" if r["warnings"] else "ok"
        label = "errors" if r["errors"] else "warnings" if r["warnings"] else "OK"
        rows.append(f'<tr><td><a href="{html.escape(r["report"])}">{html.escape(r["name"])}</a></td>'
                    f'<td><span class="status {cls}">{label}</span></td>'
                    f'<td class=n>{r["counts"]["slabs"]}</td><td class=n>{r["counts"]["openings"]}</td>'
                    f'<td class=n>{r["counts"]["columns"]}</td><td class=n>{r["counts"]["walls"]}</td>'
                    f'<td class=n>{r["counts"]["beams"]}</td><td>{html.escape(r.get("cpt") or "")}</td></tr>')
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mesh import batch</title>
<style>{_CSS}</style></head><body><header><h1>Mesh import batch<small>{datetime.now():%Y-%m-%d %H:%M}</small></h1></header>
<div style="padding:0 24px 24px"><section class="card"><table><tr><th>Drawing</th><th>Status</th><th>Slabs</th>
<th>Openings</th><th>Columns</th><th>Walls</th><th>Beams</th><th>Model</th></tr>{''.join(rows)}</table></section></div>
</body></html>"""
    p = Path(path)
    p.write_text(doc, encoding="utf-8")
    return p
