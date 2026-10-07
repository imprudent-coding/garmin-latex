"""Spezzamento delle equazioni troppo larghe per lo schermo.

Divide il sorgente TeX solo in punti "sicuri" (fuori da graffe, \\left...\\right e
ambienti): righe di aligned/gathered, \\qquad, relazioni (=, ⇒, ≃, ...), e come
ultima risorsa + e −. Ogni pezzo viene compilato a parte e le righe vengono
ricomposte allineando i pezzi sulla baseline.
"""
from __future__ import annotations

import re

from PIL import Image

RELATIONS = ["=", "<", ">", "\\le", "\\leq", "\\ge", "\\geq", "\\simeq", "\\approx", "\\equiv", "\\sim",
             "\\Rightarrow", "\\Longrightarrow", "\\Leftrightarrow", "\\iff", "\\implies", "\\to",
             "\\propto", "\\ne", "\\neq", "\\ll", "\\gg", "\\cong", "\\longrightarrow", "\\mapsto", ":="]
SPACERS = ["\\qquad", "\\quad"]
BINARY = ["+", "-", "\\pm", "\\mp", "\\times", "\\cdot"]
ROW_ENVS = ("aligned", "gathered", "align", "align*", "gather", "gather*", "split", "alignedat")


def _scan(tex: str):
    """Genera (indice, token, profondità) per i token di primo livello."""
    i, n = 0, len(tex)
    depth = 0
    while i < n:
        c = tex[i]
        if c == "\\":
            m = re.match(r"\\([a-zA-Z]+|.)?", tex[i:], re.S)
            tok = m.group(0)
            name = m.group(1) or ""
            if name in ("left", "begin"):
                yield i, tok, depth
                depth += 1
                i += len(tok)
                # salta il delimitatore/nome
                if name == "begin":
                    mm = re.match(r"\s*\{[^}]*\}", tex[i:])
                    if mm:
                        i += mm.end()
                else:
                    mm = re.match(r"\s*(\\[a-zA-Z]+|\\.|.)", tex[i:])
                    if mm:
                        i += mm.end()
                continue
            if name in ("right", "end"):
                depth -= 1
                i += len(tok)
                if name == "end":
                    mm = re.match(r"\s*\{[^}]*\}", tex[i:])
                    if mm:
                        i += mm.end()
                else:
                    mm = re.match(r"\s*(\\[a-zA-Z]+|\\.|.)", tex[i:])
                    if mm:
                        i += mm.end()
                yield i, tok, depth + 1
                continue
            yield i, tok, depth
            i += len(tok)
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        yield i, c, depth
        i += 1


def unwrap_rows(tex: str) -> list[str] | None:
    """Se la formula è un unico ambiente a righe (aligned...), ritorna le righe.
    Accetta anche un sistema \\left\\{ \\begin{aligned}...\\end{aligned} \\right. e cases."""
    t = tex.strip()
    m = re.match(r"^\\left\s*(\\\{|\\lbrace|\.)\s*(.*?)\s*\\right\s*(\.|\\\}|\\rbrace)$", t, re.S)
    if m:
        t = m.group(2).strip()
    is_cases = False
    m = re.match(r"^\\begin\{cases\}(.*)\\end\{cases\}$", t, re.S)
    if m:
        t = "\\begin{aligned}" + m.group(1) + "\\end{aligned}"
        is_cases = True
    m = re.match(r"\\begin\{(" + "|".join(re.escape(e) for e in ROW_ENVS) + r")\}(\{[^}]*\})?(.*)\\end\{\1\}$",
                 t, re.S)
    if not m:
        return None
    inner = m.group(3)
    rows, start = [], 0
    for i, tok, depth in _scan(inner):
        if depth == 0 and tok == "\\\\":
            rows.append(inner[start:i])
            start = i + 2
    rows.append(inner[start:])
    # "&&" (nuova coppia di colonne, tipicamente un'annotazione) e la condizione di
    # cases diventano righe a sé
    split_rows = []
    for r in rows:
        cells = re.split(r"(?<!\\)&&" if not is_cases else r"(?<!\\)&", r)
        split_rows.extend(cells)
    rows = [re.sub(r"(?<!\\)&", "", r).strip() for r in split_rows]
    rows = [re.sub(r"^\[[^\]]*\]", "", r).strip() for r in rows]
    return [r for r in rows if r]


