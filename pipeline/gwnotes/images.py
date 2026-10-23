"""Immagini per l'orologio: 4 livelli di grigio (2 bit), bianco su nero, RLE.

Formato RLE (vedi shared/FORMAT.md): sequenza di byte in ordine raster
(riga per riga, da sinistra a destra); ogni byte = (valore << 6) | (lunghezza - 1),
valore 0..3 (0 = nero/sfondo, 3 = bianco), lunghezza 1..64.
"""
from __future__ import annotations

import base64

from PIL import Image, ImageChops, ImageOps

from . import lz

LEVELS = 4


def to_levels(img: Image.Image, invert: bool | None = None, gamma: float = 0.8) -> Image.Image:
    """Converte in scala di grigi a 4 livelli (valori 0..3) con sfondo nero.

    invert=None: decide guardando il colore dello sfondo (bordo dell'immagine).
    gamma < 1 schiarisce i tratti sottili, che altrimenti sparirebbero.
    """
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.alpha_composite(img)
        img = bg
    g = img.convert("L")
    if invert is None:
        invert = _border_mean(g) > 127
    if invert:
        g = ImageOps.invert(g)
    lut = []
    for v in range(256):
        x = (v / 255.0) ** gamma
        lut.append(min(LEVELS - 1, int(x * LEVELS)))
    return g.point(lut)


def _border_mean(g: Image.Image) -> float:
    w, h = g.size
    px = g.load()
    vals = [px[x, 0] for x in range(w)] + [px[x, h - 1] for x in range(w)]
    vals += [px[0, y] for y in range(h)] + [px[w - 1, y] for y in range(h)]
    return sum(vals) / max(1, len(vals))


def trim(levels: Image.Image, pad: int = 2) -> Image.Image:
    """Rimuove il bordo nero (valore 0) lasciando `pad` pixel."""
    bbox = levels.point(lambda v: 255 if v else 0).getbbox()
    if not bbox:
        return levels
    l, t, r, b = bbox
    w, h = levels.size
    return levels.crop((max(0, l - pad), max(0, t - pad), min(w, r + pad), min(h, b + pad)))


def resize_levels(gray: Image.Image, width: int) -> Image.Image:
    """Ridimensiona un'immagine L (0..255) mantenendo le proporzioni."""
    w, h = gray.size
    if w == width:
        return gray
    height = max(1, round(h * width / w))
    return gray.resize((width, height), Image.LANCZOS)


def rle_encode(levels: Image.Image) -> bytes:
    data = levels.tobytes()
    out = bytearray()
    i, n = 0, len(data)
    while i < n:
        v = data[i]
        j = i + 1
        while j < n and data[j] == v and j - i < 64:
            j += 1
        out.append((v << 6) | (j - i - 1))
        i = j
    return bytes(out)


def rle_decode(buf: bytes, width: int, height: int) -> Image.Image:
    out = bytearray()
    for b in buf:
        out.extend([b >> 6] * ((b & 63) + 1))
    if len(out) != width * height:
        raise ValueError(f"RLE: attesi {width * height} pixel, trovati {len(out)}")
    return Image.frombytes("L", (width, height), bytes(out))


def encode_resource(levels: Image.Image) -> str:
    """Stringa trasmessa all'orologio: "<w>,<h>,2,<byte RLE>|<base64 di LZ(RLE)>"
    (schema 2; vedi shared/FORMAT.md). Senza perdita: LZ comprime l'RLE del ~30%."""
    w, h = levels.size
    rle = rle_encode(levels)
    return f"{w},{h},2,{len(rle)}|" + base64.b64encode(lz.compress(rle)).decode("ascii")


def decode_resource(s: str) -> Image.Image:
    """Immagine dalla stringa trasmessa: livelli 0..3 (modo L) o, per le immagini a
    colori (terzo campo 4), RGB."""
    head, _, b64 = s.partition("|")
    f = [int(x) for x in head.split(",")]
    data = base64.b64decode(b64)
    if len(f) >= 4:  # schema 2: RLE compresso con LZ
        data = lz.decompress(data, f[3])
    if len(f) >= 3 and f[2] == COLOR_BITS:
        return _color_decode(data, f[0], f[1])
    return rle_decode(data, f[0], f[1])


# ------------------------------------------------------------------ immagini a colori
#
# Per figure e schemi colorati (shared/FORMAT.md, «Immagine a colori»):
#   "<w>,<h>,4,<n>|<base64 di LZ(dati)>"
# dati = K, poi K colori (R, G, B), poi l'RLE a 4 bit: ogni byte è (indice << 4) | (lunghezza − 1)
# con lunghezza 1–16. L'indice 0 è lo sfondo nero (non disegnato), 1..K i colori della palette.
# La palette sta nei dati e non nell'intestazione, che resta fatta di soli numeri: le app
# che non conoscono il formato mostrano un'immagine sbagliata ma non si bloccano.

