"""Impaginazione delle sezioni per lo schermo rotondo.

Il risultato è una lista di pagine; ogni pagina è una lista di elementi già
posizionati (testo con baseline, immagini, rettangoli). L'orologio si limita a
disegnarli: tutto il lavoro (misure dei font, a capo, forma rotonda) è fatto qui,
con le stesse metriche dei font compilati nell'app.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field

from . import rich
from .docmodel import BoxEnd, BoxStart, ImageBlock, MathImage, Para
from .rich import CODES, END, GAP, PARAM_BASE, BASE, Styled, plain

_uid = itertools.count(1)
BREAK_AFTER = set("=,+−;⇒→≤≥≈≃<>")


# ------------------------------------------------------------------ elementi di pagina


@dataclass
class TextItem:
    x: int
    y: int  # baseline
    text: str


@dataclass
class ImageItem:
    x: int
    y: int  # bordo superiore
    w: int
    h: int
    sy: int  # prima riga dell'immagine sorgente
    key: str
    zoom: str = ""


@dataclass
class RectItem:
    x: int
    y: int
    w: int
    h: int
    color: int


@dataclass
class Page:
    items: list = field(default_factory=list)

    def encode(self) -> str:
        out = ["P"]
        for it in self.items:
            if isinstance(it, TextItem):
                out.append(f"T{it.x},{it.y},{it.text}")
            elif isinstance(it, ImageItem):
                out.append(f"I{it.x},{it.y},{it.w},{it.h},{it.sy},{it.key},{it.zoom}")
            else:
                out.append(f"R{it.x},{it.y},{it.w},{it.h},{it.color}")
        return "\n".join(out)


# ------------------------------------------------------------------ testo ricco -> pezzi


@dataclass
class Seg:
    text: str
    stack: tuple  # ((kind, param, uid), ...)


@dataclass
class Img:
    rid: str
    stack: tuple


class _Break:
    pass


def font_of(stack) -> str:
    kinds = [k for k, _, _ in stack]
    if "sub" in kinds or "sup" in kinds or "small" in kinds:
        return "small"
    if "bold" in kinds:
        return "bold"
    return "body"


class Layouter:
    def __init__(self, metrics, profile, assets, keys, warn):
        self.m = metrics
        self.p = profile
        self.assets = assets      # rid -> Asset
        self.keys = keys          # rid -> (chiave normale, chiave zoom)
        self.warn = warn

    # -------------------------------------------------- estensione verticale di un gruppo
    def _offset(self, stack) -> int:
        off = 0
        for k, _, _ in stack:
            if k == "sub":
                off -= self.p.sub_drop
            elif k == "sup":
                off += self.p.sup_rise
        return off

    def _extent(self, nodes, stack) -> tuple[int, int]:
        top = bottom = 0
        for n in nodes:
            if isinstance(n, str):
                f = font_of(stack)
                off = self._offset(stack)
                if n.strip():
                    top = max(top, self.m.ink_top(f, n) + off)
                    bottom = max(bottom, self.m.ink_bottom(f, n) - off)
            elif isinstance(n, Styled):
                st = stack + ((n.kind, 0, 0),)
                t, b = self._extent(n.children, st)
                top, bottom = max(top, t), max(bottom, b)
            elif isinstance(n, MathImage):
                a = self.assets.get(n.rid)
                if a:
                    top = max(top, a.ascent or a.normal.height)
                    bottom = max(bottom, a.normal.height - (a.ascent or a.normal.height))
        return top, bottom

    def flatten(self, nodes, stack=()) -> list:
        out = []
        for n in nodes:
            if isinstance(n, str):
                parts = n.split("\n")
                for i, part in enumerate(parts):
                    if i:
                        out.append(_Break())
                    if part:
                        out.append(Seg(part, stack))
            elif isinstance(n, Styled):
                param = n.param
                if n.kind in rich.DECOR:
                    top, bottom = self._extent(n.children, stack)
                    if n.kind in ("ul", "uul", "uarr"):
                        param = bottom + 2
                    else:
                        param = top + 2
                elif n.kind == "sub":
                    param = self.p.sub_drop
                elif n.kind == "sup":
                    param = self.p.sup_rise
                out.extend(self.flatten(n.children, stack + ((n.kind, max(0, param), next(_uid)),)))
            elif isinstance(n, MathImage):
                out.append(Img(n.rid, stack))
            else:
                out.extend(self.flatten([str(n)], stack))
        return out

    # -------------------------------------------------- parole
    def words(self, items) -> list:
        """Ritorna lista di parole; ogni parola = (pezzi, spazio_prima: Seg|None) oppure _Break."""
        words = []
        cur: list = []
        pending_space = None

        def push():
            nonlocal cur, pending_space
            if cur:
                words.append((cur, pending_space))
                pending_space = None
            cur = []

        for it in items:
            if isinstance(it, _Break):
                push()
                pending_space = None
                words.append(_Break())
                continue
            if isinstance(it, Img):
                cur.append(it)
                continue
            text = it.text
            buf = ""
            for ch in text:
                if ch == " ":
                    if buf:
                        cur.append(Seg(buf, it.stack))
                        buf = ""
                    if cur:
                        push()
                    if pending_space is None:
                        pending_space = Seg(" ", it.stack)
                else:
                    buf += ch.replace(" ", " ") if ch == " " else ch
            if buf:
                cur.append(Seg(buf, it.stack))
        push()
        return words

    def piece_w(self, pc) -> int:
        if isinstance(pc, Img):
            a = self.assets.get(pc.rid)
            return a.normal.width if a else 0
        return self.m.width(font_of(pc.stack), pc.text)

    def word_w(self, pieces) -> int:
        return sum(self.piece_w(pc) for pc in pieces)

    def piece_vext(self, pc) -> tuple[int, int]:
        if isinstance(pc, Img):
            a = self.assets.get(pc.rid)
            if not a:
                return 0, 0
            asc = a.ascent if a.ascent is not None else a.normal.height
            return asc, a.normal.height - asc
        f = font_of(pc.stack)
        off = self._offset(pc.stack)
        asc = self.m.ascent(f)
        desc = self.m.line(f) - asc
        return asc + off, desc - off

    def split_long(self, pieces, maxw):
        """Spezza una parola troppo lunga dopo =,+,... oppure carattere per carattere."""
        out, cur, w = [], [], 0
        for pc in pieces:
            if isinstance(pc, Img):
                pw = self.piece_w(pc)
                if cur and w + pw > maxw:
                    out.append(cur)
                    cur, w = [], 0
                cur.append(pc)
                w += pw
                continue
            f = font_of(pc.stack)
            buf = ""
            last_ok = -1
            for ch in pc.text:
                cw = self.m.width(f, ch)
                if w + self.m.width(f, buf) + cw > maxw and (buf or cur):
                    if last_ok >= 0:
                        head, buf = buf[:last_ok + 1], buf[last_ok + 1:]
                        if head:
                            cur.append(Seg(head, pc.stack))
                    elif buf:
                        cur.append(Seg(buf, pc.stack))
                        buf = ""
                    out.append(cur)
                    cur, w, last_ok = [], 0, -1
                buf += ch
                if ch in BREAK_AFTER:
                    last_ok = len(buf) - 1
            if buf:
                cur.append(Seg(buf, pc.stack))
                w += self.m.width(f, buf)
        if cur:
            out.append(cur)
        return out

    # -------------------------------------------------- codifica di una riga
    def encode_line(self, pieces, x0: int, baseline: int, items_out: list) -> str:
        out = []
        open_stack: list = []
        x = x0
        for pc in pieces:
            stack = list(pc.stack)
            common = 0
            while common < len(open_stack) and common < len(stack) and open_stack[common] == stack[common]:
                common += 1
            for _ in range(len(open_stack) - common):
                out.append(END)
            for kind, param, uid in stack[common:]:
                out.append(chr(BASE + CODES[kind]) + chr(PARAM_BASE + int(param)))
            open_stack = stack
            if isinstance(pc, Img):
                a = self.assets.get(pc.rid)
                if a:
                    asc = a.ascent if a.ascent is not None else a.normal.height
                    k, z = self.keys[pc.rid]
                    items_out.append(ImageItem(x, baseline - asc - self._offset(stack), a.normal.width, a.normal.height, 0, k, z))
                    out.append(chr(BASE + GAP) + chr(PARAM_BASE + a.normal.width))
                    x += a.normal.width
                continue
            out.append(pc.text)
            x += self.piece_w(pc)
        for _ in open_stack:
            out.append(END)
        return "".join(out)


class SectionLayout:
    """Impagina una sezione."""

    def __init__(self, lay: Layouter):
        self.L = lay
        self.p = lay.p
        self.pages: list[Page] = []
        self.page: Page | None = None
        self.y = 0
        self.box_depth = 0
        self.box_bars: list[int] = []  # livello di rientro di ciascun riquadro aperto
        self.new_page()

    def new_page(self):
        self.page = Page()
        self.pages.append(self.page)
        self.y = self.p.top

    def at_top(self) -> bool:
        return self.y <= self.p.top + 1

    # ---------------------------------------------------------- testo
    def para(self, para: Para, base_indent: int):
        L = self.L
        nodes = para.nodes
        if para.role == "heading":
            nodes = [rich.color("heading", [rich.bold(nodes)])]
        elif para.role == "title":
            nodes = [rich.color("heading", [rich.bold(nodes)])]
        elif para.role == "boxtitle":
            nodes = [rich.color("boxtitle", [rich.bold(nodes)])]
        elif para.role == "caption":
            nodes = [rich.color("dim", nodes)]
        indent_lvl = base_indent + para.indent
        words = L.words(L.flatten(nodes))
        marker = None
        if para.marker:
            marker = L.flatten([rich.color("heading", para.marker)])
        if para.role in ("heading", "title") and not self.at_top():
            self.y += self.p.heading_gap
        if para.role in ("heading", "title", "boxtitle"):
            # tieni il titolo insieme ad almeno due righe di testo
            need = 3 * (L.m.line("body") + self.p.line_gap)
            if self.y + need > self.p.bottom:
                self.new_page()
        line_h0 = L.m.line("body")
        i = 0
        first = True
        while i < len(words) or (first and not words):
            if not words:
                break
            # misura la riga candidata
            top = self.y
            asc0 = L.m.ascent("body")
            desc0 = line_h0 - asc0
            x_band, w_band = self.p.band(top, top + line_h0)
            indent_px = indent_lvl * self.p.indent
            avail = w_band - indent_px
            if avail < self.p.min_line_w and para.align != "center":
                self.y += 8
                if self.y + line_h0 > self.p.bottom:
                    self.new_page()
                continue
            line, w, j = [], 0, i
            while j < len(words):
                wd = words[j]
                if isinstance(wd, _Break):
                    j += 1
                    if line:
                        break
                    continue
                pieces, space = wd
                ww = L.word_w(pieces)
                sw = L.piece_w(space) if (space and line) else 0
                if line and w + sw + ww > avail:
                    break
                if not line and ww > avail:
                    parts = L.split_long(pieces, avail)
                    words[j:j + 1] = [(parts[0], space)] + [(pp, None) for pp in parts[1:]]
                    pieces, space = words[j]
                    ww = L.word_w(pieces)
                if line and space:
                    line.append(space)
                    w += sw
                line.extend(pieces)
                w += ww
                j += 1
            if not line:
                i = j
                continue
            asc = max([asc0] + [L.piece_vext(pc)[0] for pc in line])
            desc = max([desc0] + [L.piece_vext(pc)[1] for pc in line])
            h = asc + desc
            if top + h > self.p.bottom:
                self.new_page()
                continue
            # ricontrolla la larghezza con l'altezza reale della riga
            x_band, w_band = self.p.band(top, top + h)
            if w > w_band - indent_px + 1 and h > line_h0:
                self.y += 6
                if self.y + h > self.p.bottom:
                    self.new_page()
                continue
            baseline = top + asc
            if para.align == "center":
                x = x_band + (w_band - w) // 2
            else:
                x = x_band + indent_px
            if marker and first:
                mw = L.word_w(marker)
                mt = L.encode_line(marker, x - mw - 6, baseline, self.page.items)
                self.page.items.append(TextItem(x - mw - 6, baseline, mt))
            text = L.encode_line(line, x, baseline, self.page.items)
            self.page.items.append(TextItem(x, baseline, text))
            self._bars(top, h + self.p.line_gap, x_band)
            self.y = top + h + self.p.line_gap
            first = False
            i = j
        self.y += self.p.para_gap

    def _bars(self, top, h, x_band):
        for lvl in self.box_bars:
            self.page.items.append(RectItem(x_band + lvl * self.p.indent + 4, top, self.p.box_bar_w, h,
                                            rich.COLORS["boxtitle"]))

    # ---------------------------------------------------------- immagini
    def image(self, blk: ImageBlock, base_indent: int):
        a = self.L.assets.get(blk.rid)
        if a is None:
            return
        key, zoom = self.L.keys[blk.rid]
        img = a.normal
        w, h = img.width, img.height
        blank = _blank_rows(img)
        sy = 0
        gap = 4
        while sy < h:
            remaining = h - sy
            # cerca la prima posizione y in cui (una parte del)l'immagine entra
            placed = False
            y = self.y + gap
            splittable = blk.kind == "equation"
            while y + 16 <= self.p.bottom:
                hmax = self._fit_height(y, w, min(remaining, self.p.bottom - y))
                need = remaining if (remaining < 40 or not splittable) else 40
                if hmax >= need:
                    take = remaining if hmax >= remaining else _cut(blank, sy, sy + hmax)
                    if take <= 0:
                        take = hmax
                    x = int(self.p.r - w / 2)
                    self.page.items.append(ImageItem(x, y, w, take, sy, key, zoom))
                    xb, _ = self.p.band(y, y + take)
                    self._bars(y - gap, take + gap * 2, xb)
                    sy += take
                    self.y = y + take + gap
                    placed = True
                    break
                y += 6
            if not placed:
                if self.at_top():
                    # non entra nemmeno su una pagina vuota: forza (non dovrebbe succedere)
                    take = min(remaining, self.p.bottom - self.p.top)
                    self.page.items.append(ImageItem(int(self.p.r - w / 2), self.y, w, take, sy, key, zoom))
                    sy += take
                    self.y += take
                self.new_page()
        self.y += self.p.para_gap

    def _fit_height(self, y, w, hmax) -> int:
        """Massima altezza h<=hmax tale che un'immagine larga w entri a partire da y."""
        h = 0
        step = 4
        while h + step <= hmax:
            _, bw = self.p.band(y, y + h + step)
            if bw < w:
                break
            h += step
        if h + step > hmax:
            _, bw = self.p.band(y, y + hmax)
            if bw >= w:
                h = hmax
        return h

    # ---------------------------------------------------------- sezione
    def run(self, section, title_nodes):
        self.para(Para(title_nodes, align="center", role="title"), 0)
        for b in section.blocks:
            if isinstance(b, Para):
                self.para(b, self.box_depth)
            elif isinstance(b, ImageBlock):
                self.image(b, self.box_depth)
            elif isinstance(b, BoxStart):
                if b.title:
                    self.para(Para(b.title, role="boxtitle"), self.box_depth)
                    self.y -= self.p.para_gap - 2
                self.box_bars.append(self.box_depth)
                self.box_depth += 1
            elif isinstance(b, BoxEnd):
                if self.box_bars:
                    self.box_bars.pop()
                    self.box_depth -= 1
                self.y += 4
        # elimina pagine vuote finali
        while len(self.pages) > 1 and not self.pages[-1].items:
            self.pages.pop()
        return self.pages


