"""AST di pandoc -> modello del libro (capitoli -> sezioni -> blocchi)."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from . import rich
from .mathconv import Unconvertible, convert
from .rich import Styled, normalize, plain

# ------------------------------------------------------------------ modello


@dataclass
class MathImage:
    """Formula inline resa come immagine (nodo dentro il testo ricco)."""
    rid: str


@dataclass
class Para:
    nodes: list
    indent: int = 0
    marker: list | None = None
    align: str = "left"
    role: str = "text"  # text | heading | caption | boxtitle


@dataclass
class ImageBlock:
    rid: str
    kind: str  # equation | figure | snippet


@dataclass
class BoxStart:
    title: list | None
    kind: str


@dataclass
class BoxEnd:
    pass


@dataclass
class Section:
    id: str
    title: list
    label: str | None
    blocks: list = field(default_factory=list)
    qid: str = ""          # identificativo breve (es. "A1"), dal \\def\\@currentlabel della macro o dal .aux
    kind: str = "section"  # "question" se ha un qid, "intro" per il testo prima della prima sezione


@dataclass
class Chapter:
    title: list
    sections: list = field(default_factory=list)


@dataclass
class Book:
    title: str
    chapters: list = field(default_factory=list)


@dataclass
class RenderJob:
    rid: str
    type: str  # math | file | snippet
    tex: str = ""
    display: bool = False
    path: Path | None = None
    where: str = ""


@dataclass
class _Struct:
    level: int
    title: list
    label: str | None
    labeltext: str | None


SPACE_CHARS = {"\u2002", "\u2003", "\u2004", "\u2005", "\u2006", "\u2007", "\u2008", "\u2009", "\u200a",
               "\u202f", "\u205f", "\u3000"}
REPLACE = {"\u2011": "-", "\u2010": "-", "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff", "\u00ad": "", "\u200b": "",
           "\u2212": "−", "\u2032": "′"}
HARMLESS_DIVS = {"center", "titlepage", "minipage", "flushleft", "flushright", "quote", "quotation",
                 "longtable", "table", "figure", "small", "footnotesize", "large", "multicols"}


class Converter:
    def __init__(self, doc, rules, labels, warnings, metrics):
        self.doc = doc
        self.rules = rules
        self.labels = labels
        self.warn = warnings
        self.metrics = metrics
        self.charset = metrics.charset
        self.jobs: dict[str, RenderJob] = {}
        self.where = ""
        self.box_titles = dict(doc.box_titles)
        self.box_titles.update(rules.box_titles)
        self.snippets = {}
        self.stats = {"inline_text": 0, "inline_image": 0, "display": 0, "figures": 0}

    # ---------------------------------------------------------- render jobs
    def _job(self, type_, key: str, **kw) -> str:
        rid = hashlib.sha1((type_ + "|" + key).encode("utf-8")).hexdigest()[:12]
        if rid not in self.jobs:
            self.jobs[rid] = RenderJob(rid, type_, where=self.where, **kw)
        return rid

    # ---------------------------------------------------------- testo
    def text(self, s: str) -> str:
        out = []
        for ch in s:
            if ch in SPACE_CHARS:
                out.append(" ")
                continue
            if ch in REPLACE:
                out.append(REPLACE[ch])
                continue
            if ch == "\u00a0" or ch in self.charset or ch in "\n ":
                out.append(ch)
                continue
            d = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
            if d and all(c in self.charset for c in d):
                out.append(d)
            else:
                self.warn.add("carattere", f"carattere non presente nel font sostituito con '?': {ch!r} "
                                           f"(U+{ord(ch):04X}) in {self.where}")
                out.append("?")
        return "".join(out)

    def math_inline(self, tex: str):
        try:
            nodes = convert(tex, self.charset, self.rules.math_symbols, self._math_text)
            self.stats["inline_text"] += 1
            return nodes
        except Unconvertible as e:
            self.stats["inline_image"] += 1
            self.warn.add("formula-immagine", f"formula inline resa come immagine ({e}): ${tex.strip()[:80]}$",
                          quiet=True)
            return [MathImage(self._job("math", tex, tex=tex, display=False))]

    def _math_text(self, raw: str):
        # \text{...} dentro una formula: testo semplice con eventuale matematica annidata
        parts = re.split(r"(?<!\\)\$(.+?)(?<!\\)\$", raw)
        out = []
        for i, p in enumerate(parts):
            if i % 2:
                out.extend(convert(p, self.charset, self.rules.math_symbols))
            else:
                p = p.replace("~", " ").replace("---", "—").replace("--", "–")
                p = re.sub(r"\\([,;: ])", " ", p)
                if "\\" in p:
                    raise Unconvertible("comando in \\text")
                out.append(self.text(p))
        return out

    def inlines(self, items) -> list:
        out = []
        for it in items:
            t = it["t"]
            c = it.get("c")
            if t == "Str":
                out.append(self.text(c))
            elif t in ("Space", "SoftBreak"):
                out.append(" ")
            elif t == "LineBreak":
                out.append("\n")
            elif t == "Emph":
                out.append(rich.color("emph", self.inlines(c)))
            elif t == "Strong":
                out.append(rich.bold(self.inlines(c)))
            elif t == "Underline":
                out.append(Styled("ul", self.inlines(c)))
            elif t in ("Strikeout", "SmallCaps"):
                out.extend(self.inlines(c))
            elif t == "Superscript":
                out.append(Styled("sup", self.inlines(c)))
            elif t == "Subscript":
                out.append(Styled("sub", self.inlines(c)))
            elif t == "Quoted":
                q = ("“", "”") if c[0]["t"] == "DoubleQuote" else ("‘", "’")
                out.append(q[0])
                out.extend(self.inlines(c[1]))
                out.append(q[1])
            elif t == "Code":
                out.append(self.text(c[1]))
            elif t == "Math":
                if c[0]["t"] == "InlineMath":
                    out.extend(self.math_inline(c[1]))
                else:
                    out.append(_DisplayMarker(c[1]))
            elif t == "Link":
                out.extend(self.link(c))
            elif t == "Image":
                out.append(_ImageMarker(c))
            elif t in ("Span", "Cite"):
                out.extend(self.inlines(c[1] if t == "Span" else c[1]))
            elif t == "Note":
                continue
            elif t == "RawInline":
                continue
            else:
                self.warn.add("pandoc", f"elemento inline non gestito: {t}")
        return out

    def link(self, c):
        attrs = dict(c[0][2])
        rtype = attrs.get("reference-type")
        if rtype:
            ref = attrs.get("reference", "")
            info = self.labels.get(ref)
            if rtype == "pageref":
                return [_PageRef(f"p. {info.page}" if info else "")]
            if info:
                txt = info.text
                return [f"({txt})" if rtype == "eqref" else txt]
            self.warn.add("riferimento", f"etichetta non trovata nel file .aux: {ref}")
            return ["??"]
        return self.inlines(c[1])

    # ---------------------------------------------------------- blocchi
    def blocks(self, items, indent=0, align="left") -> list:
        out = []
        pending_runin = None
        for b in items:
            t = b["t"]
            c = b.get("c")
            res = []
            if t in ("Para", "Plain"):
                res = self.para(c, indent, align)
            elif t == "Header":
                level, attr, inl = c
                nodes = normalize(self.inlines(inl))
                if level >= 4:
                    pending_runin = nodes
                    continue
                res = [Para(nodes, indent, role="heading", align=align)]
            elif t == "BulletList":
                for item in c:
                    res.extend(self.list_item(item, ["•" if indent % 2 == 0 else "–"], indent))
            elif t == "OrderedList":
                start, style, delim = c[0]
                for k, item in enumerate(c[1]):
                    res.extend(self.list_item(item, [_ol_marker(start + k, style["t"], delim["t"])], indent))
            elif t == "DefinitionList":
                for term, defs in c:
                    res.append(Para([rich.bold(self.inlines(term))], indent))
                    for d in defs:
                        res.extend(self.blocks(d, indent + 1))
            elif t == "BlockQuote":
                res = self.blocks(c, indent + 1)
            elif t == "Div":
                res = self.div(c, indent, align)
            elif t == "Table":
                res = self.table(c, indent)
            elif t == "CodeBlock":
                res = [Para([self.text(line)], indent) for line in c[1].splitlines()]
            elif t == "LineBlock":
                res = [Para(self.inlines(line), indent) for line in c]
            elif t == "HorizontalRule":
                res = []
            elif t == "RawBlock":
                res = []
            elif t == "Null":
                res = []
            else:
                self.warn.add("pandoc", f"blocco non gestito: {t}")
            if pending_runin is not None:
                first = res[0] if res else None
                if t in ("Para", "Plain") and isinstance(first, Para) and first.role == "text":
                    first.nodes = [rich.color("heading", [rich.bold(pending_runin)]), " "] + first.nodes
                else:
                    res.insert(0, Para(pending_runin, indent, role="heading"))
                pending_runin = None
            out.extend(res)
        if pending_runin is not None:
            out.append(Para(pending_runin, indent, role="heading"))
        return out

    def para(self, inl, indent, align) -> list:
        nodes = self.inlines(inl)
        res, cur = [], []

        def flush():
            n = normalize(_strip_spaces(cur))
            if n and plain(n).strip() or any(isinstance(x, MathImage) for x in n):
                res.append(Para(n, indent, align=align))
            cur.clear()

        for n in nodes:
            if isinstance(n, _DisplayMarker):
                flush()
                res.append(self.display_math(n.tex))
            elif isinstance(n, _ImageMarker):
                flush()
                img = self.image(n.c)
                if img:
                    res.append(img)
            elif isinstance(n, _PageRef):
                if n.text:
                    cur.append(n.text)
            else:
                cur.append(n)
        flush()
        # testo che segue un'immagine in un ambiente centrato = didascalia
        for i in range(1, len(res)):
            if isinstance(res[i], Para) and isinstance(res[i - 1], ImageBlock) and res[i - 1].kind == "figure":
                res[i].role = "caption"
                res[i].align = "center"
        return res

    def display_math(self, tex: str) -> ImageBlock:
        self.stats["display"] += 1
        return ImageBlock(self._job("math", tex, tex=tex, display=True), "equation")

    def image(self, c):
        src = c[2][0]
        path = self.resolve_graphic(src)
        if path is None:
            self.warn.add("immagine", f"immagine non trovata: {src} ({self.where})")
            return None
        self.stats["figures"] += 1
        return ImageBlock(self._job("file", str(path), path=path), "figure")

    def resolve_graphic(self, name: str) -> Path | None:
        dirs = [self.doc.root / d for d in self.doc.graphicspath] + [self.doc.root]
        exts = ["", ".pdf", ".png", ".jpg", ".jpeg", ".eps"]
        for d in dirs:
            for e in exts:
                p = (d / (name + e)).resolve()
                if p.is_file():
                    return p
        return None

    def list_item(self, blocks, marker, indent) -> list:
        res = self.blocks(blocks, indent + 1)
        for r in res:
            if isinstance(r, Para):
                r.marker = marker
                break
        return res

    def div(self, c, indent, align) -> list:
        attr, content = c
        classes = attr[1]
        cls = classes[0] if classes else ""
        if cls.startswith("gwhead"):
            return [self.struct(int(cls[6:]) - 1, content)]
        if cls == "gwimg":
            sid = _first_code(content)
            src = self.snippets.get(sid)
            if src is None:
                return []
            return [ImageBlock(self._job("snippet", src, tex=src), "snippet")]
        if cls in self.box_titles:
            title = self.box_title_nodes(self.box_titles[cls])
            return [BoxStart(title, cls)] + self.blocks(content, indent, align) + [BoxEnd()]
        if cls in ("center", "titlepage"):
            return self.blocks(content, indent, "center")
        if cls and cls not in HARMLESS_DIVS:
            self.warn.add("ambiente", f"ambiente sconosciuto reso come testo normale: {cls}", quiet=True)
        return self.blocks(content, indent, align)

    def box_title_nodes(self, raw: str) -> list:
        raw = raw.replace("---", "—").replace("--", "–")
        parts = re.split(r"(?<!\\)\$(.+?)(?<!\\)\$", raw)
        out = []
        for i, p in enumerate(parts):
            if i % 2:
                out.extend(self.math_inline(p))
            else:
                out.append(self.text(re.sub(r"\\[a-zA-Z]+\s*|[{}]", "", p)))
        return normalize(out)

    def struct(self, level, content):
        title, label, labeltext = [], None, None
        for b in content:
            if b["t"] == "Header":
                title = normalize(_strip_spaces(self.inlines(b["c"][2])))
            elif b["t"] in ("Para", "Plain"):
                for it in b["c"]:
                    if it["t"] == "Code":
                        v = it["c"][1]
                        if v.startswith("L:"):
                            label = v[2:] or None
                        elif v.startswith("T:"):
                            labeltext = v[2:] or None
        return _Struct(level, title, label, labeltext)

    def table(self, c, indent) -> list:
        # pandoc 3: [attr, caption, colspecs, head, bodies, foot]
        _, _, colspecs, head, bodies, foot = c
        rows = []
        head_rows = head[1]
        for r in head_rows:
            rows.append(("head", r))
        for body in bodies:
            for r in body[2] + body[3]:
                rows.append(("body", r))
        for r in foot[1]:
            rows.append(("body", r))
        table = []
        for kind, r in rows:
            cells = []
            for cell in r[1]:
                blocks = cell[4]
                nodes = []
                only_pageref = True
                for b in blocks:
                    if b["t"] in ("Para", "Plain"):
                        inl = self.inlines(b["c"])
                        for n in inl:
                            if isinstance(n, _PageRef):
                                continue
                            if isinstance(n, (_DisplayMarker, _ImageMarker)):
                                continue
                            if not (isinstance(n, str) and not n.strip()):
                                only_pageref = False
                            nodes.append(n)
                cells.append((normalize(_strip_spaces(nodes)), only_pageref))
            table.append((kind, cells))
        ncols = max((len(cs) for _, cs in table), default=0)
        drop = set()
        for j in range(ncols):
            body_cells = [cs[j] for k, cs in table if k == "body" and j < len(cs)]
            if body_cells and all(op for _, op in body_cells):
                drop.add(j)
        out = []
        for kind, cells in table:
            cells = [n for j, (n, _) in enumerate(cells) if j not in drop]
            cells = [n for n in cells if plain(n).strip() or any(isinstance(x, MathImage) for x in n)]
            if not cells:
                continue
            if kind == "head":
                nodes = _join(cells, " · ")
                out.append(Para([rich.color("dim", [rich.bold(nodes)])], indent))
            elif len(cells) == 1:
                out.append(Para([rich.bold(cells[0])], indent))
            else:
                out.append(Para([rich.bold(cells[0]), " · "] + _join(cells[1:], " · "), indent))
        return out


@dataclass
class _DisplayMarker:
    tex: str


@dataclass
class _ImageMarker:
    c: list


@dataclass
class _PageRef:
    text: str


def _strip_spaces(nodes):
    nodes = list(nodes)
    while nodes and isinstance(nodes[0], str) and not nodes[0].strip(" \n"):
        nodes.pop(0)
    while nodes and isinstance(nodes[-1], str) and not nodes[-1].strip(" \n"):
        nodes.pop()
    if nodes and isinstance(nodes[0], str):
        nodes[0] = nodes[0].lstrip(" \n")
    if nodes and isinstance(nodes[-1], str):
        nodes[-1] = nodes[-1].rstrip(" \n")
    return nodes


def _join(cells, sep):
    out = []
    for i, cl in enumerate(cells):
        if i:
            out.append(sep)
        out.extend(cl)
    return out


def _first_code(content):
    for b in content:
        if b["t"] in ("Para", "Plain"):
            for it in b["c"]:
                if it["t"] == "Code":
                    return it["c"][1]
    return None


def _roman(n):
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
            (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, s in vals:
        while n >= v:
            out += s
            n -= v
    return out


def _ol_marker(n, style, delim):
    if style == "LowerAlpha":
        s = chr(ord("a") + (n - 1) % 26)
    elif style == "UpperAlpha":
        s = chr(ord("A") + (n - 1) % 26)
    elif style == "LowerRoman":
        s = _roman(n)
    elif style == "UpperRoman":
        s = _roman(n).upper()
    else:
        s = str(n)
    if delim == "OneParen":
        return s + ")"
    if delim == "TwoParens":
        return "(" + s + ")"
    return s + "."


# ------------------------------------------------------------------ raggruppamento


def slug(text: str) -> str:
    s = unicodedata.normalize("NFKD", text)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:40] or "x"


def build_book(stream: list, title: str, front_title: str) -> Book:
    levels = sorted({s.level for s in stream if isinstance(s, _Struct) and s.level <= 3})
    chap_level = levels[0] if levels else None
    sec_level = levels[1] if len(levels) > 1 else None
    book = Book(title)
    chapter = None
    section = None
    ids = set()

    def new_section(title_nodes, label, qid=None, kind="section"):
        nonlocal section
        base = slug(label) if label else slug(plain(title_nodes))
        sid, k = base, 2
        while sid in ids:
            sid, k = f"{base}-{k}", k + 1
        ids.add(sid)
        section = Section(sid, title_nodes, label, qid=qid or "", kind="question" if qid else kind)
        chapter.sections.append(section)
        return section

    def ensure_section():
        nonlocal chapter
        if chapter is None:
            chapter = Chapter([front_title])
            book.chapters.append(chapter)
        if section is None:
            new_section(list(chapter.title), None, kind="intro")

    for item in stream:
        if isinstance(item, _Struct) and item.level == chap_level:
            chapter = Chapter(item.title)
            book.chapters.append(chapter)
            section = None
            if sec_level is None:
                new_section(item.title, item.label, item.labeltext)
            continue
        if isinstance(item, _Struct) and item.level == sec_level:
            if chapter is None:
                chapter = Chapter([front_title])
                book.chapters.append(chapter)
            new_section(item.title, item.label, item.labeltext)
            continue
        if isinstance(item, _Struct):
            ensure_section()
            section.blocks.append(Para(item.title, role="heading"))
            continue
        ensure_section()
        section.blocks.append(item)
    # rimuove sezioni vuote
    for ch in book.chapters:
        ch.sections = [s for s in ch.sections if any(not isinstance(b, (BoxStart, BoxEnd)) for b in s.blocks)]
    book.chapters = [c for c in book.chapters if c.sections]
    return book