COLOR_BITS = 4
MAX_COLORS = 15          # + lo sfondo = 16 voci nella palette della bitmap dell'orologio


def is_colorful(img: Image.Image, min_pixels: int = 40) -> bool:
    """True se l'immagine ha abbastanza pixel colorati (saturi e non scuri) da meritare i colori."""
    count = _saturated_mask(img.convert("RGB")).histogram()[255]
    return count >= max(min_pixels, img.width * img.height // 2000)


def invert_keep_hue(img: Image.Image) -> Image.Image:
    """Sfondo bianco -> nero e tratti neri -> bianchi, mantenendo la tinta dei colori
    (inversione RGB e rotazione della tinta di 180°: una linea rossa resta rossa)."""
    inv = ImageOps.invert(img.convert("RGB"))
    h, sat, val = inv.convert("HSV").split()
    h = h.point(lambda v: (v + 128) % 256)
    return Image.merge("HSV", (h, sat, val)).convert("RGB")


GRAYS = 8                # livelli di grigio della palette (nero = sfondo compreso)


def _saturated_mask(rgb: Image.Image) -> Image.Image:
    _, sat, val = rgb.convert("HSV").split()
    return ImageChops.multiply(sat.point(lambda v: 255 if v > 90 else 0),
                               val.point(lambda v: 255 if v > 80 else 0))


def color_palette(rgb: Image.Image) -> list[tuple[int, int, int]]:
    """Palette di un'immagine a colori: GRAYS grigi (fotografie, tratti, testo) e fino a
    MAX_COLORS + 1 − GRAYS colori scelti fra i soli pixel colorati, così le linee colorate
    sottili (urti, annotazioni) non si perdono fra i grigi di una fotografia."""
    grays = [(round(255 * i / (GRAYS - 1)),) * 3 for i in range(GRAYS)]
    mask = _saturated_mask(rgb)
    rb, mb = rgb.tobytes(), mask.tobytes()
    px = [tuple(rb[3 * i:3 * i + 3]) for i, m in enumerate(mb) if m]
    hues: list[tuple[int, int, int]] = []
    if px:
        strip = Image.new("RGB", (len(px), 1))
        strip.putdata(px)
        q = strip.quantize(colors=MAX_COLORS + 1 - GRAYS, method=Image.Quantize.MEDIANCUT,
                           dither=Image.Dither.NONE)
        pal = q.getpalette() or []
        hues = [tuple(pal[3 * i:3 * i + 3]) for i in sorted(set(q.tobytes()))]
    return grays + hues


def encode_color(img: Image.Image, invert: bool = True) -> str:
    """Stringa trasmessa per un'immagine a colori (sfondo nero + al più MAX_COLORS colori)."""
    rgb = img.convert("RGB")
    if invert:
        rgb = invert_keep_hue(rgb)
    palette = color_palette(rgb)            # palette[0] = nero = sfondo
    pimg = Image.new("P", (1, 1))
    flat = [c for col in palette for c in col]
    pimg.putpalette(flat + flat[-3:] * (256 - len(palette)))
    q = rgb.quantize(palette=pimg, dither=Image.Dither.NONE)
    data = [min(v, len(palette) - 1) for v in q.tobytes()]
    raw = bytearray([len(palette) - 1])
    for col in palette[1:]:
        raw += bytes(col)
    i, n = 0, len(data)
    while i < n:
        v = data[i]
        j = i + 1
        while j < n and data[j] == v and j - i < 16:
            j += 1
        raw.append((v << 4) | (j - i - 1))
        i = j
    w, h = rgb.size
    return f"{w},{h},{COLOR_BITS},{len(raw)}|" + base64.b64encode(lz.compress(bytes(raw))).decode("ascii")


def _color_decode(data: bytes, width: int, height: int) -> Image.Image:
    k = data[0]
    pal = [(0, 0, 0)] + [tuple(data[1 + 3 * i:4 + 3 * i]) for i in range(k)]
    px = []
    for b in data[1 + 3 * k:]:
        px.extend([pal[b >> 4]] * ((b & 15) + 1))
    if len(px) != width * height:
        raise ValueError(f"RLE a colori: attesi {width * height} pixel, trovati {len(px)}")
    return Image.frombytes("RGB", (width, height), bytes(c for p in px for c in p))


def levels_to_display(levels: Image.Image) -> Image.Image:
    """Valori 0..3 -> grigi 0..255 (per anteprime)."""
    return levels.point([0, 85, 170, 255] + [255] * 252)
