"""Trasforma il documento in un sorgente "pulito" per pandoc.

- i comandi di sezionamento (standard o macro rilevate) diventano ambienti marcatori
  \\begin{gwheadN} ... \\end{gwheadN} che pandoc converte in Div;
- gli ambienti grafici (tikz, ...) e le macro marcate "come immagine" diventano
  segnaposto \\begin{gwimg}\\texttt{ID}\\end{gwimg} e il loro sorgente viene
  conservato per la compilazione con LaTeX;
- le definizioni interne a LaTeX (\\@...) e le ridefinizioni dei comandi di
  sezionamento vengono omesse.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .texsource import (DEFAULT_IMAGE_ENVS, SECTIONING, TOC_LEVELS, Document, MacroDef, StructMacro,
                        TexError, find_command, read_group, struct_from_macro, substitute)

DROP_COMMANDS = ["tableofcontents", "listoffigures", "listoftables", "maketitle", "printbibliography",
                 "bibliography", "bibliographystyle", "appendix", "frontmatter", "mainmatter", "backmatter"]


@dataclass
class Prepared:
    source: str
    structs: dict[str, StructMacro]
    snippets: dict[str, str] = field(default_factory=dict)  # id -> sorgente LaTeX da renderizzare
    dropped_macros: list[str] = field(default_factory=list)


def _keep_definition(md: MacroDef) -> bool:
    if md.name in SECTIONING or "@" in md.name:
        return False
    if "\\@" in md.body or "@" in md.body.replace("\\@", ""):
        return False
    return True


def _parse_invocation(body: str, i: int, nargs: int, default: str | None):
    args = []
    if default is not None:
        g, j = read_group(body, i, "[", "]")
        if g is not None:
            args.append(g)
            i = j
        else:
            args.append(default)
    while len(args) < nargs:
        g, j = read_group(body, i)
        if g is None:
            # argomento senza graffe: singolo token
            m = re.match(r"\s*(\\[a-zA-Z]+|\S)", body[i:])
            if not m:
                raise TexError("argomento mancante")
            g, j = m.group(1), i + m.end()
        args.append(g)
        i = j
    return args, i


def _head_env(level: int, title: str, label: str | None, labeltext: str | None) -> str:
    n = level + 1  # part=-1 -> gwhead0
    title = re.sub(r"\\q?quad(?![a-zA-Z])\s*", r"\\ \\ ", title)
    parts = [f"\n\\begin{{gwhead{n}}}\n\\paragraph{{{title}}}\n"]
    parts.append(f"\\texttt{{L:{label or ''}}}\\texttt{{T:{labeltext or ''}}}\n")
    parts.append(f"\\end{{gwhead{n}}}\n")
    return "".join(parts)


def _replace_structs(body: str, structs: dict[str, StructMacro]) -> str:
    if not structs:
        return body
    names = sorted(structs, key=len, reverse=True)
    pat = re.compile(r"\\(" + "|".join(map(re.escape, names)) + r")(?![a-zA-Z@])")
    out, pos = [], 0
    while True:
        m = pat.search(body, pos)
        if not m:
            out.append(body[pos:])
            break
        sm = structs[m.group(1)]
        args, end = _parse_invocation(body, m.end(), sm.nargs, sm.default)
        out.append(body[pos:m.start()])
        title = substitute(sm.title_tpl, args)
        label = substitute(sm.label_tpl, args) if sm.label_tpl else None
        lt = substitute(sm.labeltext_tpl, args) if sm.labeltext_tpl else None
        out.append(_head_env(sm.level, title, label, lt))
        pos = end
    return "".join(out)


STD_SEC_RE = re.compile(r"\\(" + "|".join(SECTIONING) + r")(\*?)(?![a-zA-Z@])")


def _replace_standard_sections(body: str) -> str:
    out, pos = [], 0
    while True:
        m = STD_SEC_RE.search(body, pos)
        if not m:
            out.append(body[pos:])
            break
        cmd, star = m.group(1), m.group(2)
        i = m.end()
        short, j = read_group(body, i, "[", "]")
        if short is not None:
            i = j
        title, i = read_group(body, i)
        if title is None:
            out.append(body[pos:m.end()])
            pos = m.end()
            continue
        level = TOC_LEVELS[cmd]
        if star:
            # \section*{X}\addcontentsline{toc}{lvl}{Y}  -> struttura
            mm = re.match(r"\s*(?:\\phantomsection\s*)?\\addcontentsline\s*\{toc\}\s*\{(\w+)\}", body[i:])
            if mm and mm.group(1) in TOC_LEVELS:
                y, k = read_group(body, i + mm.end())
                out.append(body[pos:m.start()])
                out.append(_head_env(TOC_LEVELS[mm.group(1)], y or title, None, None))
                pos = k
                continue
            out.append(body[pos:i])
            pos = i
            continue
        if level > 3:  # \paragraph, \subparagraph: titoli interni
            out.append(body[pos:i])
            pos = i
            continue
        # etichetta subito dopo il titolo
        label = None
        ml = re.match(r"\s*\\label\s*\{([^}]*)\}", body[i:])
        if ml:
            label = ml.group(1)
            i += ml.end()
        out.append(body[pos:m.start()])
        out.append(_head_env(level, title, label, None))
        pos = i
    return "".join(out)


def _protect_phantom_toc(body: str) -> str:
    # \phantomsection\addcontentsline{toc}{section}{X} isolato prima di \section*: gestito sopra;
    # gli \addcontentsline rimasti (senza titolo vicino) diventano anch'essi struttura.
    out, pos = [], 0
    pat = re.compile(r"\\addcontentsline\s*\{toc\}\s*\{(\w+)\}")
    while True:
        m = pat.search(body, pos)
        if not m:
            out.append(body[pos:])
            break
        title, end = read_group(body, m.end())
        out.append(body[pos:m.start()])
        if m.group(1) in TOC_LEVELS and m.group(1) not in ("paragraph", "subparagraph"):
            # \addcontentsline seguito da \section*{...}: il titolo di \section* è ridondante
            mm = re.match(r"\s*\\(" + "|".join(SECTIONING) + r")\*\s*", body[end:])
            if mm:
                _, end2 = read_group(body, end + mm.end())
                end = end2
            out.append(_head_env(TOC_LEVELS[m.group(1)], title or "", None, None))
        pos = end
    return "".join(out)


def _replace_image_envs(body: str, envs: list[str], snippets: dict[str, str]) -> str:
    for env in envs:
        pat = re.compile(r"\\begin\{" + re.escape(env) + r"\}(.*?)\\end\{" + re.escape(env) + r"\}", re.S)

        def repl(m):
            sid = f"env{len(snippets) + 1}"
            snippets[sid] = m.group(0)
            return f"\n\\begin{{gwimg}}\\texttt{{{sid}}}\\end{{gwimg}}\n"

        body = pat.sub(repl, body)
    return body


def _replace_image_macros(body: str, macros: dict[str, int], snippets: dict[str, str]) -> str:
    for name, nargs in macros.items():
        out, pos = [], 0
        while True:
            m = find_command(body, name, pos)
            if not m:
                out.append(body[pos:])
                break
            args, end = _parse_invocation(body, m.end(), nargs, None)
            sid = f"mac{len(snippets) + 1}"
            snippets[sid] = body[m.start():end]
            out.append(body[pos:m.start()])
            out.append(f"\\begin{{gwimg}}\\texttt{{{sid}}}\\end{{gwimg}}")
            pos = end
        body = "".join(out)
    return body


def _normalize_tables(body: str) -> str:
    """longtable/tabularx/tabulary -> tabular (pandoc legge in modo affidabile solo tabular)."""
    body = re.sub(r"\\(endfirsthead|endhead|endfoot|endlastfoot)(?![a-zA-Z])", "", body)
    body = re.sub(r"\\begin\{longtable\}(\[[^\]]*\])?", r"\\begin{tabular}", body)
    body = body.replace("\\end{longtable}", "\\end{tabular}")
    # pandoc non accetta @{...} nelle specifiche di \multicolumn
    body = re.sub(r"(\\multicolumn\s*\{\d+\}\s*)\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", r"\1{l}", body)
    out, pos = [], 0
    pat = re.compile(r"\\begin\{(tabularx|tabulary|tabular\*)\}")
    while True:
        m = pat.search(body, pos)
        if not m:
            out.append(body[pos:])
            break
        _, i = read_group(body, m.end())  # larghezza
        spec, j = read_group(body, i)  # colonne: X/L/C/R -> l
        spec = re.sub(r"[XLCRJ]", "l", spec or "l")
        out.append(body[pos:m.start()] + "\\begin{tabular}{" + spec + "}")
        pos = j
        end_name = m.group(1)
        body = body[:pos] + body[pos:].replace("\\end{" + end_name + "}", "\\end{tabular}", 1)
    return "".join(out)


def prepare(doc: Document, rules) -> Prepared:
    structs: dict[str, StructMacro] = {}
    for name, md in doc.macros.items():
        if name in rules.ignore_structure:
            continue
        sm = struct_from_macro(md)
        if sm:
            structs[name] = sm
    for name, spec in rules.structure.items():
        structs[name] = StructMacro(name, spec.get("args", 1), None, TOC_LEVELS[spec["level"]],
                                    spec.get("title", "#1"), spec.get("label"), spec.get("labeltext"))

    snippets: dict[str, str] = {}
    body = doc.body
    body = _replace_image_envs(body, DEFAULT_IMAGE_ENVS + list(rules.image_envs), snippets)
    body = _replace_image_macros(body, dict(rules.image_macros), snippets)
    body = _replace_structs(body, structs)
    body = _replace_standard_sections(body)
    body = _protect_phantom_toc(body)
    body = _normalize_tables(body)
    for c in DROP_COMMANDS:
        body = re.sub(r"\\" + c + r"(?![a-zA-Z@])", "", body)

    defs, dropped = [], []
    overrides = rules.macros
    for name, md in doc.macros.items():
        if name in structs:
            continue
        if name in overrides:
            continue
        if not _keep_definition(md):
            dropped.append(name)
            continue
        defs.append(md.source)
    for name, ov in overrides.items():
        nargs = ov.get("args", 0)
        defs.append(f"\\newcommand{{\\{name}}}" + (f"[{nargs}]" if nargs else "") + "{" + ov["body"] + "}")
    for name, md in doc.envs.items():
        if md.kind == "env" and name in rules.expand_envs:
            defs.append(md.source)

    src = "\\documentclass{article}\n" + "\n".join(defs) + "\n\\begin{document}\n" + body + "\n\\end{document}\n"
    return Prepared(src, structs, snippets, dropped)
