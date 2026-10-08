"""Lettura dei sorgenti LaTeX: documento principale, \\input/\\include, macro.

Niente nomi di file o macro sono cablati: la struttura (capitoli/sezioni) viene
dedotta dalle definizioni stesse. Una macro che contiene
\\addcontentsline{toc}{<livello>}{<titolo>} (o un \\section non asteriscato...)
è considerata un comando di sezionamento di quel livello.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

TOC_LEVELS = {"part": -1, "chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3,
              "paragraph": 4, "subparagraph": 5}
SECTIONING = tuple(TOC_LEVELS)

DEFAULT_IMAGE_ENVS = ["tikzpicture", "pgfpicture", "circuitikz", "picture", "pspicture", "forest",
                      "tikzcd", "xy", "asy"]


class TexError(Exception):
    pass


# ------------------------------------------------------------------ utilità


def strip_comments(src: str) -> str:
    out = []
    for line in src.split("\n"):
        i = 0
        while True:
            j = line.find("%", i)
            if j < 0:
                out.append(line)
                break
            # conta i backslash precedenti
            k, n = j - 1, 0
            while k >= 0 and line[k] == "\\":
                n += 1
                k -= 1
            if n % 2 == 0:
                out.append(line[:j])
                break
            i = j + 1
    return "\n".join(out)


def read_group(s: str, i: int, open_ch="{", close_ch="}"):
    """Legge un gruppo bilanciato che inizia (dopo spazi) in s[i]. Ritorna (contenuto, indice_dopo)."""
    n = len(s)
    while i < n and s[i] in " \t\n":
        i += 1
    if i >= n or s[i] != open_ch:
        return None, i
    depth, j = 0, i
    while j < n:
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise TexError(f"gruppo non chiuso a partire da: {s[i:i + 60]!r}")


def read_arg(s: str, i: int):
    """Argomento obbligatorio: {..} oppure un singolo token."""
    g, j = read_group(s, i)
    if g is not None:
        return g, j
    while i < len(s) and s[i] in " \t\n":
        i += 1
    if i < len(s) and s[i] == "\\":
        m = re.match(r"\\([a-zA-Z@]+|.)", s[i:])
        return m.group(0), i + len(m.group(0))
    if i < len(s):
        return s[i], i + 1
    raise TexError("argomento mancante")


def find_command(s: str, name: str, start=0):
    """Trova \\name non seguito da lettere."""
    pat = re.compile(r"\\" + re.escape(name) + r"(?![a-zA-Z@])")
    return pat.search(s, start)


# ------------------------------------------------------------------ definizioni


@dataclass
class MacroDef:
    name: str
    nargs: int
    default: str | None
    body: str
    kind: str  # newcommand | def | operator | env | tcolorbox
    source: str  # testo originale della definizione
    env_end: str = ""


@dataclass
class StructMacro:
    name: str
    nargs: int
    default: str | None
    level: int
    title_tpl: str
    label_tpl: str | None
    labeltext_tpl: str | None


@dataclass
class Document:
    main: Path
    root: Path
    files: list[Path]
    preamble: str
    body: str
    macros: dict[str, MacroDef] = field(default_factory=dict)
    envs: dict[str, MacroDef] = field(default_factory=dict)
    box_titles: dict[str, str] = field(default_factory=dict)
    graphicspath: list[str] = field(default_factory=list)
    title: str | None = None


DEF_RE = re.compile(r"\\(newcommand|renewcommand|providecommand|DeclareRobustCommand|DeclareMathOperator)\*?"
                    r"|\\(def|gdef|edef)(?![a-zA-Z])"
                    r"|\\(newenvironment|renewenvironment)\*?"
                    r"|\\(newtcolorbox|DeclareTColorBox|newtcbtheorem)")


def parse_definitions(src: str):
    """Estrae definizioni di macro/ambienti. Ritorna (macros, envs, box_titles, spans)."""
    macros: dict[str, MacroDef] = {}
    envs: dict[str, MacroDef] = {}
    boxes: dict[str, str] = {}
    spans = []
    pos = 0
    while True:
        m = DEF_RE.search(src, pos)
        if not m:
            break
        start = m.start()
        i = m.end()
        try:
            if m.group(1):
                kind = "operator" if m.group(1) == "DeclareMathOperator" else "newcommand"
                if src[i:i + 1] == "*":
                    i += 1
                name, i = read_arg(src, i)
                name = name.strip().lstrip("\\")
                nargs, default = 0, None
                g, j = read_group(src, i, "[", "]")
                if g is not None:
                    nargs, i = int(g), j
                    g, j = read_group(src, i, "[", "]")
                    if g is not None:
                        default, i = g, j
                body, i = read_group(src, i)
                if body is None:
                    raise TexError(f"definizione di \\{name} senza corpo")
                if kind == "operator":
                    body = r"\operatorname{" + body + "}"
                macros[name] = MacroDef(name, nargs, default, body, kind, src[start:i])
            elif m.group(2):
                mm = re.match(r"\s*\\([a-zA-Z@]+)((?:#\d)*)", src[i:])
                if not mm:
                    pos = i
                    continue
                name = mm.group(1)
                nargs = len(mm.group(2)) // 2
                i += mm.end()
                body, i = read_group(src, i)
                if body is None:
                    pos = i
                    continue
                macros[name] = MacroDef(name, nargs, None, body, "def", src[start:i])
            elif m.group(3):
                name, i = read_group(src, i)
                nargs, default = 0, None
                g, j = read_group(src, i, "[", "]")
                if g is not None:
                    nargs, i = int(g), j
                    g, j = read_group(src, i, "[", "]")
                    if g is not None:
                        default, i = g, j
                b, i = read_group(src, i)
                e, i = read_group(src, i)
                envs[name] = MacroDef(name, nargs, default, b or "", "env", src[start:i], e or "")
            else:
                name, i = read_group(src, i)
                g, j = read_group(src, i, "[", "]")
                if g is not None:
                    i = j
                    g, j = read_group(src, i, "[", "]")
                    if g is not None:
                        i = j
                opts, i = read_group(src, i)
                if m.group(4) == "newtcbtheorem":
                    title, i = read_group(src, i)
                    opts, i = read_group(src, i)
                    boxes[name] = (title or name).strip()
                else:
                    boxes[name] = _tcb_title(opts or "") or name
                envs[name] = MacroDef(name, 0, None, "", "tcolorbox", src[start:i])
        except (TexError, ValueError):
            pos = m.end()
            continue
        spans.append((start, i))
        pos = i
    # ereditarietà degli stili tcolorbox (\tcbset{x/.style={...title=...}})
    return macros, envs, boxes, spans


def _tcb_title(opts: str) -> str | None:
    m = re.search(r"(?<![a-z])title\s*=\s*", opts)
    if not m:
        return None
    i = m.end()
    g, _ = read_group(opts, i)
    if g is not None:
        return g.strip()
    return opts[i:].split(",")[0].strip()


def substitute(tpl: str, args: list[str]) -> str:
    return re.sub(r"#(\d)", lambda m: args[int(m.group(1)) - 1] if int(m.group(1)) <= len(args) else "", tpl)


def struct_from_macro(md: MacroDef) -> StructMacro | None:
    body = md.body
    m = re.search(r"\\addcontentsline\s*\{toc\}\s*\{(\w+)\}", body)
    level = None
    title = None
    if m and m.group(1) in TOC_LEVELS:
        level = TOC_LEVELS[m.group(1)]
        title, _ = read_group(body, m.end())
    else:
        for cmd in SECTIONING:
            mm = re.search(r"\\" + cmd + r"(?![a-zA-Z*])\s*(\[[^\]]*\])?", body)
            if mm:
                level = TOC_LEVELS[cmd]
                title, _ = read_group(body, mm.end())
                break
    if level is None or title is None:
        return None
    label = None
    ml = re.search(r"\\label\s*\{([^}]*)\}", body)
    if ml:
        label = ml.group(1)
    labeltext = None
    mt = re.search(r"\\def\\@currentlabel\s*\{([^}]*)\}", body)
    if mt:
        labeltext = mt.group(1)
    return StructMacro(md.name, md.nargs, md.default, level, title.strip(), label, labeltext)


# ------------------------------------------------------------------ caricamento


def find_main_documents(root: Path) -> list[Path]:
    mains = []
    for p in sorted(root.rglob("*.tex")):
        try:
            s = strip_comments(p.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if re.search(r"\\documentclass", s) and r"\begin{document}" in s:
            mains.append(p)
    return mains


INPUT_RE = re.compile(r"\\(input|include|subfile)(?![a-zA-Z])\s*(?:\{([^}]*)\}|([^\s{}\\]+))")


def flatten(path: Path, root: Path, seen: list[Path], depth=0) -> str:
    if depth > 30:
        raise TexError("\\input annidati troppo in profondità (ciclo?)")
    src = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
    seen.append(path)

    def repl(m):
        name = (m.group(2) or m.group(3) or "").strip()
        cand = (root / name)
        if cand.suffix != ".tex":
            cand = cand.with_name(cand.name + ".tex") if not cand.exists() else cand
        if not cand.exists():
            raise TexError(f"{path.relative_to(root)}: file incluso non trovato: {name}")
        inner = flatten(cand, root, seen, depth + 1)
        if m.group(1) == "subfile":
            mm = re.search(r"\\begin\{document\}(.*)\\end\{document\}", inner, re.S)
            inner = mm.group(1) if mm else inner
        return "\n" + inner + "\n"

    return INPUT_RE.sub(repl, src)


def load_document(main: Path) -> Document:
    root = main.parent
    files: list[Path] = []
    full = flatten(main, root, files)
    b = full.find(r"\begin{document}")
    e = full.rfind(r"\end{document}")
    if b < 0 or e < 0:
        raise TexError(f"{main.name}: manca \\begin{{document}} o \\end{{document}}")
    preamble = full[:b]
    body = full[b + len(r"\begin{document}"):e]
    macros, envs, boxes, _ = parse_definitions(preamble)
    bm, be, bb, _ = parse_definitions(body)
    macros.update(bm)
    envs.update(be)
    boxes.update(bb)
    gp = []
    m = re.search(r"\\graphicspath\s*\{((?:\{[^}]*\})+)\}", preamble)
    if m:
        gp = re.findall(r"\{([^}]*)\}", m.group(1))
    title = None
    mt = find_command(preamble, "title")
    if mt:
        title, _ = read_group(preamble, mt.end())
    return Document(main, root, files, preamble, body, macros, envs, boxes, gp, title)
