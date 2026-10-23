"""Test della pipeline. Quelli che richiedono LaTeX/pandoc vengono saltati se mancano."""
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gwnotes import bundle, eqsplit, images, lz, panels  # noqa: E402
from gwnotes.mathconv import Unconvertible, convert  # noqa: E402
from gwnotes.prepare import prepare  # noqa: E402
from gwnotes.profile import VIVOACTIVE5  # noqa: E402
from gwnotes.rich import load_metrics, plain  # noqa: E402
from gwnotes.rules import Rules  # noqa: E402
from gwnotes.toc import strip_qid  # noqa: E402
from gwnotes.texsource import load_document, parse_definitions, strip_comments, struct_from_macro  # noqa: E402

HAS_TEX = shutil.which("pdflatex") and shutil.which("latexmk")
HAS_PANDOC = shutil.which("pandoc")


# ---------------------------------------------------------------- matematica


@pytest.mark.parametrize("tex,expected", [
    (r"\alpha+\beta", "α+β"),
    (r"x^2", "x^2"),
    (r"v_{tot}", "v_{tot}"),
    (r"\frac{\mu}{2a}", "μ/(2a)"),
    (r"\frac{dh}{dt}", "dh/dt"),
    (r"\sqrt{\mu/r}", "√(μ/r)"),
    (r"90^\circ", "90°"),
    (r"a\cos\theta", "a cos θ"),
    (r"\mathcal E=\frac{v^2}{2}-\frac{\mu}{r}", "ℰ=v^2/2−μ/r"),
    (r"\Delta V\to\infty", "ΔV→∞"),
])
def test_math_to_text(tex, expected):
    assert plain(convert(tex, load_metrics().charset)) == expected


@pytest.mark.parametrize("tex", [
    r"\begin{bmatrix}1&0\\0&1\end{bmatrix}",
    r"\underbrace{x}_{y}",
    r"\boxed{x}",
    r"\frac{\frac{\frac{a}{b}}{c}}{d}",
    r"\unknownmacro{x}",
])
def test_math_unconvertible(tex):
    with pytest.raises(Unconvertible):
        convert(tex, load_metrics().charset)


def test_vector_styles():
    nodes = convert(r"\underline{\underline R}\,\hat r\,\dot\theta", load_metrics().charset)
    kinds = [n.kind for n in nodes if not isinstance(n, str)]
    assert kinds == ["uul", "hat", "dot"]


def test_missing_glyph_goes_to_image():
    with pytest.raises(Unconvertible):
        convert(r"\text{日本}", load_metrics().charset)


# ---------------------------------------------------------------- immagini


def test_rle_roundtrip():
    img = Image.new("L", (123, 45), 0)
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 100, 30], fill=3)
    d.line([0, 44, 122, 0], fill=1, width=3)
    enc = images.encode_resource(img)
    back = images.decode_resource(enc)
    assert back.size == img.size and back.tobytes() == img.tobytes()


def test_lz_roundtrip():
    import random
    rnd = random.Random(1)
    samples = [b"", b"a", b"abcabcabcabcabcabc" * 50, bytes(rnd.randrange(256) for _ in range(3000)),
               bytes([0, 0, 0, 0, 5]) * 2000 + bytes(range(256)) * 3]
    for d in samples:
        assert lz.decompress(lz.compress(d), len(d)) == d
    assert len(lz.compress(b"x" * 10000)) < 100


def test_image_resource_is_compressed_and_lossless():
    img = Image.new("L", (200, 80), 0)
    d = ImageDraw.Draw(img)
    for x in range(0, 200, 20):
        d.line([x, 0, x + 10, 79], fill=2, width=2)
    enc = images.encode_resource(img)
    head = enc.split("|", 1)[0].split(",")
    assert len(head) == 4 and head[2] == "2"
    assert images.decode_resource(enc).tobytes() == img.tobytes()


