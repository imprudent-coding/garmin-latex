"""Titoli per l'elenco dell'orologio (domande da scorrere velocemente).

Ogni sezione ha:
- il titolo completo, su al massimo 3 righe, mostrato per la voce selezionata;
- un titolo compatto su una riga, in due larghezze (al centro dello schermo e
  verso i bordi, dove il cerchio è più stretto), con l'identificativo della
  domanda (es. "A1") in evidenza.
"""
from __future__ import annotations

from . import rich
from .layout import encode_title_lines
from .rich import Styled, normalize, plain

INTRO_LABEL = "Introduzione"


def strip_qid(nodes: list, qid: str) -> list:
    """Toglie l'identificativo iniziale dal titolo ("A1  First…" -> "First…")."""
    if not qid:
        return nodes
    text = plain(nodes)
    if not text.startswith(qid):
        return nodes
    out = list(nodes)
    remaining = len(qid)
    while out and remaining > 0:
        n = out[0]
        if not isinstance(n, str):
            return nodes  # l'id non è testo semplice: meglio non toccare
        if len(n) <= remaining:
            remaining -= len(n)
            out.pop(0)
        else:
            out[0] = n[remaining:]
            remaining = 0
    while out and isinstance(out[0], str) and not out[0].strip("  "):
        out.pop(0)
    if out and isinstance(out[0], str):
        out[0] = out[0].lstrip("  ")
    return normalize(out)


def display_nodes(section, chapter_title: list, alone: bool = False) -> list:
    """Titolo da mostrare: id in evidenza + titolo; "Introduzione" per il testo di apertura
    di un gruppo (se il gruppo ha una sola sezione, il titolo del gruppo)."""
    if alone and section.kind != "question":
        return list(chapter_title)
    if section.kind == "intro" or (section.kind != "question" and plain(section.title) == plain(chapter_title)):
        return [INTRO_LABEL]
    if section.qid:
        rest = strip_qid(section.title, section.qid)
        return [rich.color("heading", [rich.bold([section.qid])]), "  "] + rest
    return list(section.title)


def section_titles(lay, profile, section, chapter_title, alone=False) -> tuple[list, list]:
    """(righe del titolo completo, [riga compatta larga, riga compatta stretta])."""
    nodes = display_nodes(section, chapter_title, alone)
    full = encode_title_lines(lay, nodes, profile.title_w, max_lines=3)
    if nodes == [INTRO_LABEL]:
        nodes = [rich.color("dim", nodes)]  # nell'elenco compatto l'introduzione è attenuata
    small = [Styled("small", nodes)]
    wide = encode_title_lines(lay, small, profile.row_w_wide, max_lines=1)
    narrow = encode_title_lines(lay, small, profile.row_w_narrow, max_lines=1)
    return full, [wide[0], narrow[0]]


def chapter_header(lay, profile, chapter) -> tuple[str, int] | None:
    """Intestazione del gruppo nell'elenco (nessuna se il gruppo ha una sola sezione)."""
    if len(chapter.sections) <= 1:
        return None
    chapter_title = chapter.title
    nodes = [Styled("small", [rich.color("heading", chapter_title)])]
    return encode_title_lines(lay, nodes, profile.row_w_header, max_lines=1)[0]
