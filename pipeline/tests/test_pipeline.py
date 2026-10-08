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

from gwnotes import bundle, eqsplit, images, lz  # noqa: E402
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
                        "--preview", "2"], cwd=ROOT, capture_output=True, text=True)
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
    assert (out / "preview").exists() and (out / "notes.pdf").exists()
    assert (out / "preview" / "_elenco.png").exists()
    idx = "\n".join(json.loads(z.read(m["resources"]["idx"]["file"]))["chunks"])
    q = [l.split("|") for l in idx.split("\n") if l.startswith("Q|")]
    assert len(q) == 2 and all(len(f) == 6 for f in q)


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
