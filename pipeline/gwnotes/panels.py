"""Divisione delle figure a griglia (più righe *e* più colonne di grafici) in pannelli.

Sull'orologio una figura come una griglia 2x2 di grafici, ridotta per il cerchio,
è illeggibile: assi e titoli diventano minuscoli. Ogni pannello diventa allora
una pagina a sé (dopo la figura intera, per il colpo d'occhio).

Le figure a striscia (una sola riga o una sola colonna di grafici) restano
intere: si leggono con lo zoom, scorrendo.

Metodo: taglio ricorsivo sulle fasce vuote (XY-cut) dell'immagine a livelli
(sfondo 0). La divisione si accetta solo se è una griglia pulita:
- almeno 2 righe e 2 colonne di pannelli;
- pannelli di area simile (la più piccola >= MIN_AREA_RATIO della più grande);
- nessun pannello più stretto/basso di MIN_SIDE della figura.
Così didascalie o legende staccate dal loro disegno fanno fallire la divisione
e la figura resta intera. Le eccezioni si dichiarano in rules.yaml
(figure_panels: nome file -> auto | split | whole).
"""
from __future__ import annotations

from PIL import Image

MIN_GAP = 0.02         # fascia vuota minima, frazione della dimensione della figura
MIN_PART = 0.2         # parte minima di un taglio, frazione della dimensione della figura
MIN_AREA_RATIO = 0.4
MIN_SIDE = 0.15

Box = tuple[int, int, int, int]


def _profiles(img: Image.Image, box: Box) -> tuple[list[bool], list[bool]]:
    """Righe e colonne del riquadro con almeno un pixel non di sfondo
    (getbbox è nativo: veloce anche senza numpy)."""
    x0, y0, x1, y1 = box
    rows = [img.crop((x0, y, x1, y + 1)).getbbox() is not None for y in range(y0, y1)]
    cols = [img.crop((x, y0, x + 1, y1)).getbbox() is not None for x in range(x0, x1)]
    return rows, cols


def _trim(px: Image.Image, box: Box) -> Box | None:
    rows, cols = _profiles(px, box)
    if not any(rows):
        return None
    y0 = box[1] + rows.index(True)
    y1 = box[1] + len(rows) - rows[::-1].index(True)
    x0 = box[0] + cols.index(True)
    x1 = box[0] + len(cols) - cols[::-1].index(True)
    return (x0, y0, x1, y1)


def _gaps(profile: list[bool], minrun: int) -> list[tuple[int, int]]:
    """Fasce vuote interne (non ai bordi) lunghe almeno minrun."""
    out, i, n = [], 0, len(profile)
    while i < n:
        if profile[i]:
            i += 1
            continue
        j = i
        while j < n and not profile[j]:
            j += 1
        if i > 0 and j < n and j - i >= minrun:
            out.append((i, j))
        i = j
    return out


def _cut(px: Image.Image, box: Box, fig_w: int, fig_h: int, depth: int = 0):
    """Albero di tagli: ("leaf", box) oppure ("h"/"v", [figli])."""
    b = _trim(px, box)
    if b is None:
        return None
    if depth < 3:
        rows, cols = _profiles(px, b)
        for prof, kind, size in ((rows, "h", fig_h), (cols, "v", fig_w)):
            gaps = _gaps(prof, max(4, int(MIN_GAP * size)))
            if not gaps:
                continue
            cuts = [0] + [(a + c) // 2 for a, c in gaps] + [len(prof)]
            parts = []
            for a, c in zip(cuts, cuts[1:]):
                parts.append((b[0], b[1] + a, b[2], b[1] + c) if kind == "h" else (b[0] + a, b[1], b[0] + c, b[3]))
            ext = [(p[3] - p[1]) if kind == "h" else (p[2] - p[0]) for p in parts]
            if min(ext) < MIN_PART * size:
                continue
            kids = [k for k in (_cut(px, p, fig_w, fig_h, depth + 1) for p in parts) if k is not None]
            if len(kids) > 1:
                return (kind, kids)
    return ("leaf", b)


def _leaves(node) -> list[Box]:
    if node[0] == "leaf":
        return [node[1]]
    return [b for k in node[1] for b in _leaves(k)]


def _is_grid(node) -> bool:
    """Righe e colonne: un taglio in una direzione i cui figli sono tagliati nell'altra."""
    if node[0] == "leaf":
        return False
    other = "v" if node[0] == "h" else "h"
    return all(k[0] == other for k in node[1]) and len(node[1]) >= 2


def grid_panels(levels: Image.Image, mode: str = "auto") -> list[Box] | None:
    """Riquadri dei pannelli (ordine di lettura: righe, poi colonne) se la figura
    è una griglia da dividere, altrimenti None. mode: auto | split | whole."""
    if mode == "whole":
        return None
    w, h = levels.size
    tree = _cut(levels.convert("L"), (0, 0, w, h), w, h)
    if tree is None or tree[0] == "leaf":
        return None
    boxes = _leaves(tree)
    if mode == "split":
        return boxes if len(boxes) > 1 else None
    if not _is_grid(tree):
        return None
    areas = [(b[2] - b[0]) * (b[3] - b[1]) for b in boxes]
    if min(areas) < MIN_AREA_RATIO * max(areas):
        return None
    if any((b[2] - b[0]) < MIN_SIDE * w or (b[3] - b[1]) < MIN_SIDE * h for b in boxes):
        return None
    return boxes
