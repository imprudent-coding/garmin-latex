"""Comando principale della pipeline.

    python -m gwnotes build [--latex ../latex] [--out ../dist] [--no-pdf] [--preview N]

Esce con codice != 0 solo per errori veri (compilazione LaTeX fallita, pandoc
mancante, ...). Tutto ciò che non si converte bene diventa immagine o testo e
finisce nel report (dist/report.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from types import SimpleNamespace

from . import images, pdfstrips, rich
from .assets import AssetBuilder
from .bundle import (SCHEMA, BundleBuilder, PrevBundle, Resource, SectionPages, build_index, build_web_packs,
                     chunk_text, image_keys, index_sections, res_file, short_hash, write_zip)
from .docmodel import Book, Converter, ImageBlock, MathImage, Para, build_book
from .latexbuild import LatexError, compile_pdf, latex_warnings, read_labels
from .layout import Layouter, SectionLayout, encode_title_lines
from .toc import chapter_header, section_titles
from .paths import REPO_ROOT
from .prepare import prepare
from .preview import Renderer, contact_sheet, parse_index, render_index
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


def _notes_from_latex(args, rules, warn, metrics, profile, work: Path, out: Path, bb: BundleBuilder):
    """Appunti dal LaTeX (build completa). Ritorna lo stato per il resto della build, o un
    codice d'uscita (int) in caso di errore."""
    latex_dir = Path(args.latex).resolve()
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
    divided: list[str] = []
    for conv, doc in converters:
        jobs = {rid: j for rid, j in all_jobs.items() if rid in conv.jobs}
        ab = AssetBuilder(doc, rules, profile, work / ("assets-" + doc.main.stem), warn)
        assets.update(ab.build(jobs))
        print(f"      equazioni spezzate: {ab.stats['split']}, ridotte: {ab.stats['scaled']}, "
              f"con zoom: {ab.stats['zoom']}")
        divided += ab.divided
        if ab.divided:
            print(f"      figure divise in pannelli: {', '.join(ab.divided)}")
    _replace_missing(book, assets, all_jobs)
    for ch in book.chapters:
        for s in ch.sections:
            if not s.qid and s.label:
                for conv, _ in converters:
                    info = conv.labels.get(s.label)
                    if info and 0 < len(info.text) <= 6:
                        s.qid, s.kind = info.text, "question"
                        break

    keys = {}
    for rid, a in assets.items():
        k = bb.image(images.encode_resource(a.normal))
        z = bb.image(images.encode_resource(a.zoom)) if a.zoom is not None else ""
        keys[rid] = (k, z)
        for pi, pa in enumerate(a.panels or []):
            pk = bb.image(images.encode_resource(pa.normal))
            pz = bb.image(images.encode_resource(pa.zoom)) if pa.zoom is not None else ""
            keys[f"{rid}#{pi}"] = (pk, pz)

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
            full, compact = section_titles(lay, profile, s, ch.title, alone=len(ch.sections) == 1)
            sp = SectionPages(s.id, plain(s.title), full, enc, ci, qid=s.qid, kind=s.kind, compact=compact)
            res, starts = bb.section(sp)
            secs.append((sp, res, starts))
            all_pages[s.id] = enc
            total_pages += len(enc)
            tsec.append({"id": s.id, "title": plain(s.title), "pages": len(enc), "key": res.key, "hash": res.hash,
                         "qid": s.qid, "kind": s.kind})
        chapters_idx.append((encode_title_lines(lay, ch.title, profile.title_w), chapter_header(lay, profile, ch), secs))
        toc.append({"title": plain(ch.title), "sections": tsec})

    return SimpleNamespace(title=book.title, n_chapters=len(book.chapters),
                           n_sections=sum(len(c.sections) for c in book.chapters), chapters_idx=chapters_idx,
                           toc=toc, all_pages=all_pages, total_pages=total_pages, divided=divided, lay=lay)


