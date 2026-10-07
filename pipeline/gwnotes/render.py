"""Rendering con LaTeX di formule e frammenti, e rasterizzazione delle figure.

Tutte le formule sono compilate in un unico documento (pacchetto `preview`, una
pagina per formula) che usa lo stesso preambolo del documento originale: macro e
pacchetti dell'utente funzionano senza configurazione.
Una formula che non compila da sola non blocca la build: viene segnalata nel
report e mostrata come testo TeX.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

PT_PER_IN = 72.27
BORDER_PT = 1.0


@dataclass
class Raster:
    gray: Image.Image          # L, inchiostro scuro su sfondo chiaro (come il PDF)
    ascent: int | None = None  # pixel dal bordo superiore alla baseline (solo formule)
    natural: bool = True       # True se gray è alla dimensione "naturale" di lettura


def base_font_pt(preamble: str) -> float:
    m = re.search(r"\\documentclass\s*\[([^\]]*)\]", preamble)
    if m:
        mm = re.search(r"(\d+(?:\.\d+)?)pt", m.group(1))
        if mm:
            return float(mm.group(1))
    return 10.0


def clean_math(tex: str, display: bool) -> str:
    tex = re.sub(r"\\label\s*\{[^}]*\}", "", tex)
    tex = re.sub(r"\\tag\*?\s*\{[^}]*\}", "", tex)
    tex = re.sub(r"\\(nonumber|notag)(?![a-zA-Z])", "", tex)
    tex = tex.strip()
    if display and "\\\\" in tex and not re.search(r"\\begin\{", tex):
        tex = "\\begin{gathered}" + tex + "\\end{gathered}"
    return tex


def _preview_doc(preamble: str, items: list[tuple[str, str]]) -> str:
    body = []
    for rid, content in items:
        body.append(
            "\\begin{preview}\\typeout{GWITEM:%s}%s\\typeout{GWDIM:%s:\\the\\ht0:\\the\\dp0:\\the\\wd0}"
            "\\usebox0\\end{preview}\n" % (rid, content, rid)
        )
    pre = preamble.rstrip()
    pre += ("\n\\usepackage[active,tightpage]{preview}\n\\setlength\\PreviewBorder{%gpt}\n"
            "\\pagestyle{empty}\n" % BORDER_PT)
    return pre + "\n\\begin{document}\n" + "".join(body) + "\\end{document}\n"


def _content(job) -> str:
    if job.type == "math":
        tex = clean_math(job.tex, job.display)
        style = "\\displaystyle " if job.display else ""
        return "\\sbox0{$" + style + tex + "$}"
    # frammento (tikz, ...): in un box orizzontale
    return "\\sbox0{" + job.tex + "}"


def _run_pdflatex(tex_src: str, cwd: Path, workdir: Path, name: str):
    workdir.mkdir(parents=True, exist_ok=True)
    tex_path = workdir / f"{name}.tex"
    tex_path.write_text(tex_src, encoding="utf-8")
    p = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-recorder",
                        f"-output-directory={workdir}", str(tex_path)],
                       cwd=cwd, capture_output=True, text=True, timeout=1800)
    log = (workdir / f"{name}.log").read_text(encoding="utf-8", errors="replace") \
        if (workdir / f"{name}.log").exists() else p.stdout
    return workdir / f"{name}.pdf", log


def _failed_items(log: str) -> dict[str, str]:
    failed: dict[str, str] = {}
    cur = None
    lines = log.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"GWITEM:(\w+)", line)
        if m:
            cur = m.group(1)
            continue
        if line.startswith("! ") and cur:
            failed.setdefault(cur, line[2:].strip())
    return failed


def _dims(log: str) -> dict[str, tuple[float, float, float]]:
    dims = {}
    for m in re.finditer(r"GWDIM:(\w+):([\d.]+)pt:([\d.]+)pt:([\d.]+)pt", log):
        dims[m.group(1)] = (float(m.group(2)), float(m.group(3)), float(m.group(4)))
    return dims


def render_latex_jobs(jobs, preamble: str, cwd: Path, workdir: Path, px_per_em: float, warn) -> dict[str, Raster]:
    """Compila formule/frammenti. Ritorna rid -> Raster (alla dimensione naturale)."""
    if not jobs:
        return {}
    em_pt = base_font_pt(preamble)
    dpi = px_per_em * PT_PER_IN / em_pt
    items = [(j.rid, _content(j)) for j in jobs]
    _, log = _run_pdflatex(_preview_doc(preamble, items), cwd, workdir, "gwmath1")
    failed = _failed_items(log)
    by_rid = {j.rid: j for j in jobs}
    for rid, err in failed.items():
        j = by_rid.get(rid)
        if j:
            warn.add("formula-errore", f"formula non compilabile da sola ({err}) in {j.where}: {j.tex[:120]}")
    ok_items = [(rid, c) for rid, c in items if rid not in failed]
    if failed:
        pdf, log = _run_pdflatex(_preview_doc(preamble, ok_items), cwd, workdir, "gwmath2")
        still = _failed_items(log)
        if still:
            raise RuntimeError("errori LaTeX persistenti nel rendering delle formule: " + "; ".join(still.values()))
    else:
        pdf = workdir / "gwmath1.pdf"
    dims = _dims(log)
    pages = _rasterize_pdf(pdf, dpi, workdir / "pages")
    if len(pages) != len(ok_items):
        raise RuntimeError(f"rendering formule: {len(pages)} pagine per {len(ok_items)} formule")
    out = {}
    for (rid, _), img in zip(ok_items, pages):
        ascent = None
        if rid in dims:
            ht, dp, _ = dims[rid]
            total = ht + dp + 2 * BORDER_PT
            ascent = round(img.height * (ht + BORDER_PT) / total) if total > 0 else img.height
        out[rid] = Raster(img, ascent, True)
    return out


def _rasterize_pdf(pdf: Path, dpi: float, outdir: Path, first: int | None = None, last: int | None = None):
    outdir.mkdir(parents=True, exist_ok=True)
    for f in outdir.glob("p-*.png"):
        f.unlink()
    cmd = ["pdftoppm", "-r", f"{dpi:.3f}", "-gray", "-png", "-aa", "yes", "-aaVector", "yes"]
    if first:
        cmd += ["-f", str(first)]
    if last:
        cmd += ["-l", str(last)]
    subprocess.run(cmd + [str(pdf), str(outdir / "p")], check=True, capture_output=True)
    files = sorted(outdir.glob("p-*.png"), key=lambda p: int(p.stem.split("-")[-1]))
    imgs = []
    for f in files:
        with Image.open(f) as im:
            imgs.append(im.convert("L").copy())
    return imgs


def render_figure(path: Path, dpi: int) -> Raster:
    """Rasterizza un file grafico (PDF/PNG/JPG/EPS) alla risoluzione di "zoom"."""
    suffix = path.suffix.lower()
    if suffix in (".pdf", ".eps"):
        src = path
        if suffix == ".eps":
            tmp = Path(tempfile.mkdtemp())
            subprocess.run(["epstopdf", str(path), f"--outfile={tmp / 'x.pdf'}"], check=True, capture_output=True)
            src = tmp / "x.pdf"
        with tempfile.TemporaryDirectory() as td:
            imgs = _rasterize_pdf(src, dpi, Path(td), 1, 1)
        return Raster(imgs[0], None, True)
    with Image.open(path) as im:
        im.load()
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
            bg.alpha_composite(im)
            im = bg
        return Raster(im.convert("L").copy(), None, True)