def split_points(tex: str, kinds) -> list[str]:
    """Divide al primo livello davanti ai token indicati (il token resta nel pezzo successivo)."""
    cuts = []
    toks = list(_scan(tex))
    paren = 0
    for k, (i, tok, depth) in enumerate(toks):
        if depth == 0 and tok in ("(", "["):
            paren += 1
        elif depth == 0 and tok in (")", "]"):
            paren = max(0, paren - 1)
        if depth != 0 or i == 0 or paren > 0:
            continue
        if tok in kinds:
            # non spezzare un segno unario (es. "=-x" o "(-")
            if tok in ("-", "+"):
                prev = tex[:i].rstrip()
                if not prev or prev[-1] in "=(<>{,&" or prev.endswith(("\\le", "\\ge", "\\Rightarrow")):
                    continue
            # \;\Rightarrow\; : taglia prima degli spazi
            j = i
            while True:
                mm = re.search(r"(\\[,;:!]|\\ |\s)+$", tex[:j])
                if mm and mm.start() < j:
                    j = mm.start()
                else:
                    break
            cuts.append(j)
    pieces, start = [], 0
    for c in sorted(set(cuts)):
        if c <= start:
            continue
        piece = tex[start:c].strip()
        if piece:
            pieces.append(piece)
        start = c
    last = tex[start:].strip()
    if last:
        pieces.append(last)
    return pieces


def leading_op_tex(piece: str) -> str:
    """Un pezzo che inizia con una relazione/operatore va preceduto da {} per la spaziatura giusta."""
    p = piece.lstrip()
    for tok in RELATIONS + BINARY + SPACERS:
        if p.startswith(tok) and (not tok[0] == "\\" or not p[len(tok):len(tok) + 1].isalpha()):
            return "{}" + p
    return p


def compose(lines, gap: int = 6, indent: int = 24) -> tuple[Image.Image, int]:
    """lines: lista di righe, ogni riga è lista di (immagine L, ascent).
    Ritorna immagine composta (sfondo bianco) e ascent della prima riga."""
    rendered = []
    for li, pieces in enumerate(lines):
        asc = max(a for _, a in pieces)
        desc = max(im.height - a for im, a in pieces)
        w = sum(im.width for im, _ in pieces)
        row = Image.new("L", (w, asc + desc), 255)
        x = 0
        for im, a in pieces:
            row.paste(im, (x, asc - a))
            x += im.width
        rendered.append((row, asc))
    width = max(r.width + (indent if i else 0) for i, (r, _) in enumerate(rendered))
    height = sum(r.height for r, _ in rendered) + gap * (len(rendered) - 1)
    out = Image.new("L", (width, height), 255)
    y = 0
    for i, (r, _) in enumerate(rendered):
        out.paste(r, (indent if i else 0, y))
        y += r.height + gap
    return out, rendered[0][1]


def pack(widths: list[int], maxw: int, indent: int, first_indented: bool = False,
         slack: float = 1.08) -> list[list[int]]:
    """Raggruppa pezzi consecutivi in righe di larghezza <= maxw (greedy).

    Tollera un piccolo sforamento (`slack`, poi l'immagine viene ridotta di poco)
    ed evita di lasciare da solo un pezzo molto corto."""
    lines, cur, curw = [], [], 0
    for k, w in enumerate(widths):
        limit = maxw - (indent if (lines or first_indented) else 0)
        if cur and curw + w > limit * slack:
            short_alone = curw < 0.2 * maxw and len(cur) == 1
            if not (short_alone and curw + w <= limit * 1.2):
                lines.append(cur)
                cur, curw = [], 0
        cur.append(k)
        curw += w
    if cur:
        if lines and curw < 0.15 * maxw:
            prev = sum(widths[i] for i in lines[-1])
            if prev + curw <= (maxw - indent) * 1.2:
                lines[-1].extend(cur)
                cur = []
        if cur:
            lines.append(cur)
    return lines


TEXT_CMD = re.compile(r"\\(?:text|mbox|textrm|textup)\s*\{")


def wrap_text_piece(tex: str, width_pt: float) -> str | None:
    """Un pezzo che contiene \\text{...} e non si può spezzare altrove: diventa un
    paragrafo (\\parbox) in cui LaTeX va a capo da solo; la matematica resta in $...$."""
    if not TEXT_CMD.search(tex):
        return None
    out, pos = [], 0
    while True:
        m = TEXT_CMD.search(tex, pos)
        if not m:
            rest = tex[pos:].strip()
            if rest:
                out.append("$" + rest + "$")
            break
        before = tex[pos:m.start()].strip()
        if before:
            out.append("$" + before + "$")
        depth, j = 1, m.end()
        while j < len(tex) and depth:
            if tex[j] == "{":
                depth += 1
            elif tex[j] == "}":
                depth -= 1
            j += 1
        out.append(tex[m.end():j - 1])
        pos = j
    body = " ".join(o for o in out if o not in ("$\\quad$", "$\\qquad$"))
    return "\\parbox[t]{%.1fpt}{\\raggedright %s}" % (width_pt, body)