def _notes_from_bundle(prev: PrevBundle, warn, metrics, profile, bb: BundleBuilder):
    """Appunti copiati dal bundle precedente (build incrementale: cambiano solo gli esami).
    Nessuna compilazione: indice, sezioni e immagini sono quelli della Release precedente."""
    chapters = prev.notes_chapters()
    keys = set()
    for ch in chapters:
        for sid, _ in ch.sections:
            res = prev.resources["s:" + sid]
            bb.add(res)
            keys.update(image_keys(["\n".join(res.chunks)]))
    for k in sorted(keys):
        if k in prev.resources:
            bb.add(prev.resources[k])
    toc = [c for c in prev.manifest.get("toc", []) if c.get("lib") != "esami"]
    print(f"[1-4/5] Appunti dal bundle precedente: {len(chapters)} capitoli, "
          f"{sum(len(c.sections) for c in chapters)} sezioni, {len(keys)} immagini")
    return SimpleNamespace(title=prev.title, n_chapters=len(chapters),
                           n_sections=sum(len(c.sections) for c in chapters), chapters_idx=list(chapters),
                           toc=toc, all_pages={}, total_pages=sum(s["pages"] for c in toc for s in c["sections"]),
                           divided=[], lay=Layouter(metrics, profile, {}, {}, warn))


