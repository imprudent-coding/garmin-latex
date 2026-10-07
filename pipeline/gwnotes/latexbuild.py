"""Compilazione del documento con LaTeX (validazione + PDF di riferimento)."""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .texsource import read_group


class LatexError(Exception):
    pass


@dataclass
class LabelInfo:
    text: str
    page: str


def extract_errors(log: str, limit: int = 15) -> list[str]:
    """Estrae gli errori "! ..." dal log, con file e riga quando disponibili."""
    errors = []
    lines = log.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\.?/?[^:\s]+\.tex):(\d+): (.*)$", line)
        if m:
            ctx = [f"{m.group(1)} riga {m.group(2)}: {m.group(3)}"]
            for nxt in lines[i + 1:i + 4]:
                if nxt.startswith("l."):
                    ctx.append(nxt.strip())
                    break
            errors.append(" | ".join(ctx))
            if len(errors) >= limit:
                break
            continue
        if line.startswith("! "):
            ctx = [line]
            for nxt in lines[i + 1:i + 6]:
                if nxt.startswith("l.") or nxt.strip().startswith("<"):
                    ctx.append(nxt.strip())
                    if nxt.startswith("l."):
                        break
            # file corrente: ultima "(./file.tex" aperta prima dell'errore
            opened = re.findall(r"\(\.?/?([^\s()]+\.tex)", "\n".join(lines[:i]))
            where = opened[-1] if opened else "?"
            errors.append(f"[{where}] " + " | ".join(ctx))
            if len(errors) >= limit:
                break
    return errors


def compile_pdf(main: Path, outdir: Path, timeout: int = 900) -> Path:
    outdir.mkdir(parents=True, exist_ok=True)
    if not shutil.which("latexmk"):
        raise LatexError("latexmk non trovato: installa TeX Live (vedi pipeline/README.md)")
    cmd = ["latexmk", "-pdf", "-interaction=nonstopmode", "-halt-on-error", "-file-line-error",
           f"-outdir={outdir.resolve()}", main.name]
    p = subprocess.run(cmd, cwd=main.parent, capture_output=True, text=True, timeout=timeout)
    log_path = outdir / (main.stem + ".log")
    log = log_path.read_text(encoding="utf-8", errors="replace") if log_path.exists() else p.stdout
    pdf = outdir / (main.stem + ".pdf")
    if p.returncode != 0 or not pdf.exists():
        errs = extract_errors(log) or [p.stdout[-2000:], p.stderr[-2000:]]
        raise LatexError(f"compilazione di {main.name} fallita:\n  " + "\n  ".join(errs)
                         + f"\n(log completo: {log_path})")
    return pdf


def latex_warnings(outdir: Path, main: Path) -> list[str]:
    log_path = outdir / (main.stem + ".log")
    if not log_path.exists():
        return []
    log = log_path.read_text(encoding="utf-8", errors="replace")
    warns = re.findall(r"LaTeX Warning: (.*?)(?:\n\n|\.\n)", log, re.S)
    return sorted({" ".join(w.split()) for w in warns})


def read_labels(aux: Path) -> dict[str, LabelInfo]:
    labels: dict[str, LabelInfo] = {}
    if not aux.exists():
        return labels
    src = aux.read_text(encoding="utf-8", errors="replace")
    for m in re.finditer(r"\\newlabel\{([^}]*)\}", src):
        g, i = read_group(src, m.end())
        if g is None:
            continue
        text, j = read_group(g, 0)
        page, _ = read_group(g, j)
        labels[m.group(1)] = LabelInfo(_clean(text or ""), _clean(page or ""))
    return labels


def _clean(s: str) -> str:
    s = re.sub(r"\\[a-zA-Z@]+\s*", "", s)
    return s.replace("{", "").replace("}", "").strip()
