"""PDF -> pagine dell'orologio fatte di strisce d'immagine (simulazioni d'esame).

Il PDF da leggere è il formato "orologio" delle simulazioni d'esame
(Gasdynamics-fork, simulazione_esame/<cartella>/orologio.pdf): testo in una
colonna stretta a sinistra e un margine destro largo, vuoto. La colonna è
dichiarata nelle parole chiave del PDF ("colonna=<sinistra>cm+<larghezza>cm").

Come si taglia:
1. le pagine si rasterizzano in modo che la colonna sia larga STRIP_W pixel;
2. le righe orizzontali con inchiostro formano dei blocchi (una riga di testo,
   un'equazione, una figura...), separati da righe vuote;
3. un blocco che sporge di poco oltre la colonna (equazione lunga) resta nel
   testo, rimpicciolito alla sua larghezza; uno che sporge di più (tabella,
   figura: nel formato orologio le figure sono più larghe della colonna apposta)
   ha una pagina per sé, rimpicciolito per stare nel cerchio, con lo zoom;
4. gli altri blocchi si impilano, con la loro spaziatura, in strisce alte al
   massimo quanto entra nel cerchio con larghezza STRIP_W: una striscia per
   pagina, al centro dello schermo. Un taglio cade sempre fra due blocchi,
   quindi mai a metà di una riga, e non lascia sola in fondo la prima riga di
   un paragrafo o di un titolo. Le strisce con un'equazione rimpicciolita hanno
   lo zoom.
Il risultato sono pagine nel formato del bundle (righe "P" e "I", shared/FORMAT.md):
l'orologio le disegna come qualsiasi altra pagina con immagini.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from . import images
from .assets import circle_scale
from .layout import ImageItem, Page

STRIP_W = 262          # larghezza della colonna sullo schermo (px)
INK = 200              # sotto questo grigio un pixel è inchiostro
WIDE_TOL = 6           # px oltre la colonna tollerati prima di considerare un blocco largo
MAX_GAP = 26           # spazio verticale massimo conservato fra due blocchi (px)
PAGE_GAP = 12          # spazio fra blocchi di pagine PDF diverse
PAD = 3
PARA_GAP = 12          # spazio fra blocchi da cui si riconosce l'inizio di un paragrafo o titolo
ZOOM = 2               # fattore di ingrandimento della versione zoom
SHRINK_MAX = 1.45      # un blocco fino a 1,45 volte la colonna resta nel testo, rimpicciolito
DEFAULT_COLUMN = (0.2, 4.6)  # cm, se il PDF non la dichiara


@dataclass
class Block:
    page: int
    y0: int
    y1: int  # esclusivo
    x0: int
    x1: int  # esclusivo
    kind: str = "text"   # text | shrink | page (vedi classify)


def pdf_info(pdf: Path) -> dict[str, str]:
    p = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True, check=True)
    out = {}
    for line in p.stdout.splitlines():
        k, sep, v = line.partition(":")
        if sep:
            out[k.strip()] = v.strip()
    return out


def column_cm(info: dict[str, str]) -> tuple[float, float]:
    m = re.search(r"colonna\s*=\s*([\d.]+)\s*cm\s*\+\s*([\d.]+)\s*cm", info.get("Keywords", ""))
    return (float(m.group(1)), float(m.group(2))) if m else DEFAULT_COLUMN


def rasterize(pdf: Path, dpi: float) -> list[Image.Image]:
    with tempfile.TemporaryDirectory(prefix="gwstrips-") as tmp:
        subprocess.run(["pdftoppm", "-r", f"{dpi:.3f}", "-png", str(pdf), str(Path(tmp) / "p")], check=True)
        files = sorted(Path(tmp).glob("p-*.png"), key=lambda f: int(f.stem.split("-")[-1]))
        return [Image.open(f).convert("RGB").copy() for f in files]


def ink_blocks(page: Image.Image, page_no: int) -> list[Block]:
    """Blocchi di righe con inchiostro (separati da almeno una riga vuota)."""
    mask = page.convert("L").point(lambda v: 255 if v < INK else 0)
    _, rows = mask.getprojection()
    blocks, start = [], None
    for y, inked in enumerate(list(rows) + [0]):
        if inked and start is None:
            start = y
        elif not inked and start is not None:
            l, _, r, _ = mask.crop((0, start, mask.width, y)).getbbox()
            blocks.append(Block(page_no, start, y, l, r))
            start = None
    return blocks


def classify(blocks: list[Block], col_left: int, col_right: int, max_h: int) -> list[list[Block]]:
    """Assegna a ogni blocco il tipo e li raggruppa: [blocco "page", pezzi...] o [blocco].

    - "text": sta nella colonna (con WIDE_TOL di tolleranza);
    - "shrink": sporge di poco (fino a SHRINK_MAX volte la colonna, es. un'equazione
      lunga) e resta nel testo, rimpicciolito alla larghezza della colonna;
    - "page": sporge di più o è più alto di una striscia (figure, tabelle): pagina
      per sé. I blocchi che lo seguono a meno di MAX_GAP/2 sulla stessa pagina PDF
      ne fanno parte (pezzi della stessa figura separati da una riga vuota)."""
    groups: list[list[Block]] = []
    for b in blocks:
        width = b.x1 - min(col_left, b.x0)
        h = b.y1 - b.y0
        if b.x1 <= col_right + WIDE_TOL and h <= max_h:
            b.kind = "text"
        elif width <= SHRINK_MAX * STRIP_W and h * STRIP_W / width <= max_h / 2:
            b.kind = "shrink"
        else:
            b.kind = "page"
        prev = groups[-1] if groups else None
        if prev and prev[0].kind == "page" and prev[-1].page == b.page and b.y0 - prev[-1].y1 < MAX_GAP // 2:
            prev.append(b)
        else:
            groups.append([b])
    return groups


def strip_height(profile, width: int) -> int:
    """Altezza massima di una striscia larga `width`, centrata sullo schermo."""
    h = 0
    while True:
        nh = h + 2
        top, bottom = profile.r - nh / 2, profile.r + nh / 2
        if top < profile.top or bottom > profile.bottom or profile.band(top, bottom)[1] < width:
            return h
        h = nh


def _gap(prev: Block | None, b: Block) -> int:
    if prev is None:
        return 0
    return min(MAX_GAP, b.y0 - prev.y1) if b.page == prev.page else PAGE_GAP


def compose(pages: list[Image.Image], blocks: list[Block], x0: int, x1: int | None, scale: int = 1,
            width: int | None = None) -> Image.Image:
    """Blocchi uno sotto l'altro con la loro spaziatura (al più MAX_GAP), allineati a sinistra.

    Ogni blocco si ritaglia da x0 a max(x1, fine del blocco); se `width` è dato,
    i blocchi più larghi si rimpiccioliscono a quella larghezza. Coordinate in
    pixel della risoluzione normale; `scale` è il fattore delle pagine passate."""
    parts, prev = [], None
    for b in blocks:
        right = max(x1 or 0, b.x1 + PAD)
        im = pages[b.page].crop((x0 * scale, b.y0 * scale, right * scale, b.y1 * scale))
        if width is not None and im.width > width * scale:
            im = images.resize_levels(im, width * scale)
        parts.append((_gap(prev, b) * scale, im))
        prev = b
    w = width * scale if width is not None else max(im.width for _, im in parts)
    out = Image.new(parts[0][1].mode, (w, sum(g + im.height for g, im in parts) + 2 * PAD * scale), "white")
    y = PAD * scale
    for g, im in parts:
        y += g
        out.paste(im, (0, y))
        y += im.height
    return out


def is_photo(img: Image.Image) -> bool:
    """Fotografia (molti grigi intermedi): non si inverte, resta come nella stampa."""
    gray = img.convert("L")
    hist = gray.histogram()
    return sum(hist[50:200]) > 0.25 * gray.width * gray.height


@dataclass
class StripPage:
    """Una pagina: striscia di testo (livelli di grigio) o figura/tabella (livelli di
    grigio o, se colorata, a colori: shared/FORMAT.md)."""
    normal: Image.Image          # livelli 0..3, o RGB se color
    zoom: Image.Image | None
    color: bool = False
    invert: bool = True          # solo per color: sfondo bianco -> nero

    def encode(self) -> tuple[str, str]:
        """Stringhe trasmesse (normale, zoom o "")."""
        if self.color:
            return (images.encode_color(self.normal, self.invert),
                    images.encode_color(self.zoom, self.invert) if self.zoom is not None else "")
        return (images.encode_resource(self.normal),
                images.encode_resource(self.zoom) if self.zoom is not None else "")


def build_pages(pdf: Path, profile) -> tuple[list[StripPage], dict]:
    info = pdf_info(pdf)
    left_cm, width_cm = column_cm(info)
    dpi = STRIP_W / (width_cm / 2.54)
    pages = rasterize(pdf, dpi)
    zpages = rasterize(pdf, dpi * ZOOM)
    col_left = round(left_cm / 2.54 * dpi)
    col_right = col_left + STRIP_W
    x0 = max(0, col_left - PAD)
    full_w = STRIP_W + 2 * PAD
    max_h = strip_height(profile, full_w)
    blocks = [b for i, p in enumerate(pages) for b in ink_blocks(p, i)]
    out: list[StripPage] = []
    run: list[Block] = []

    def height(b: Block) -> int:
        h = b.y1 - b.y0
        w = b.x1 + PAD - x0
        return round(h * full_w / w) if w > full_w else h

    def run_h(bs):
        return 2 * PAD + sum(_gap(p, b) + height(b) for p, b in zip([None] + bs[:-1], bs))

    def flush():
        nonlocal run
        if run:
            img = compose(pages, run, x0, col_right + PAD, width=full_w)
            zoom = None
            if any(b.kind == "shrink" for b in run):
                zoom = images.to_levels(compose(zpages, run, x0, col_right + PAD, scale=ZOOM, width=full_w),
                                        invert=True)
            out.append(StripPage(images.to_levels(img, invert=True), zoom))
            run = []

    for g in classify(blocks, col_left, col_right, max_h):
        if g[0].kind == "page":
            flush()
            gx0 = max(0, min(col_left, min(b.x0 for b in g)) - PAD)
            img = compose(pages, g, gx0, None)
            s = circle_scale(img.width, img.height, profile.fit_radius, profile.size - 2 * profile.margin,
                             profile.bottom - profile.top)
            normal = images.resize_levels(img, max(1, round(img.width * s))) if s < 1 else img
            zimg = compose(zpages, g, gx0, None, scale=ZOOM)
            if zimg.width > profile.zoom_max:
                zimg = images.resize_levels(zimg, profile.zoom_max)
            inv = not is_photo(img)
            if images.is_colorful(img):
                # schemi e figure con linee colorate: a colori, con la palette dell'immagine
                out.append(StripPage(normal.convert("RGB"), zimg.convert("RGB"), color=True, invert=inv))
            else:
                out.append(StripPage(images.to_levels(normal, invert=inv), images.to_levels(zimg, invert=inv)))
            continue
        b = g[0]
        if run and run_h(run + [b]) > max_h:
            # niente righe orfane: se la striscia finisce con la sola prima riga di un
            # paragrafo o di un titolo (preceduta da uno spazio ampio), passa alla successiva
            carry = []
            if len(run) > 1 and _gap(run[-2], run[-1]) >= PARA_GAP:
                carry = [run.pop()]
            flush()
            run = carry
        run.append(b)
    flush()
    meta = {"title": info.get("Title", "") or pdf.parent.name, "dpi": dpi, "blocks": len(blocks),
            "strip_h": max_h}
    return out, meta


def layout_pages(strips: list[StripPage], keys: list[tuple[str, str]], profile) -> list[str]:
    """Una striscia per pagina, centrata. keys: (chiave, chiave zoom) di ogni striscia."""
    pages = []
    for sp, (k, z) in zip(strips, keys):
        w, h = sp.normal.size
        pg = Page([ImageItem(int(profile.r - w / 2), int(profile.r - h / 2), w, h, 0, k, z)])
        pages.append(pg.encode())
    return pages


@dataclass
class ExamLabel:
    prova: str   # "14/09/2026" (o il nome della cartella, se manca la data)
    qid: str     # "E2" ("" se il titolo non dice il numero dell'esercizio)
    topic: str   # argomento


def exam_label(pdf_title: str, folder: str) -> ExamLabel:
    """Prova, esercizio e argomento dal titolo del PDF
    ("Prova del 14/09/2026 – Esercizio 2: argomento", da \\esercizio del preambolo);
    in mancanza, la data dal nome della cartella (AAAA-MM-GG_...)."""
    t = re.sub(r"\s+", " ", pdf_title).strip()
    m = re.match(r"(?:Prova del\s+)?(\d{1,2}/\d{1,2}/\d{4})\s*[–—-]+\s*Esercizio\s+(\w+)\s*:?\s*(.*)$", t)
    if m:
        return ExamLabel(m.group(1), "E" + m.group(2), m.group(3) or folder)
    d = re.match(r"(\d{4})-(\d{2})-(\d{2})", folder)
    prova = f"{d.group(3)}/{d.group(2)}/{d.group(1)}" if d else "Altre simulazioni"
    return ExamLabel(prova, "", t or folder)


def prova_sort_key(prova: str) -> tuple:
    """Ordine cronologico delle prove ("GG/MM/AAAA"); le altre in fondo."""
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})$", prova)
    return (1, int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else (0, 0, 0, 0)


def find_exams(root: Path) -> list[Path]:
    """PDF in formato orologio: <root>/<cartella>/orologio.pdf, in ordine di cartella."""
    return sorted(root.glob("*/orologio.pdf"))


def code_hash() -> str:
    """Impronta del codice che produce le strisce: un PDF già convertito in un bundle
    precedente si riusa solo se anche questa è uguale."""
    here = Path(__file__).parent
    h = hashlib.sha256()
    for name in ("pdfstrips.py", "images.py", "lz.py", "assets.py", "layout.py", "profile.py"):
        h.update((here / name).read_bytes())
    return h.hexdigest()[:12]
