"""Testo ricco: Unicode + codici di stile nell'area privata (vedi shared/FORMAT.md).

Rappresentazione interna: lista di "nodi"
  str                          -> testo
  Styled(kind, children)       -> stile annidato (bold, sub, sup, ul, ...)
  Gap(px)                      -> spazio orizzontale (es. per un'immagine inline)

Serializzazione (`encode`): ogni apertura è un carattere U+E000+codice seguito da
un carattere parametro chr(0x100 + valore); la chiusura è END (U+E00F).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache

from .paths import FONT_GENERATED

BASE = 0xE000
CODES = {
    "bold": 1,
    "color": 2,
    "sub": 3,
    "sup": 4,
    "ul": 5,       # sottolineato (vettore)
    "uul": 6,      # doppio sottolineato (matrice)
    "hat": 7,
    "dot": 8,
    "ddot": 9,
    "tilde": 10,
    "bar": 11,
    "vec": 12,     # freccia sopra
    "uarr": 13,    # freccia sotto (diade)
    "box": 14,     # riquadro
    "small": 17,   # testo nel font piccolo (righe compatte dell'elenco)
}
END = chr(BASE + 15)
GAP = 16  # spazio di N pixel, senza chiusura
TITLE_BREAK = chr(BASE + 30)  # separatore di riga nei titoli dell'indice
PARAM_BASE = 0x100

# palette dei colori (indice -> RGB), deve coincidere con garmin/source/Palette.mc
COLORS = {
    "text": 0,
    "heading": 1,
    "dim": 2,
    "emph": 3,
    "boxtitle": 4,
    "link": 5,
    "warn": 6,
}

DECOR = {"ul", "uul", "hat", "dot", "ddot", "tilde", "bar", "vec", "uarr", "box"}


@dataclass
class Styled:
    kind: str
    children: list = field(default_factory=list)
    param: int = 0  # per "color": indice palette


@dataclass
class Gap:
    px: int


# ---------------------------------------------------------------- metriche font


class Metrics:
    def __init__(self, data: dict):
        self.data = data
        self.font_id = data["fontId"]
        self.charset = set(data["charset"])
        self.fonts = data["fonts"]

    def has(self, ch: str) -> bool:
        return ch in self.charset

    def glyph(self, font: str, ch: str):
        return self.fonts[font]["glyphs"].get(str(ord(ch)))

    def width(self, font: str, text: str) -> int:
        g = self.fonts[font]["glyphs"]
        w = 0
        for ch in text:
            m = g.get(str(ord(ch)))
            w += m[0] if m else 0
        return w

    def ascent(self, font: str) -> int:
        return self.fonts[font]["ascent"]

    def line(self, font: str) -> int:
        return self.fonts[font]["lineHeight"]

    def ink_top(self, font: str, text: str) -> int:
        """Pixel sopra la baseline del glifo più alto (>=0)."""
        asc = self.ascent(font)
        best = 0
        for ch in text:
            m = self.glyph(font, ch)
            if m and m[2] > 0:
                best = max(best, asc - m[1])
        return best

    def ink_bottom(self, font: str, text: str) -> int:
        """Pixel sotto la baseline del glifo più basso (>=0)."""
        asc = self.ascent(font)
        best = 0
        for ch in text:
            m = self.glyph(font, ch)
            if m and m[2] > 0:
                best = max(best, m[1] + m[2] - asc)
        return best


@lru_cache(maxsize=1)
def load_metrics() -> Metrics:
    return Metrics(json.loads((FONT_GENERATED / "metrics.json").read_text(encoding="utf-8")))


# ---------------------------------------------------------------- helper sui nodi


def plain(nodes) -> str:
    """Testo senza stili (per ricerca, log, titoli del telefono)."""
    out = []
    for n in nodes:
        if isinstance(n, str):
            out.append(n)
        elif isinstance(n, Styled):
            inner = plain(n.children)
            if n.kind == "sub":
                out.append("_" + inner if len(inner) == 1 else "_{" + inner + "}")
            elif n.kind == "sup":
                out.append("^" + inner if len(inner) == 1 else "^{" + inner + "}")
            else:
                out.append(inner)
    return "".join(out)


def chars(nodes):
    for n in nodes:
        if isinstance(n, str):
            yield from n
        elif isinstance(n, Styled):
            yield from chars(n.children)


def normalize(nodes) -> list:
    """Unisce stringhe adiacenti e rimuove nodi vuoti."""
    out: list = []
    for n in nodes:
        if isinstance(n, Styled):
            n = Styled(n.kind, normalize(n.children), n.param)
            if not n.children:
                continue
        if isinstance(n, str):
            if not n:
                continue
            if out and isinstance(out[-1], str):
                out[-1] += n
                continue
        out.append(n)
    return out


def bold(nodes) -> Styled:
    return Styled("bold", list(nodes))


def color(name: str, nodes) -> Styled:
    return Styled("color", list(nodes), COLORS[name])
