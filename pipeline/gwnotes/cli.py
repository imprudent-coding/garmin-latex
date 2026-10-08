"""Comando principale della pipeline.

    python -m gwnotes build [--latex ../latex] [--out ../dist] [--no-pdf] [--preview N]

Esce con codice != 0 solo per errori veri (compilazione LaTeX fallita, pandoc
mancante, ...). Tutto ciò che non si converte bene diventa immagine o testo e
finisce nel report (dist/report.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from . import images, rich
from .assets import AssetBuilder
from .bundle import SCHEMA, BundleBuilder, Resource, SectionPages, build_index, chunk_text, res_file, short_hash, write_zip
from .docmodel import Book, Converter, ImageBlock, MathImage, Para, build_book
from .latexbuild import LatexError, compile_pdf, latex_warnings, read_labels
from .layout import Layouter, SectionLayout, encode_title_lines
from .paths import REPO_ROOT
from .prepare import prepare
from .preview import Renderer, contact_sheet
from .profile import VIVOACTIVE5
from .report import Warnings
from .rich import Styled, load_metrics, plain
from .rules import Rules
from .texsource import TexError, find_main_documents, load_document

HARMLESS_RAW = {"needspace", "smallskip", "medskip", "bigskip", "vspace", "hspace", "clearpage", "newpage",
                "pagebreak", "phantomsection", "hfill", "vfill", "centering", "noindent", "par", "hypertarget",
                "markright", "markboth", "footnotesize", "small", "large", "Large", "LARGE", "huge", "Huge",
                "normalsize", "scriptsize", "tiny", "bfseries", "itshape", "normalfont", "renewcommand",
                "setlength", "addtolength", "label", "linebreak", "nolinebreak", "allowbreak", "quad", "qquad",
                "thispagestyle", "pagestyle", "raggedright", "raggedleft", "bigbreak", "medbreak", "smallbreak",
                "nopagebreak", "enlargethispage", "strut", "null", "relax", "ignorespaces", "unskip", "kern",
                "hline", "toprule", "midrule", "bottomrule", "cline", "cmidrule", "arraystretch", "vfil", "hfil",
                "begingroup", "endgroup", "bgroup", "egroup", "selectfont", "fontsize", "color", "texttt"}


def run_pandoc(src: str, raw: bool = False) -> dict:
    if not shutil.which("pandoc"):
        raise SystemExit("ERRORE: pandoc non trovato (vedi pipeline/README.md)")
    fmt = "latex+raw_tex" if raw else "latex"
    p = subprocess.run(["pandoc", "-f", fmt, "-t", "json"], input=src, capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit("ERRORE: pandoc non riesce a leggere il documento:\n" + p.stderr)
    return json.loads(p.stdout)


def unknown_commands(ast) -> dict[str, int]:
    found: dict[str, int] = {}

    def walk(x):
        if isinstance(x, dict):
            if x.get("t") in ("RawInline", "RawBlock") and x["c"][0] == "latex":
                for name in re.findall(r"\\([a-zA-Z]+)", x["c"][1]):
                    if name not in HARMLESS_RAW and name not in ("begin", "end"):
                        found[name] = found.get(name, 0) + 1
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(ast)
    return found


def git_commit(path: Path) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return ""


def _replace_missing(book: Book, assets, jobs):
    """Formule non compilabili: mostrate come sorgente TeX (in colore di avviso)."""
    def fix_nodes(nodes):
        out = []
        for n in nodes:
            if isinstance(n, MathImage) and n.rid not in assets:
                out.append(rich.color("warn", ["$" + jobs[n.rid].tex + "$"]))
            elif isinstance(n, Styled):
                out.append(Styled(n.kind, fix_nodes(n.children), n.param))
            else:
                out.append(n)
        return out

    for ch in book.chapters:
        ch.title = fix_nodes(ch.title)
        for s in ch.sections:
            s.title = fix_nodes(s.title)
            nb = []
            for b in s.blocks:
                if isinstance(b, ImageBlock) and b.rid not in assets:
                    nb.append(Para([rich.color("warn", [jobs[b.rid].tex if b.rid in jobs else "?"])], align="center"))
                    continue
                if isinstance(b, Para):
                    b.nodes = fix_nodes(b.nodes)
                    if b.marker:
                        b.marker = fix_nodes(b.marker)
                nb.append(b)
            s.blocks = nb


def build(args) -> int:
    t0 = time.time()
    latex_dir = Path(args.latex).resolve()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rules = Rules.load(Path(args.rules) if args.rules else None)
    warn = Warnings()
    metrics = load_metrics()
    profile = VIVOACTIVE5
    work = Path(tempfile.mkdtemp(prefix="gwnotes-"))

    mains = find_main_documents(latex_dir)
    if not mains:
        print(f"ERRORE: nessun documento principale (\\documentclass + \\begin{{document}}) in {latex_dir}")
        return 2
    print(f"Documenti principali: {', '.join(str(m.relative_to(latex_dir)) for m in mains)}")

    book = Book(title="")
    all_jobs = {}
    converters = []
    included = set()
    for main in mains:
        print(f"[1/5] Compilazione LaTeX di {main.name}…")
        build_dir = work / ("latex-" + main.stem)
        if not args.no_pdf:
            try:
                pdf = compile_pdf(main, build_dir)
            except LatexError as e:
                print("ERRORE LaTeX:\n" + str(e))
                return 1
            shutil.copy(pdf, out / (main.stem + ".pdf" if len(mains) > 1 else "notes.pdf"))
            for w in latex_warnings(build_dir, main):
                warn.add("latex", w, quiet=True)
        labels = read_labels(build_dir / (main.stem + ".aux"))
        print(f"[2/5] Analisi della struttura…")
        try:
            doc = load_document(main)
        except TexError as e:
            print(f"ERRORE: {e}")
            return 1
        included.update(doc.files)
        prep = prepare(doc, rules)
        ast = run_pandoc(prep.source)
        for name, n in sorted(unknown_commands(run_pandoc(prep.source, raw=True)).items()):
            warn.add("comando-ignorato", f"\\{name} ({n}×): ignorato nella versione orologio", quiet=True)
        conv = Converter(doc, rules, labels, warn, metrics)
        conv.snippets = prep.snippets
        stream = conv.blocks(ast["blocks"])
        title = doc.title or rules.front_title
        b = build_book(stream, re.sub(r"\\[a-zA-Z]+|[{}]", "", title).strip(), rules.front_title)
        if not book.title:
            book.title = b.title if b.title != rules.front_title else main.stem
        book.chapters.extend(b.chapters)
        all_jobs.update(conv.jobs)
        converters.append((conv, doc))
        print(f"      capitoli: {len(b.chapters)}, sezioni: {sum(len(c.sections) for c in b.chapters)}, "
              f"formule inline in testo: {conv.stats['inline_text']}, come immagine: {conv.stats['inline_image']}, "
              f"equazioni: {conv.stats['display']}, figure: {conv.stats['figures']}")

    orphans = sorted(p for p in latex_dir.rglob("*.tex") if p.resolve() not in {f.resolve() for f in included})
    for p in orphans:
        warn.add("file", f"{p.relative_to(latex_dir)} non è incluso da nessun documento principale", quiet=True)

    print(f"[3/5] Rendering di {len(all_jobs)} formule/figure…")
    assets = {}
    for conv, doc in converters:
        jobs = {rid: j for rid, j in all_jobs.items() if rid in conv.jobs}
        ab = AssetBuilder(doc, rules, profile, work / ("assets-" + doc.main.stem), warn)
        assets.update(ab.build(jobs))
        print(f"      equazioni spezzate: {ab.stats['split']}, ridotte: {ab.stats['scaled']}, "
              f"con zoom: {ab.stats['zoom']}")
    _replace_missing(book, assets, all_jobs)

    bb = BundleBuilder(rules.chunk_bytes)
    keys = {}
    for rid, a in assets.items():
        k = bb.image(images.encode_resource(a.normal))
        z = bb.image(images.encode_resource(a.zoom)) if a.zoom is not None else ""
        keys[rid] = (k, z)

    print("[4/5] Impaginazione…")
    lay = Layouter(metrics, profile, assets, keys, warn)
    chapters_idx = []
    toc = []
    all_pages = {}
    total_pages = 0
    for ci, ch in enumerate(book.chapters):
        secs = []
        tsec = []
        for s in ch.sections:
            pages = SectionLayout(lay).run(s, s.title)
            enc = [p.encode() for p in pages]
            for k, pg in enumerate(enc):
                if len(pg.encode("utf-8")) > 7000:
                    warn.add("pagina", f"pagina {k + 1} di {s.id} molto grande ({len(pg.encode())} byte)")
            sp = SectionPages(s.id, plain(s.title), encode_title_lines(lay, s.title, profile.title_w), enc, ci)
            res, starts = bb.section(sp)
            secs.append((sp, res, starts))
            all_pages[s.id] = enc
            total_pages += len(enc)
            tsec.append({"id": s.id, "title": plain(s.title), "pages": len(enc), "key": res.key, "hash": res.hash})
        chapters_idx.append((encode_title_lines(lay, ch.title, profile.title_w), secs))
        toc.append({"title": plain(ch.title), "sections": tsec})

    content_hash = short_hash("|".join(f"{k}:{r.hash}" for k, r in sorted(bb.resources.items())), 12)
    version = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d.%H%M%S") if not args.version else args.version
    content_version = f"{version}-{content_hash}"
    idx_lines = build_index(book.title, metrics.font_id, content_version, chapters_idx)
    bb.add(Resource("idx", chunk_text(idx_lines, rules.chunk_bytes)))

    manifest = {
        "schema": SCHEMA,
        "contentVersion": content_version,
        "contentHash": content_hash,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sourceCommit": git_commit(REPO_ROOT),
        "title": book.title,
        "fontId": metrics.font_id,
        "chunkBytes": rules.chunk_bytes,
        "profile": profile.to_dict(),
        "index": {"key": "idx", "hash": bb.resources["idx"].hash, "chunks": len(bb.resources["idx"].chunks)},
        "toc": toc,
        "resources": {k: {"hash": r.hash, "chunks": len(r.chunks), "bytes": r.bytes, "file": res_file(k)}
                      for k, r in sorted(bb.resources.items())},
    }
    print("[5/5] Scrittura del bundle e dell'anteprima…")
    write_zip(out / "notes-bundle.zip", manifest, bb.resources)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    # anteprime
    prev_dir = out / "preview"
    if prev_dir.exists():
        shutil.rmtree(prev_dir)
    prev_dir.mkdir()
    img_res = {k: "".join(r.chunks) for k, r in bb.resources.items() if k.startswith("i:")}
    renderer = Renderer(img_res)
    chosen = list(all_pages)
    if args.preview_sections:
        chosen = [s for s in chosen if any(re.search(p, s) for p in args.preview_sections)] or chosen
    count = 0
    for sid in chosen[: args.preview]:
        pages = all_pages[sid]
        imgs = [renderer.render_page(p, i + 1, len(pages)) for i, p in enumerate(pages)]
        contact_sheet(imgs, cols=min(4, len(imgs))).save(prev_dir / f"{sid}.png", optimize=True)
        imgs[0].save(prev_dir / f"{sid}-p1.png")
        count += 1

    sizes = {"text": sum(r.bytes for k, r in bb.resources.items() if k.startswith("s:")),
             "images": sum(r.bytes for k, r in bb.resources.items() if k.startswith("i:")),
             "index": bb.resources["idx"].bytes}
    largest = max((r for k, r in bb.resources.items() if k.startswith("s:")), key=lambda r: r.bytes)
    report = [
        f"# Report di conversione\n",
        f"- Versione contenuti: `{content_version}` (schema {SCHEMA}, font `{metrics.font_id}`)",
        f"- Capitoli: {len(book.chapters)}, sezioni: {sum(len(c.sections) for c in book.chapters)}, "
        f"pagine orologio: {total_pages}",
        f"- Dati: testo {sizes['text'] / 1024:.0f} KB, immagini {sizes['images'] / 1024:.0f} KB, "
        f"indice {sizes['index'] / 1024:.1f} KB, pezzi da {rules.chunk_bytes} byte",
        f"- Sezione più grande: `{largest.key}` ({largest.bytes / 1024:.1f} KB)",
        f"- Tempo: {time.time() - t0:.0f} s, anteprime: {count} sezioni in `preview/`\n",
        "## Avvisi\n",
        warn.markdown(),
    ]
    (out / "report.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report[:6]))
    print(f"Avvisi: {warn.count()} (dettagli in {out / 'report.md'})")
    shutil.rmtree(work, ignore_errors=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="gwnotes", description="LaTeX -> bundle per Garmin")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="converte gli appunti")
    b.add_argument("--latex", default=str(REPO_ROOT / "latex"))
    b.add_argument("--out", default=str(REPO_ROOT / "dist"))
    b.add_argument("--rules", default=None)
    b.add_argument("--no-pdf", action="store_true", help="non compilare il PDF (solo per sviluppo: niente etichette)")
    b.add_argument("--preview", type=int, default=12, help="numero di sezioni in anteprima")
    b.add_argument("--preview-sections", nargs="*", help="regex degli id di sezione da mostrare in anteprima")
    b.add_argument("--version", default=None, help="versione contenuti (default: data UTC)")
    args = ap.parse_args(argv)
    if args.cmd == "build":
        return build(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
