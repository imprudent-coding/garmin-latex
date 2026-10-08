"""Immagini per l'orologio: 4 livelli di grigio (2 bit), bianco su nero, RLE.

Formato RLE (vedi shared/FORMAT.md): sequenza di byte in ordine raster
(riga per riga, da sinistra a destra); ogni byte = (valore << 6) | (lunghezza - 1),
valore 0..3 (0 = nero/sfondo, 3 = bianco), lunghezza 1..64.
"""
from __future__ import annotations

import base64

from PIL import Image, ImageOps

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
    head, _, b64 = s.partition("|")
    f = [int(x) for x in head.split(",")]
    data = base64.b64decode(b64)
    if len(f) >= 4:  # schema 2: RLE compresso con LZ
        data = lz.decompress(data, f[3])
    return rle_decode(data, f[0], f[1])


def levels_to_display(levels: Image.Image) -> Image.Image:
    """Valori 0..3 -> grigi 0..255 (per anteprime)."""
    return levels.point([0, 85, 170, 255] + [255] * 252)