def _grid_figure(rows, cols, pw=120, ph=90, gap=30, label=False):
    img = Image.new("L", (cols * pw + (cols - 1) * gap, rows * ph + (rows - 1) * gap + (40 if label else 0)), 0)
    d = ImageDraw.Draw(img)
    for r in range(rows):
        for c in range(cols):
            x, y = c * (pw + gap), r * (ph + gap)
            d.rectangle([x, y, x + pw - 1, y + ph - 1], outline=3)
            d.line([x + 5, y + ph - 10, x + pw - 5, y + 10], fill=2)
    if label:  # didascalia sottile staccata sotto la griglia
        d.rectangle([10, img.height - 8, 60, img.height - 4], fill=3)
    return img


def test_grid_figures_are_split_strips_are_not():
    boxes = panels.grid_panels(_grid_figure(2, 2))
    assert boxes is not None and len(boxes) == 4
    assert boxes[0][1] < boxes[2][1] and boxes[0][0] < boxes[1][0]  # ordine: righe, poi colonne
    assert panels.grid_panels(_grid_figure(1, 3)) is None            # striscia: resta intera
    assert panels.grid_panels(_grid_figure(2, 2, label=True)) is None  # didascalia staccata: intera
    assert panels.grid_panels(_grid_figure(2, 2), mode="whole") is None
    assert len(panels.grid_panels(_grid_figure(1, 3), mode="split")) == 3


def test_color_image_roundtrip_keeps_hues():
    """Figura a colori: sfondo bianco -> nero, linea rossa resta rossa, tratti neri -> chiari."""
    img = Image.new("RGB", (120, 60), "white")
    d = ImageDraw.Draw(img)
    d.line((0, 10, 119, 10), fill=(220, 30, 30), width=3)      # urto rosso
    d.line((0, 30, 119, 30), fill=(0, 170, 220), width=3)      # gola ciano
    d.line((0, 50, 119, 50), fill=(0, 0, 0), width=2)          # tratto nero
    assert images.is_colorful(img) and not images.is_colorful(img.convert("L"))
    enc = images.encode_color(img, invert=True)
    head = enc.split("|")[0].split(",")
    assert head[:3] == ["120", "60", "4"] and all(x.isdigit() for x in head)  # intestazione solo numerica
    back = images.decode_resource(enc)
    assert back.mode == "RGB" and back.size == (120, 60)
    assert back.getpixel((5, 2)) == (0, 0, 0)                  # sfondo
    r, g, b = back.getpixel((60, 10))
    assert r > 150 and g < 100 and b < 100                     # ancora rosso
    r, g, b = back.getpixel((60, 30))
    assert b > 150 and r < 100                                 # ancora ciano/blu
    assert min(back.getpixel((60, 50))) > 200                  # il nero diventa bianco


def test_to_levels_inverts_white_background():
    img = Image.new("L", (20, 20), 255)
    ImageDraw.Draw(img).rectangle([5, 5, 14, 14], fill=0)
    lv = images.to_levels(img)
    assert lv.getpixel((0, 0)) == 0 and lv.getpixel((10, 10)) == 3


# ---------------------------------------------------------------- sorgenti e struttura


def test_strip_comments_keeps_escaped_percent():
    assert strip_comments("a 50\\% b % commento") == "a 50\\% b "


def test_struct_macro_detection():
    src = r"""
\newcommand{\lezione}[2]{\clearpage\section*{#1: #2}\addcontentsline{toc}{section}{#1: #2}\label{lez:#1}}
\newcommand{\nota}[1]{\textbf{#1}}
"""
    macros, *_ = parse_definitions(src)
    sm = struct_from_macro(macros["lezione"])
    assert sm and sm.level == 1 and sm.title_tpl == "#1: #2" and sm.label_tpl == "lez:#1"
    assert struct_from_macro(macros["nota"]) is None


def _write(tmp, name, text):
    p = tmp / name
    p.write_text(text, encoding="utf-8")
    return p


