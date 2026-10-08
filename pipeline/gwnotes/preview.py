"""Anteprima delle pagine come le disegna l'orologio (implementazione di riferimento).

Usa gli stessi font bitmap compilati nell'app e la stessa semantica di disegno
descritta in shared/FORMAT.md, così le PNG generate in CI mostrano fedelmente
il risultato sul vivoactive 5.
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

from . import images
from .paths import FONT_GENERATED
from .rich import BASE, CODES, PARAM_BASE

PALETTE = {
    0: (255, 255, 255),   # testo
    1: (255, 181, 74),    # titoli
    2: (154, 154, 154),   # attenuato (didascalie, metadati)
    3: (127, 212, 255),   # enfasi
    4: (111, 227, 180),   # titoli e barre dei riquadri
    5: (127, 212, 255),   # link
    6: (255, 107, 107),   # avvisi
}
IMG_LEVELS = [(0, 0, 0), (85, 85, 85), (170, 170, 170), (255, 255, 255)]
KIND_BY_CODE = {v: k for k, v in CODES.items()}
END_CODE = 15
GAP_CODE = 16


class FntFont:
    def __init__(self, fnt: Path):
        txt = fnt.read_text(encoding="utf-8")
        common = dict(re.findall(r"(\w+)=(\d+)", re.search(r"^common .*$", txt, re.M).group(0)))
        self.base = int(common["base"])
        self.line = int(common["lineHeight"])
        page_file = re.search(r'page id=0 file="([^"]+)"', txt).group(1)
        self.atlas = Image.open(fnt.parent / page_file).convert("L")
        self.chars = {}
        for m in re.finditer(r"^char (.*)$", txt, re.M):
            d = {k: int(v) for k, v in re.findall(r"(\w+)=(-?\d+)", m.group(1))}
            self.chars[d["id"]] = d

    def width(self, s: str) -> int:
        return sum(self.chars.get(ord(c), {"xadvance": 0})["xadvance"] for c in s)

    def draw(self, img: Image.Image, x: int, top: int, s: str, color):
        for c in s:
            g = self.chars.get(ord(c))
            if not g:
                continue
            if g["width"] and g["height"]:
                mask = self.atlas.crop((g["x"], g["y"], g["x"] + g["width"], g["y"] + g["height"]))
                img.paste(Image.new("RGB", mask.size, color), (x + g["xoffset"], top + g["yoffset"]), mask)
            x += g["xadvance"]
        return x


class Renderer:
    def __init__(self, resources: dict[str, str] | None = None, font_dir: Path = FONT_GENERATED):
        self.fonts = {n: FntFont(font_dir / f"{n}.fnt") for n in ("body", "bold", "small")}
        self.resources = resources or {}   # chiave immagine -> stringa codificata
        self._cache: dict[str, Image.Image] = {}

    def image(self, key: str) -> Image.Image | None:
        if key not in self._cache:
            s = self.resources.get(key)
            if s is None:
                return None
            lv = images.decode_resource(s)
            rgb = Image.new("RGB", lv.size)
            rgb.putdata([IMG_LEVELS[v] for v in lv.getdata()])
            self._cache[key] = rgb
        return self._cache[key]

    def draw_text(self, img, d: ImageDraw.ImageDraw, x: int, baseline: int, text: str):
        stack = []  # (kind, param, start_x)
        i, n = 0, len(text)
        run = ""

        def cur_font():
            kinds = [k for k, _, _ in stack]
            if "sub" in kinds or "sup" in kinds or "small" in kinds:
                return self.fonts["small"]
            if "bold" in kinds:
                return self.fonts["bold"]
            return self.fonts["body"]

        def offset(st):
            off = 0
            for k, p, _ in st:
                if k == "sub":
                    off -= p
                elif k == "sup":
                    off += p
            return off

        def color(st):
            c = 0
            for k, p, _ in st:
                if k == "color":
                    c = p
            return PALETTE.get(c, PALETTE[0])

        def flush():
            nonlocal x, run
            if run:
                f = cur_font()
                x = f.draw(img, x, baseline - offset(stack) - f.base, run, color(stack))
                run = ""

        while i < n:
            c = ord(text[i])
            if BASE <= c < BASE + 0x100:
                flush()
                code = c - BASE
                if code == END_CODE:
                    if stack:
                        kind, param, sx = stack.pop()
                        self.decor(d, kind, param, sx, x, baseline - offset(stack), color(stack))
                    i += 1
                    continue
                param = ord(text[i + 1]) - PARAM_BASE if i + 1 < n else 0
                if code == GAP_CODE:
                    x += param
                else:
                    stack.append((KIND_BY_CODE.get(code, "?"), param, x))
                i += 2
                continue
            run += text[i]
            i += 1
        flush()

    @staticmethod
    def decor(d, kind, p, sx, ex, base, col):
        mid = (sx + ex) // 2
        if kind == "ul":
            d.rectangle([sx, base + p, ex - 1, base + p + 1], fill=col)
        elif kind == "uul":
            d.rectangle([sx, base + p, ex - 1, base + p + 1], fill=col)
            d.rectangle([sx, base + p + 4, ex - 1, base + p + 5], fill=col)
        elif kind == "hat":
            y = base - p
            d.line([(mid - 5, y + 4), (mid, y), (mid + 5, y + 4)], fill=col, width=2)
        elif kind == "dot":
            y = base - p
            d.rectangle([mid - 1, y - 2, mid + 1, y], fill=col)
        elif kind == "ddot":
            y = base - p
            d.rectangle([mid - 4, y - 2, mid - 2, y], fill=col)
            d.rectangle([mid + 2, y - 2, mid + 4, y], fill=col)
        elif kind == "tilde":
            y = base - p
            d.line([(mid - 6, y + 1), (mid - 3, y - 2), (mid + 3, y + 1), (mid + 6, y - 2)], fill=col, width=2)
        elif kind == "bar":
            y = base - p
            d.rectangle([sx, y - 1, ex - 1, y], fill=col)
        elif kind in ("vec", "uarr"):
            y = base - p if kind == "vec" else base + p
            d.rectangle([sx, y - 1, ex - 1, y], fill=col)
            d.line([(ex - 5, y - 4), (ex - 1, y), (ex - 5, y + 3)], fill=col, width=2)

    def render_page(self, page_src: str, page_no: int, total: int, mask=True) -> Image.Image:
        img = Image.new("RGB", (390, 390), (0, 0, 0))
        d = ImageDraw.Draw(img)
        for line in page_src.split("\n"):
            if not line or line == "P":
                continue
            t, rest = line[0], line[1:]
            if t == "T":
                x, y, text = rest.split(",", 2)
                self.draw_text(img, d, int(x), int(y), text)
            elif t == "I":
                x, y, w, h, sy, key, zoom = rest.split(",", 6)
                im = self.image(key)
                if im is not None:
                    crop = im.crop((0, int(sy), int(w), int(sy) + int(h)))
                    img.paste(crop, (int(x), int(y)))
                else:
                    d.rectangle([int(x), int(y), int(x) + int(w), int(y) + int(h)], outline=(80, 80, 80))
                if zoom:
                    d.text((int(x) + int(w) - 10, int(y)), "+", fill=PALETTE[4])
            elif t == "R":
                x, y, w, h, c = (int(v) for v in rest.split(","))
                d.rectangle([x, y, x + w - 1, y + h - 1], fill=PALETTE.get(c, PALETTE[0]))
        # numero di pagina (come lo disegna l'orologio)
        f = self.fonts["small"]
        label = f"{page_no}/{total}"
        f.draw(img, 195 - f.width(label) // 2, 362, label, PALETTE[2])
        if mask:
            m = Image.new("L", img.size, 0)
            ImageDraw.Draw(m).ellipse([0, 0, 389, 389], fill=255)
            bg = Image.new("RGB", img.size, (40, 40, 40))
            bg.paste(img, (0, 0), m)
            ImageDraw.Draw(bg).ellipse([0, 0, 389, 389], outline=(90, 90, 90))
            img = bg
        return img


def contact_sheet(pages: list[Image.Image], cols: int = 4, pad: int = 10) -> Image.Image:
    rows = (len(pages) + cols - 1) // cols
    w = cols * 390 + (cols + 1) * pad
    h = rows * 390 + (rows + 1) * pad
    sheet = Image.new("RGB", (w, h), (24, 24, 24))
    for k, p in enumerate(pages):
        r, c = divmod(k, cols)
        sheet.paste(p, (pad + c * (390 + pad), pad + r * (390 + pad)))
    return sheet


# ---------------------------------------------------------------- elenco delle domande
# Stessa disposizione di garmin/source/QuestionList.mc (righe compatte, voce
# selezionata espansa al centro).

ROW_H = 30        # riga compatta (font piccolo)
HEAD_H = 30       # intestazione di gruppo
NARROW_DY = 95    # oltre questa distanza dal centro si usa la riga stretta
TB = chr(0xE01E)


def parse_index(lines: list[str]) -> list[dict]:
    rows, chapters = [], 0
    for l in lines:
        t = l[:1]
        if t == "C":
            chapters += 1
        elif t == "H":
            _, w, text = l.split("|", 2)
            rows.append({"t": "H", "w": int(w), "text": text})
        elif t == "S":
            f = l.split("|", 6)
            rows.append({"t": "S", "id": f[1], "pages": int(f[3]),
                         "fw": [int(x) for x in f[5].split(";") if x], "full": f[6].split(TB)})
        elif t == "Q":
            f = l.split("|", 5)
            r = rows[-1]
            r.update(kind=f[2], qid=f[3], cw=[int(x) for x in f[4].split(";")], compact=f[5].split(TB))
    if chapters <= 1:
        rows = [r for r in rows if r["t"] != "H"]
    return rows


def _sel_height(r) -> int:
    return 14 + len(r["full"]) * 34 + 23 + 6


def render_index(renderer: "Renderer", rows: list[dict], sel: int, status: str = "Aggiornato") -> Image.Image:
    img = Image.new("RGB", (390, 390), (0, 0, 0))
    d = ImageDraw.Draw(img)
    small = renderer.fonts["small"]
    selectable = [i for i, r in enumerate(rows) if r["t"] == "S"]
    si = selectable[sel]
    r = rows[si]
    h = _sel_height(r)
    top = 195 - h // 2
    # voce selezionata: sfondo leggero, titolo completo in arancio
    d.rounded_rectangle([20, top, 369, top + h], radius=14, fill=(26, 26, 26))
    y = top + 8 + 25
    for k, line in enumerate(r["full"]):
        w = r["fw"][k] if k < len(r["fw"]) else 200
        renderer.draw_text(img, d, 195 - w // 2, y, _with_base(line, 1))
        y += 34
    sub = f"{r['pages']} pagine"
    small.draw(img, 195 - small.width(sub) // 2, y - 25, sub, PALETTE[2])

    def draw_row(i, rtop):
        row = rows[i]
        hh = HEAD_H if row["t"] == "H" else ROW_H
        mid = rtop + hh // 2
        base = rtop + hh - 9
        if row["t"] == "H":
            renderer.draw_text(img, d, 195 - row["w"] // 2, base, row["text"])
            d.line([(195 - row["w"] // 2, rtop + 3), (195 + row["w"] // 2, rtop + 3)], fill=(60, 60, 60))
            return
        k = 1 if abs(mid - 195) > NARROW_DY else 0
        renderer.draw_text(img, d, 195 - row["cw"][k] // 2, base, row["compact"][k])

    yy = top
    for i in range(si - 1, -1, -1):
        hh = HEAD_H if rows[i]["t"] == "H" else ROW_H
        yy -= hh
        if yy < 28:
            break
        draw_row(i, yy)
    yy = top + h
    for i in range(si + 1, len(rows)):
        hh = HEAD_H if rows[i]["t"] == "H" else ROW_H
        if yy + hh > 352:
            break
        draw_row(i, yy)
        yy += hh
    small.draw(img, 195 - small.width(status) // 2, 6, status, PALETTE[2])
    pos = f"{sel + 1}/{len(selectable)}"
    small.draw(img, 195 - small.width(pos) // 2, 362, pos, PALETTE[2])
    # arco di posizione a destra
    frac = sel / max(1, len(selectable) - 1)
    d.arc([3, 3, 386, 386], -40, 40, fill=(51, 51, 51), width=3)
    a = -40 + 80 * frac
    d.arc([3, 3, 386, 386], a - 3, a + 3, fill=PALETTE[1], width=5)
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).ellipse([0, 0, 389, 389], fill=255)
    bg = Image.new("RGB", img.size, (40, 40, 40))
    bg.paste(img, (0, 0), m)
    ImageDraw.Draw(bg).ellipse([0, 0, 389, 389], outline=(90, 90, 90))
    return bg


def _with_base(text: str, color: int) -> str:
    """Applica un colore di base a una riga (come RichText.baseColor sull'orologio)."""
    return chr(BASE + CODES["color"]) + chr(PARAM_BASE + color) + text + chr(BASE + 15)