def build(args) -> int:
    t0 = time.time()
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    rules = Rules.load(Path(args.rules) if args.rules else None)
    warn = Warnings()
    metrics = load_metrics()
    profile = VIVOACTIVE5
    work = Path(tempfile.mkdtemp(prefix="gwnotes-"))
    bb = BundleBuilder(rules.chunk_bytes)
    prev = PrevBundle.load(Path(args.reuse)) if args.reuse else None
    if prev is not None and not prev.compatible(metrics.font_id, rules.chunk_bytes):
        print("Bundle precedente con schema, font o pezzi diversi: non riutilizzabile")
        prev = None
    if args.notes_from_reuse:
        if prev is None:
            print("ERRORE: --notes-from-reuse senza un bundle precedente riutilizzabile")
            return 3
        notes = _notes_from_bundle(prev, warn, metrics, profile, bb)
    else:
        notes = _notes_from_latex(args, rules, warn, metrics, profile, work, out, bb)
        if isinstance(notes, int):
            return notes
    lay = notes.lay
    chapters_idx, toc, all_pages = notes.chapters_idx, notes.toc, notes.all_pages
    total_pages = notes.total_pages

    # simulazioni d'esame: PDF già impaginati per l'orologio, tagliati in strisce
    exam_ids: list[str] = []
    exams_meta: dict[str, dict] = {}
    if args.exams:
        exam_pdfs = pdfstrips.find_exams(Path(args.exams).resolve())
        print(f"[4b] Simulazioni d'esame: {len(exam_pdfs)} PDF in {args.exams}")
        groups: dict[str, list] = {}  # prova -> [(sid, etichetta, pagine)]
        for pdf in exam_pdfs:
            sid = "x-" + re.sub(r"[^a-z0-9]+", "-", pdf.parent.name.lower()).strip("-")
            # PDF già convertito nel bundle precedente, con lo stesso codice: si riusa
            ckey = short_hash(pdf.read_bytes(), 16) + "-" + pdfstrips.code_hash()
            old = prev.exams.get(sid) if prev is not None else None
            if old and old.get("key") == ckey and old.get("pdftitle") is not None and prev.has_section(sid):
                enc = prev.section_pages(sid)
                for k in image_keys(enc):
                    bb.add(prev.resources[k])
                pdftitle = old["pdftitle"]
                print(f"      {pdf.parent.name}: invariato, {len(enc)} pagine riprese dal bundle precedente")
            else:
                strips, meta = pdfstrips.build_pages(pdf, profile)
                keys = []
                for st in strips:
                    n, tiles = st.encode()
                    # zoom diviso in strisce: chiavi separate da ";" (shared/FORMAT.md)
                    keys.append((bb.image(n), ";".join(bb.image(t) for t in tiles)))
                enc = pdfstrips.layout_pages(strips, keys, profile)
                pdftitle = meta["title"]
                print(f"      {pdf.parent.name}: {len(enc)} pagine, {meta['blocks']} blocchi")
            exams_meta[sid] = {"key": ckey, "pdftitle": pdftitle}
            label = pdfstrips.exam_label(pdftitle, pdf.parent.name)
            groups.setdefault(label.prova, []).append((sid, label, enc))
        # una prova per gruppo, dalla più recente; nel gruppo gli esercizi in ordine
        for prova in pdfstrips.order_provas(list(groups)):
            ci = len(chapters_idx)
            ch_title = [groups[prova][0][1].heading]
            ex_secs, ex_nodes, tsec = [], [], []
            for sid, label, enc in groups[prova]:
                sec = SimpleNamespace(id=sid, title=[f"{label.qid}  {label.topic}" if label.qid else label.topic],
                                      kind="question" if label.qid else "section", qid=label.qid, label="")
                ex_nodes.append(sec)
                full, compact = section_titles(lay, profile, sec, ch_title, alone=False)
                sp = SectionPages(sid, plain(sec.title), full, enc, ci, qid=sec.qid, kind=sec.kind, compact=compact)
                res, starts = bb.section(sp)
                ex_secs.append((sp, res, starts))
                all_pages[sid] = enc
                exam_ids.append(sid)
                total_pages += len(enc)
                tsec.append({"id": sid, "title": plain(sec.title), "pages": len(enc), "key": res.key,
                             "hash": res.hash, "qid": sec.qid, "kind": sec.kind})
            # intestazione del gruppo anche con un solo esercizio: dice di quale prova si tratta
            header = encode_title_lines(lay, [Styled("small", [rich.color("heading", ch_title)])],
                                        profile.row_w_header, max_lines=1)[0]
            chapters_idx.append((encode_title_lines(lay, ch_title, profile.title_w), header, ex_secs, "esami"))
            toc.append({"title": ch_title[0], "lib": "esami", "sections": tsec})

    # file per il download via web (GitHub Pages): sezione + immagini, per sezione
    web_files, web_packs = build_web_packs(
        [sec for c in chapters_idx for sec in index_sections(c)],
        bb.resources)
    web_base = (args.web_base or "").strip()
    if web_base and not web_base.endswith("/"):
        web_base += "/"
    # contentHash copre anche l'indice (tranne la riga V, che contiene la versione):
    # l'app Android salta un bundle con lo stesso contentHash, quindi un cambio solo
    # dell'indice (es. righe W/F dei file web) deve cambiarlo.
    idx_body = build_index(notes.title, metrics.font_id, "", chapters_idx, web_base=web_base, web_packs=web_packs)[1:]
    content_hash = short_hash("|".join(f"{k}:{r.hash}" for k, r in sorted(bb.resources.items()))
                              + "|idx:" + short_hash("\n".join(idx_body)), 12)
    version = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d.%H%M%S") if not args.version else args.version
    content_version = f"{version}-{content_hash}"
    idx_lines = build_index(notes.title, metrics.font_id, content_version, chapters_idx,
                            web_base=web_base, web_packs=web_packs)
    bb.add(Resource("idx", chunk_text(idx_lines, rules.chunk_bytes)))

    manifest = {
        "schema": SCHEMA,
        "contentVersion": content_version,
        "contentHash": content_hash,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "sourceCommit": git_commit(REPO_ROOT),
        "title": notes.title,
        "fontId": metrics.font_id,
        "chunkBytes": rules.chunk_bytes,
        "profile": profile.to_dict(),
        "index": {"key": "idx", "hash": bb.resources["idx"].hash, "chunks": len(bb.resources["idx"].chunks)},
        "toc": toc,
        # build incrementali: impronta degli ingressi degli appunti e PDF degli esami già convertiti
        "inputs": args.inputs,
        "exams": exams_meta,
        "resources": {k: {"hash": r.hash, "chunks": len(r.chunks), "bytes": r.bytes, "file": res_file(k)}
                      for k, r in sorted(bb.resources.items())},
    }
    print("[5/5] Scrittura del bundle e dell'anteprima…")
    write_zip(out / "notes-bundle.zip", manifest, bb.resources)
    web_dir = out / "web"
    if web_dir.exists():
        shutil.rmtree(web_dir)
    (web_dir / "w").mkdir(parents=True)
    for name, body in web_files.items():
        (web_dir / "w" / f"{name}.json").write_bytes(body)
    # indice attuale, a nome fisso: l'orologio lo controlla con "Sincronizza ora" e
    # all'avvio, così vede una nuova versione senza aspettare l'app del telefono
    idx_res = bb.resources["idx"]
    (web_dir / "w" / "idx.json").write_text(
        json.dumps({"ver": content_version, "schema": SCHEMA, "font": metrics.font_id, "hash": idx_res.hash,
                    "chunks": idx_res.chunks}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (web_dir / "index.html").write_text(
        f"<!doctype html><meta charset=utf-8><title>{html.escape(notes.title)}</title>"
        f"<p>File degli appunti per l'app dell'orologio (versione {content_version}).</p>\n", encoding="utf-8")
    print(f"      web: {len(web_files)} file, {sum(len(b) for b in web_files.values()) // 1024} KB"
          + (f" su {web_base}" if web_base else " (senza --web-base: l'indice non li cita)"))
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    # anteprime
    prev_dir = out / "preview"
    if prev_dir.exists():
        shutil.rmtree(prev_dir)
    prev_dir.mkdir()
    img_res = {k: "".join(r.chunks) for k, r in bb.resources.items() if k.startswith("i:")}
    renderer = Renderer(img_res)
    chosen = [s for s in all_pages if s not in exam_ids]
    if args.preview_sections:
        chosen = [s for s in chosen if any(re.search(p, s) for p in args.preview_sections)] or chosen
    chosen = chosen[: args.preview] + exam_ids  # le simulazioni d'esame sempre
    count = 0
    for sid in chosen:
        pages = all_pages[sid]
        imgs = [renderer.render_page(p, i + 1, len(pages)) for i, p in enumerate(pages)]
        contact_sheet(imgs, cols=min(4, len(imgs))).save(prev_dir / f"{sid}.png", optimize=True)
        imgs[0].save(prev_dir / f"{sid}-p1.png")
        count += 1

    # anteprima dell'elenco delle domande, con alcune voci selezionate
    rows = parse_index(idx_lines)
    nsel = sum(1 for r in rows if r["t"] == "S")
    picks = sorted({0, 2, nsel // 3, nsel // 2, (2 * nsel) // 3, nsel - 1})
    contact_sheet([render_index(renderer, rows, k) for k in picks if 0 <= k < nsel],
                  cols=3).save(prev_dir / "_elenco.png", optimize=True)

    sizes = {"text": sum(r.bytes for k, r in bb.resources.items() if k.startswith("s:")),
             "images": sum(r.bytes for k, r in bb.resources.items() if k.startswith("i:")),
             "index": bb.resources["idx"].bytes}
    largest = max((r for k, r in bb.resources.items() if k.startswith("s:")), key=lambda r: r.bytes)
    report = [
        f"# Report di conversione\n",
        f"- Versione contenuti: `{content_version}` (schema {SCHEMA}, font `{metrics.font_id}`)",
        f"- Capitoli: {notes.n_chapters}, sezioni: {notes.n_sections}, "
        f"pagine orologio: {total_pages}"
        + (f" (simulazioni d'esame: {len(exam_ids)})" if args.exams else "")
        + (" — appunti ripresi dalla Release precedente" if args.notes_from_reuse else ""),
        f"- Dati: testo {sizes['text'] / 1024:.0f} KB, immagini {sizes['images'] / 1024:.0f} KB, "
        f"indice {sizes['index'] / 1024:.1f} KB, pezzi da {rules.chunk_bytes} byte",
        f"- Sezione più grande: `{largest.key}` ({largest.bytes / 1024:.1f} KB)",
        f"- Figure divise in pannelli (una pagina per pannello dopo la figura intera): "
        f"{', '.join(notes.divided) if notes.divided else 'nessuna'}",
        f"- Tempo: {time.time() - t0:.0f} s, anteprime: {count} sezioni in `preview/`\n",
        "## Avvisi\n",
        warn.markdown(),
    ]
    (out / "report.md").write_text("\n".join(report), encoding="utf-8")
    print("\n".join(report[:7]))
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
    b.add_argument("--exams", default="",
                   help="cartella delle simulazioni d'esame (<cartella>/<esercizio>/orologio.pdf)")
    b.add_argument("--reuse", default="",
                   help="bundle precedente (notes-bundle.zip): gli esami con lo stesso PDF non si riconvertono")
    b.add_argument("--notes-from-reuse", action="store_true",
                   help="appunti presi dal bundle di --reuse, senza LaTeX (cambiano solo gli esami)")
    b.add_argument("--inputs", default="", help="impronta degli ingressi degli appunti, salvata nel manifest")
    b.add_argument("--version", default=None, help="versione contenuti (default: data UTC)")
    b.add_argument("--web-base", default="",
                   help="URL dei file web (es. https://utente.github.io/repo/w/); vuoto = solo bundle")
    args = ap.parse_args(argv)
    if args.cmd == "build":
        return build(args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