def test_input_flattening_and_prepare(tmp_path):
    _write(tmp_path, "main.tex", "\\documentclass{article}\n\\begin{document}\n\\input{cap1}\n\\include{cap2}\n"
                                 "\\end{document}\n")
    _write(tmp_path, "cap1.tex", "\\section{Primo}\\label{sec:a} Testo $x^2$.\n")
    _write(tmp_path, "cap2.tex", "\\section{Secondo}\n\\subsection{Dettaglio} altro\n")
    doc = load_document(tmp_path / "main.tex")
    assert [p.name for p in doc.files] == ["main.tex", "cap1.tex", "cap2.tex"]
    prep = prepare(doc, Rules())
    assert prep.source.count("\\begin{gwhead2}") == 2 and prep.source.count("\\begin{gwhead3}") == 1


# ---------------------------------------------------------------- spezzamento equazioni


def test_split_at_relations_not_inside_parens():
    parts = eqsplit.split_points(r"a=b+c\ (d=e)\;\Rightarrow\; f", eqsplit.RELATIONS)
    assert parts == ["a", r"=b+c\ (d=e)", r"\;\Rightarrow\; f"]


def test_unwrap_rows_of_system():
    rows = eqsplit.unwrap_rows(r"\left\{\begin{aligned}a&=1\\b&=2&&\text{(nota)}\end{aligned}\right.")
    assert rows == ["a=1", "b=2", r"\text{(nota)}"]


def test_pack_avoids_orphans():
    lines = eqsplit.pack([20, 290], 300, 24)
    assert lines == [[0, 1]]


def test_strip_qid():
    assert plain(strip_qid(["A1\u00a0\u00a0First integral"], "A1")) == "First integral"
    assert plain(strip_qid(["B2 Synodic"], "A1")) == "B2 Synodic"


# ---------------------------------------------------------------- bundle


def test_chunking_respects_limit():
    parts = ["α" * 300, "b" * 500, "c" * 2000]
    chunks = bundle.chunk_text(parts, 800)
    assert all(len(c.encode("utf-8")) <= 800 for c in chunks)
    assert "".join(chunks).replace("\n", "") == "".join(parts)


def test_profile_band_is_narrower_at_top():
    _, w_top = VIVOACTIVE5.band(40, 70)
    _, w_mid = VIVOACTIVE5.band(180, 210)
    assert w_top < w_mid <= 390


def test_web_packs_split_and_dedupe():
    R = bundle.Resource
    res = {"s:a": R("s:a", ["x" * 1000]), "s:b": R("s:b", ["y" * 1000]),
           "i:1": R("i:1", ["1" * 20000]), "i:2": R("i:2", ["2" * 20000])}
    files, by_sec = bundle.build_web_packs([("a", "s:a", ["i:1", "i:2"]), ("b", "s:b", ["i:2"])], res, limit=32000)
    assert len(by_sec["a"]) == 2 and len(by_sec["b"]) == 1  # a: [s:a, i:1] + [i:2]; b: solo s:b
    got = {}
    for name in by_sec["a"] + by_sec["b"]:
        for k, h, chunks in json.loads(files[name])["r"]:
            assert h == res[k].hash and chunks == res[k].chunks
            got[k] = got.get(k, 0) + 1
    assert got == {"s:a": 1, "i:1": 1, "i:2": 1, "s:b": 1}
    assert bundle.image_keys(["P\nI1,2,3,4,0,i:1,i:2\nT1,1,x", "P\nI1,2,3,4,0,i:1,"]) == ["i:1", "i:2"]


# ---------------------------------------------------------------- end-to-end