def _blank_rows(img) -> list[bool]:
    w, h = img.size
    data = img.tobytes()
    return [not any(data[r * w:(r + 1) * w]) for r in range(h)]


def _cut(blank, start, end) -> int:
    """Taglio preferibilmente su una riga vuota tra start e end (ritorna l'altezza presa)."""
    for r in range(end - 1, start + (end - start) // 3, -1):
        if blank[r]:
            return r - start + 1
    return end - start


def encode_title_lines(lay: Layouter, nodes, width: int, max_lines: int = 2):
    """Titolo per i menu: righe codificate + larghezze (per centrarle sull'orologio)."""
    words = lay.words(lay.flatten(nodes))
    lines, cur, w = [], [], 0
    for wd in words:
        if isinstance(wd, _Break):
            continue
        pieces, space = wd
        ww = lay.word_w(pieces)
        sw = lay.piece_w(space) if (space and cur) else 0
        if cur and w + sw + ww > width:
            lines.append((cur, w))
            cur, w, sw = [], 0, 0
        if cur and space:
            cur.append(space)
            w += sw
        cur.extend(pieces)
        w += ww
    if cur:
        lines.append((cur, w))
    if len(lines) > max_lines:
        # ultima riga riempita carattere per carattere, poi "…"
        rest = list(lines[max_lines - 1][0])
        for pieces, _ in lines[max_lines:]:
            rest.append(Seg(" ", ()))
            rest.extend(pieces)
        lines = lines[:max_lines - 1]
        ell = Seg("…", ())
        ew = lay.piece_w(ell)
        out, lw = [], 0
        for pc in rest:
            pw = lay.piece_w(pc)
            if lw + pw + ew <= width:
                out.append(pc)
                lw += pw
                continue
            if isinstance(pc, Seg):
                f = font_of(pc.stack)
                part = ""
                for ch in pc.text:
                    if lw + lay.m.width(f, part + ch) + ew > width:
                        break
                    part += ch
                if part.strip():
                    out.append(Seg(part, pc.stack))
                    lw += lay.m.width(f, part)
            break
        while out and isinstance(out[-1], Seg) and not out[-1].text.strip():
            lw -= lay.piece_w(out.pop())
        out.append(ell)
        lines.append((out, lw + ew))
    enc = []
    for pieces, lw in lines:
        dummy: list = []
        enc.append((lay.encode_line([pc for pc in pieces if not isinstance(pc, Img)], 0, 0, dummy), lw))
    return enc
