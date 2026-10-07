"""Dai job di rendering alle immagini finali per l'orologio (normale + zoom)."""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from . import eqsplit, images
from .bundle import short_hash
from .render import Raster, render_figure, render_latex_jobs


@dataclass
class Asset:
    normal: Image.Image          # livelli 0..3, sfondo nero
    ascent: int | None           # baseline (formule inline)
    zoom: Image.Image | None     # versione grande (pan sull'orologio) o None
    kind: str


@dataclass
class _Piece:
    rid: str
    tex: str
    display: bool = True
    type: str = "math"
    where: str = ""


def circle_scale(w: int, h: int, radius: float, maxw: int, maxh: int) -> float:
    s = min(1.0, maxw / w, maxh / h)
    d = math.hypot(w / 2, h / 2)
    if d * s > radius:
        s = radius / d
    return s


def _scale_gray(gray: Image.Image, s: float, ascent: int | None):
    if abs(s - 1.0) < 1e-3:
        return gray, ascent
    w = max(1, round(gray.width * s))
    h = max(1, round(gray.height * s))
    return gray.resize((w, h), Image.LANCZOS), (round(ascent * s) if ascent is not None else None)


def _levels(gray: Image.Image) -> Image.Image:
    return images.to_levels(gray, invert=None)


class AssetBuilder:
    def __init__(self, doc, rules, profile, workdir: Path, warn):
        self.doc = doc
        self.rules = rules
        self.p = profile
        self.workdir = workdir
        self.warn = warn
        self.stats = {"split": 0, "scaled": 0, "zoom": 0}

    def build(self, jobs: dict) -> dict[str, Asset]:
        latex_jobs = [j for j in jobs.values() if j.type in ("math", "snippet")]
        rasters = render_latex_jobs(latex_jobs, self.doc.preamble, self.doc.root, self.workdir / "r0",
                                    self.rules.math_px_per_em, self.warn)
        assets: dict[str, Asset] = {}
        wide = [j for j in latex_jobs if j.type == "math" and j.display and j.rid in rasters
                and rasters[j.rid].gray.width > self.p.eq_maxw]
        split = self._split_wide(wide, rasters)
        for j in latex_jobs:
            r = rasters.get(j.rid)
            if r is None:
                continue  # formula fallita: resa come testo dal chiamante
            if j.rid in split:
                gray, asc = split[j.rid]
                r = Raster(gray, asc, True)
                self.stats["split"] += 1
            kind = "equation" if j.type == "math" and j.display else ("inline" if j.type == "math" else "snippet")
            assets[j.rid] = self._fit(r, kind)
        for j in jobs.values():
            if j.type == "file":
                try:
                    r = render_figure(j.path, self.rules.figure_zoom_dpi)
                except Exception as e:  # file grafico illeggibile: avviso, non errore fatale
                    self.warn.add("immagine", f"impossibile leggere {j.path.name}: {e}")
                    continue
                gray = r.gray
                lv = images.trim(_levels(gray))
                # ritaglia anche la versione in grigi sullo stesso riquadro
                assets[j.rid] = self._fit_levels(lv, "figure")
        return assets

    # ----------------------------------------------------------- equazioni larghe
    def _split_wide(self, wide, rasters):
        """Ritorna rid -> (immagine composta, ascent) per le equazioni spezzate.

        Livelli di spezzamento, applicati solo ai pezzi ancora troppo larghi:
        righe (aligned/cases/sistemi) -> \\qquad -> relazioni -> + e −.
        """
        out = {}
        levels = ["rows", eqsplit.SPACERS, eqsplit.RELATIONS, eqsplit.BINARY]
        # piano: equazione -> lista di atomi (tex, nuova_riga_forzata, livello successivo)
        plans = {j.rid: [(j.tex, True, 0)] for j in wide}
        cache: dict[str, Raster] = {}

        def key_of(tex):
            return eqsplit.leading_op_tex(_strip_spacer(tex))

        for _ in range(len(levels) + 1):
            todo = {}
            for atoms in plans.values():
                for tex, _, _ in atoms:
                    k = key_of(tex)
                    if k not in cache and k not in todo:
                        todo[k] = _Piece("p" + short_hash(k), k)
            if todo:
                rs = render_latex_jobs(list(todo.values()), self.doc.preamble, self.doc.root,
                                       self.workdir / f"split{len(cache)}", self.rules.math_px_per_em, _Quiet())
                for k, piece in todo.items():
                    if piece.rid in rs:
                        cache[k] = rs[piece.rid]
            changed = False
            for rid, atoms in plans.items():
                new_atoms = []
                for tex, hard, lvl in atoms:
                    r = cache.get(key_of(tex))
                    if r is None or r.gray.width <= self.p.eq_maxw or lvl >= len(levels):
                        new_atoms.append((tex, hard, lvl))
                        continue
                    changed = True
                    wrapped = eqsplit.wrap_text_piece(tex, self._px_to_pt(self.p.eq_maxw - self.p.eq_indent))
                    if wrapped and (lvl >= len(levels) - 1 or eqsplit.TEXT_CMD.match(_strip_spacer(tex))):
                        new_atoms.append((wrapped, hard, len(levels)))
                        continue
                    if levels[lvl] == "rows":
                        rows = eqsplit.unwrap_rows(tex)
                        parts = rows if rows and len(rows) > 1 else [tex]
                        forced = [True] * len(parts) if len(parts) > 1 else [hard]
                    else:
                        parts = eqsplit.split_points(tex, levels[lvl])
                        forced = [hard] + [levels[lvl] is eqsplit.SPACERS] * (len(parts) - 1)
                    if len(parts) > 1:
                        forced[0] = hard
                    # i pezzi tornano al livello "rows" se sono a loro volta sistemi
                    for part, f in zip(parts, forced):
                        nxt = 0 if (levels[lvl] != "rows" and eqsplit.unwrap_rows(part)) else lvl + 1
                        new_atoms.append((part, f, nxt if len(parts) > 1 else lvl + 1))
                plans[rid] = new_atoms
            if not changed:
                break
        for j in wide:
            atoms = plans[j.rid]
            groups, cur = [], []
            ok = True
            for tex, hard, _ in atoms:
                if hard and cur:
                    groups.append(cur)
                    cur = []
                r = cache.get(key_of(tex))
                if r is None:
                    ok = False
                    break
                cur.append((_strip_ws(r.gray), r.ascent or r.gray.height))
            if not ok:
                continue
            if cur:
                groups.append(cur)
            lines = []
            for gi, g in enumerate(groups):
                widths = [im.width for im, _ in g]
                for idx in eqsplit.pack(widths, self.p.eq_maxw, self.p.eq_indent, first_indented=gi > 0):
                    lines.append([g[k] for k in idx])
            if len(lines) <= 1:
                continue
            img, asc = eqsplit.compose(lines, gap=self.p.eq_line_gap, indent=self.p.eq_indent)
            out[j.rid] = (img, asc)
        return out

    def _px_to_pt(self, px: float) -> float:
        from .render import PT_PER_IN, base_font_pt
        dpi = self.rules.math_px_per_em * PT_PER_IN / base_font_pt(self.doc.preamble)
        return px / dpi * PT_PER_IN

    # ----------------------------------------------------------- dimensionamento
    def _fit(self, r: Raster, kind: str) -> Asset:
        gray, asc = r.gray, r.ascent
        if kind == "equation":
            # le equazioni possono essere alte: l'impaginazione le divide tra le pagine
            s = min(1.0, self.p.eq_maxw / gray.width)
        else:
            maxw = self.p.inline_maxw if kind == "inline" else self.p.fig_maxw
            s = circle_scale(gray.width, gray.height, self.p.fit_radius, maxw, self.p.img_maxh)
        zoom = None
        if s < 0.999:
            self.stats["scaled"] += 1
        if s < self.p.zoom_threshold:
            zoom = self._zoom_version(gray)
        g2, a2 = _scale_gray(gray, s, asc)
        return Asset(_levels(g2), a2, zoom, kind)

    def _fit_levels(self, lv: Image.Image, kind: str) -> Asset:
        disp = images.levels_to_display(lv)
        s = circle_scale(lv.width, lv.height, self.p.fit_radius, self.p.fig_maxw, self.p.img_maxh)
        zoom = None
        if s < self.p.zoom_threshold:
            zoom = self._zoom_version(disp, invert=False)
        g2, _ = _scale_gray(disp, s, None)
        return Asset(images.to_levels(g2, invert=False, gamma=1.0), None, zoom, kind)

    def _zoom_version(self, gray: Image.Image, invert=None) -> Image.Image:
        self.stats["zoom"] += 1
        s = min(1.0, self.p.zoom_max / gray.width, self.p.zoom_max / gray.height)
        g2, _ = _scale_gray(gray, s, None)
        return images.to_levels(g2, invert=invert, gamma=1.0 if invert is False else 0.8)


class _Quiet:
    def add(self, *a, **k):
        pass


def _strip_spacer(tex: str) -> str:
    t = tex.strip()
    for sp in ("\\qquad", "\\quad", ","):
        if t.startswith(sp) and sp != ",":
            t = t[len(sp):].strip()
    return t


def _strip_ws(gray: Image.Image) -> Image.Image:
    """Toglie il bordo bianco orizzontale (lasciando 2 px)."""
    inv = gray.point(lambda v: 255 - v)
    bbox = inv.getbbox()
    if not bbox:
        return gray
    l, _, r, _ = bbox
    return gray.crop((max(0, l - 2), 0, min(gray.width, r + 2), gray.height))