SAMPLE = r"""\documentclass[11pt]{article}
\usepackage{amsmath,graphicx}
\newcommand{\vect}[1]{\underline{#1}}
\newcommand{\capitolo}[1]{\section*{#1}\addcontentsline{toc}{section}{#1}}
\newtcolorbox{nota}{title={Nota}}
\begin{document}
\capitolo{Cinematica}
\subsection{Moto circolare}\label{sec:circ}
La velocità è $\vect v=\vect\omega\times\vect r$ e $v=\omega r$.
\begin{equation}
a_c=\frac{v^2}{r}=\omega^2 r,\qquad T=\frac{2\pi}{\omega}\quad\text{(periodo del moto circolare uniforme)}
\end{equation}
Una matrice inline $\begin{pmatrix}1&0\\0&1\end{pmatrix}$ e un riferimento alla sezione \ref{sec:circ}.
\begin{itemize}\item primo \item secondo con $\sum_{i=1}^N m_i$\end{itemize}
\subsection{Seconda}
Testo.
\end{document}
"""


@pytest.mark.skipif(not (HAS_TEX and HAS_PANDOC), reason="servono TeX Live e pandoc")
def test_end_to_end(tmp_path):
    src = tmp_path / "latex"
    src.mkdir()
    (src / "main.tex").write_text(SAMPLE.replace("\\newtcolorbox{nota}{title={Nota}}\n", ""), encoding="utf-8")
    out = tmp_path / "dist"
    p = subprocess.run([sys.executable, "-m", "gwnotes", "build", "--latex", str(src), "--out", str(out),
                        "--preview", "2", "--web-base", "https://x.example/w"], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    z = zipfile.ZipFile(out / "notes-bundle.zip")
    m = json.loads(z.read("manifest.json"))
    assert m["schema"] == bundle.SCHEMA
    assert [c["title"] for c in m["toc"]] == ["Cinematica"]
    assert [s["title"] for s in m["toc"][0]["sections"]] == ["Moto circolare", "Seconda"]
    for key, r in m["resources"].items():
        data = json.loads(z.read(r["file"]))
        assert data["hash"] == r["hash"] and len(data["chunks"]) == r["chunks"]
        assert all(len(c.encode("utf-8")) <= m["chunkBytes"] for c in data["chunks"])
    sec = json.loads(z.read(m["resources"]["s:sec-circ"]["file"]))
    text = "\n".join(sec["chunks"])
    assert text.startswith("P\n") and "\nI" in text  # almeno un'immagine (equazione)
    assert "Moto" in text and "circolare" in text and "∑" in text
    # le immagini non si spezzano tra due pagine: ogni riga "I" parte dalla riga 0
    assert all(l[1:].split(",")[4] == "0" for l in text.split("\n") if l.startswith("I"))
    assert (out / "preview").exists() and (out / "notes.pdf").exists()
    assert (out / "preview" / "_elenco.png").exists()
    idx = "\n".join(json.loads(z.read(m["resources"]["idx"]["file"]))["chunks"])
    q = [l.split("|") for l in idx.split("\n") if l.startswith("Q|")]
    assert len(q) == 2 and all(len(f) == 6 for f in q)
    assert "W|https://x.example/w/" in idx.split("\n")
    f_rows = [l.split("|") for l in idx.split("\n") if l.startswith("F|")]
    assert [f[1] for f in f_rows] == ["sec-circ", m["toc"][0]["sections"][1]["id"]]
    web_keys = set()
    for f in f_rows:
        for name in f[2].split(";"):
            web_keys |= {r[0] for r in json.loads((out / "web" / "w" / f"{name}.json").read_text())["r"]}
    assert web_keys == {k for k in m["resources"] if k != "idx"}
    # indice attuale sul web, per la sincronizzazione dell'orologio senza telefono
    widx = json.loads((out / "web" / "w" / "idx.json").read_text())
    assert widx["ver"] == m["contentVersion"] and widx["hash"] == m["resources"]["idx"]["hash"]
    assert "\n".join(widx["chunks"]) == idx
    # stesso contenuto, indice diverso (senza file web): il contentHash deve cambiare,
    # altrimenti l'app Android terrebbe il bundle vecchio
    out2 = tmp_path / "dist2"
    p2 = subprocess.run([sys.executable, "-m", "gwnotes", "build", "--latex", str(src), "--out", str(out2),
                         "--preview", "0"], cwd=ROOT, capture_output=True, text=True)
    assert p2.returncode == 0, p2.stdout + p2.stderr
    m2 = json.loads(zipfile.ZipFile(out2 / "notes-bundle.zip").read("manifest.json"))
    assert {k: r["hash"] for k, r in m2["resources"].items() if k != "idx"} == \
        {k: r["hash"] for k, r in m["resources"].items() if k != "idx"}  # stesse sezioni e immagini
    assert m2["contentHash"] != m["contentHash"]


@pytest.mark.skipif(not (HAS_TEX and HAS_PANDOC), reason="servono TeX Live e pandoc")
def test_question_ids_from_currentlabel(tmp_path):
    src = tmp_path / "latex"
    src.mkdir()
    (src / "main.tex").write_text(r"""\documentclass{article}
\makeatletter
\newcommand{\gruppo}[2]{\clearpage\addcontentsline{toc}{section}{#1. #2}}
\newcommand{\domanda}[2]{\section*{#1\quad #2}\addcontentsline{toc}{subsection}{#1\quad #2}\def\@currentlabel{#1}\label{q:#1}}
\makeatother
\begin{document}
\gruppo{A}{Primo gruppo}
Testo introduttivo del gruppo.
\domanda{A1}{Che cos'è $x^2$?}
Risposta.
\domanda{A2}{Seconda domanda}
Altra risposta.
\end{document}
""", encoding="utf-8")
    out = tmp_path / "dist"
    p = subprocess.run([sys.executable, "-m", "gwnotes", "build", "--latex", str(src), "--out", str(out),
                        "--preview", "1"], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 0, p.stdout + p.stderr
    m = json.loads(zipfile.ZipFile(out / "notes-bundle.zip").read("manifest.json"))
    secs = m["toc"][0]["sections"]
    assert [(s["kind"], s["qid"]) for s in secs] == [("intro", ""), ("question", "A1"), ("question", "A2")]


@pytest.mark.skipif(not HAS_TEX, reason="serve TeX Live")
def test_latex_error_fails_build_with_clear_message(tmp_path):
    src = tmp_path / "latex"
    src.mkdir()
    (src / "main.tex").write_text("\\documentclass{article}\n\\begin{document}\n\\badcommand\n\\end{document}\n")
    p = subprocess.run([sys.executable, "-m", "gwnotes", "build", "--latex", str(src), "--out",
                        str(tmp_path / "d")], cwd=ROOT, capture_output=True, text=True)
    assert p.returncode == 1
    assert "Undefined control sequence" in p.stdout and "main.tex" in p.stdout


# ---------------------------------------------------------------- simulazioni d'esame (PDF a strisce)

from gwnotes import pdfstrips  # noqa: E402


def _page_with_lines(rows, width=600, height=900):
    """Pagina bianca con rettangoli neri (x0, y0, x1, y1) al posto delle righe di testo."""
    img = Image.new("L", (width, height), 255)
    d = ImageDraw.Draw(img)
    for r in rows:
        d.rectangle(r, fill=0)
    return img


def test_strip_blocks_and_kinds():
    left, right = 10, 10 + pdfstrips.STRIP_W
    page = _page_with_lines([
        (left, 20, right - 20, 40),          # riga di testo
        (left, 45, right + 60, 75),          # equazione che sporge di poco
        (left, 100, right + 300, 400),       # figura larga il doppio
        (left, 404, right + 300, 420),       # suo pezzo staccato da una riga vuota
        (left, 460, right - 40, 480),        # didascalia
    ])
    blocks = pdfstrips.ink_blocks(page, 0)
    assert [(b.y0, b.y1) for b in blocks] == [(20, 41), (45, 76), (100, 401), (404, 421), (460, 481)]
    groups = pdfstrips.classify(blocks, left, right, max_h=260)
    assert [g[0].kind for g in groups] == ["text", "shrink", "page", "text"]
    assert len(groups[2]) == 2  # i due pezzi della figura restano insieme


def test_strip_height_fits_circle():
    h = pdfstrips.strip_height(VIVOACTIVE5, pdfstrips.STRIP_W)
    p = VIVOACTIVE5
    assert 200 < h < 300
    assert p.band(p.r - h / 2, p.r + h / 2)[1] >= pdfstrips.STRIP_W


def test_exam_label_and_order():
    lab = pdfstrips.exam_label("Prova del 14/09/2026 – Esercizio 2: Mach nell'ugello", "2026-09-14_E02")
    assert (lab.prova, lab.qid, lab.topic) == ("14/09/2026", "E2", "Mach nell'ugello")
    lab = pdfstrips.exam_label("Titolo libero", "2025-01-30_altro")
    assert (lab.prova, lab.qid, lab.topic) == ("30/01/2025", "", "Titolo libero")
    order = sorted(["14/09/2026", "30/01/2025", "02/10/2026"], key=pdfstrips.prova_sort_key, reverse=True)
    assert order == ["02/10/2026", "14/09/2026", "30/01/2025"]


def test_column_from_pdf_keywords():
    assert pdfstrips.column_cm({"Keywords": "colonna=0.2cm+4.6cm"}) == (0.2, 4.6)
    assert pdfstrips.column_cm({}) == pdfstrips.DEFAULT_COLUMN


def test_index_library_row():
    sp = bundle.SectionPages("x-a", "A", [("A", 10)], ["P"], 0)
    res = bundle.Resource("s:x-a", ["P"])
    lines = bundle.build_index("T", "f", "v", [([("Esami", 50)], None, [(sp, res, [0])], "esami")])
    assert lines[1].startswith("C|1|") and lines[2] == "L|esami" and lines[3].startswith("S|x-a|")
    # senza libreria: nessuna riga L (compatibile con gli indici di prima)
    lines = bundle.build_index("T", "f", "v", [([("Appunti", 50)], None, [(sp, res, [0])])])
    assert not any(line.startswith("L|") for line in lines)


def _exam_dir(root: Path, name: str, text: str) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / "orologio.tex").write_text(r"""\documentclass[11pt]{article}
\usepackage[paperwidth=12cm,paperheight=40cm,left=0.2cm,top=0.2cm,textwidth=4.6cm,textheight=39cm]{geometry}
\usepackage[pdftitle={Prova},pdfkeywords={colonna=0.2cm+4.6cm}]{hyperref}
\pagestyle{empty}\hfuzz=20cm\raggedright
\begin{document}
""" + text + "\n\\end{document}\n", encoding="utf-8")
    subprocess.run(["latexmk", "-pdf", "-quiet", "orologio.tex"], cwd=d, check=True, capture_output=True)
    return d


@pytest.mark.skipif(not (HAS_TEX and HAS_PANDOC), reason="servono TeX Live e pandoc")
def test_incremental_build_matches_full(tmp_path):
    """Build incrementale (appunti dal bundle precedente, esami invariati riusati) =
    build completa: stesso contentHash. Un esame nuovo si converte, gli altri no."""
    src = tmp_path / "latex"
    src.mkdir()
    (src / "main.tex").write_text(SAMPLE.replace("\\newtcolorbox{nota}{title={Nota}}\n", ""), encoding="utf-8")
    exams = tmp_path / "esami"
    _exam_dir(exams, "2026-01-01_a", "Primo esercizio. " * 30)

    def build(out, *extra):
        p = subprocess.run([sys.executable, "-m", "gwnotes", "build", "--latex", str(src), "--out", str(out),
                            "--preview", "0", "--web-base", "https://x.example/w", "--exams", str(exams), *extra],
                           cwd=ROOT, capture_output=True, text=True)
        assert p.returncode == 0, p.stdout + p.stderr
        return p.stdout, json.loads((out / "manifest.json").read_text())

    _, full = build(tmp_path / "d1")
    prev = str(tmp_path / "d1" / "notes-bundle.zip")
    log, inc = build(tmp_path / "d2", "--reuse", prev, "--notes-from-reuse")
    assert "invariato" in log and "Appunti dal bundle precedente" in log
    assert inc["contentHash"] == full["contentHash"]
    assert sorted((tmp_path / "d1" / "web" / "w").iterdir()) != [] and \
        sorted(p.name for p in (tmp_path / "d1" / "web" / "w").iterdir()) == \
        sorted(p.name for p in (tmp_path / "d2" / "web" / "w").iterdir())
    # nuovo esame: solo quello si converte; il gruppo esami ha due voci
    _exam_dir(exams, "2026-02-02_b", "Secondo esercizio. " * 30)
    log, inc2 = build(tmp_path / "d3", "--reuse", prev, "--notes-from-reuse")
    assert log.count("invariato") == 1 and "2026-02-02_b:" in log
    # un gruppo per prova (data dalla cartella), dalla più recente
    assert [c["title"] for c in inc2["toc"] if c.get("lib") == "esami"] == \
        ["Prova del 02/02/2026", "Prova del 01/01/2026"]
    assert inc2["contentHash"] != full["contentHash"]
    # cartella cancellata: l'esame sparisce dal bundle (e dall'orologio, al nuovo indice)
    shutil.rmtree(exams / "2026-01-01_a")
    _, inc3 = build(tmp_path / "d4", "--reuse", str(tmp_path / "d3" / "notes-bundle.zip"), "--notes-from-reuse")
    assert [c["title"] for c in inc3["toc"] if c.get("lib") == "esami"] == ["Prova del 02/02/2026"]
    assert not any(k.startswith("s:x-2026-01-01") for k in inc3["resources"])


@pytest.mark.skipif(not HAS_TEX, reason="LaTeX non installato")
def test_exam_pdf_to_pages(tmp_path):
    """PDF formato orologio vero: colonna dichiarata, testo, un'equazione lunga, nessuna riga persa."""
    d = tmp_path / "2026-01-01_prova"
    d.mkdir()
    (d / "orologio.tex").write_text(r"""\documentclass[11pt]{article}
\usepackage[paperwidth=12cm,paperheight=40cm,left=0.2cm,top=0.2cm,textwidth=4.6cm,textheight=39cm]{geometry}
\usepackage[pdftitle={Prova},pdfkeywords={colonna=0.2cm+4.6cm}]{hyperref}
\pagestyle{empty}\hfuzz=20cm\raggedright
\begin{document}
""" + "Testo di prova che va a capo più volte nella colonna stretta. " * 12 + r"""
\[ a+b+c+d+e+f+g+h+i+j+k+l+m+n+o+p+q+r+s+t+u+v+w+x+y+z = 0 \]
""" + "Altro testo dopo la formula. " * 8 + r"""
\end{document}
""", encoding="utf-8")
    subprocess.run(["latexmk", "-pdf", "-quiet", "orologio.tex"], cwd=d, check=True, capture_output=True)
    assert pdfstrips.find_exams(tmp_path) == [d / "orologio.pdf"]
    strips, meta = pdfstrips.build_pages(d / "orologio.pdf", VIVOACTIVE5)
    assert meta["title"] == "Prova" and len(strips) >= 2
    for s in strips:
        assert s.normal.width <= VIVOACTIVE5.size and s.normal.height <= meta["strip_h"] + 10
    assert any(s.zoom is not None for s in strips)  # l'equazione lunga ha lo zoom
    keys = [(f"i:{i}", "") for i in range(len(strips))]
    pages = pdfstrips.layout_pages(strips, keys, VIVOACTIVE5)
    assert all(p.startswith("P\nI") for p in pages)
