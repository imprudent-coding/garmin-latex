"""Genera i font bitmap (formato AngelCode BMFont) usati dall'app dell'orologio.

I file generati sono il "contratto" tra pipeline e app Garmin:
  shared/font/generated/<nome>.fnt + <nome>_0.png   -> compilati nell'app (resourcePath)
  shared/font/generated/fonts.xml                     -> dichiarazione risorse Connect IQ
  shared/font/generated/metrics.json                  -> metriche usate dalla pipeline per impaginare
  garmin/source/FontInfo.mc                           -> costanti per l'app (id font, baseline)

Uso:  cd pipeline && python -m gwnotes.fontgen
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .paths import REPO_ROOT

FONT_DIR = REPO_ROOT / "shared" / "font"
OUT_DIR = FONT_DIR / "generated"
MC_OUT = REPO_ROOT / "garmin" / "source" / "FontInfo.mc"
PAGE_W = 512
PAD = 1


def read_charset(path: Path = FONT_DIR / "charset.txt") -> str:
    chars = [" "]
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        _, _, s = line.partition("\t")
        for c in s.strip():
            if c not in chars and c != " ":
                chars.append(c)
    return "".join(chars)


def _render_font(name: str, ttf: Path, size: int, charset: str):
    font = ImageFont.truetype(str(ttf), size)
    ascent, descent = font.getmetrics()
    glyphs = []
    for ch in charset:
        adv = int(round(font.getlength(ch)))
        l, t, r, b = font.getbbox(ch, anchor="ls")
        w, h = max(0, r - l), max(0, b - t)
        if w == 0 or h == 0:
            w = h = 0
        img = None
        if w > 0 and h > 0:
            img = Image.new("L", (w, h), 0)
            ImageDraw.Draw(img).text((-l, -t), ch, fill=255, font=font, anchor="ls")
        glyphs.append({"ch": ch, "adv": adv, "xoff": l, "yoff": ascent + t, "w": w, "h": h, "img": img})
    # shelf packing
    order = sorted((g for g in glyphs if g["img"] is not None), key=lambda g: -g["h"])
    x = y = shelf_h = 0
    for g in order:
        if x + g["w"] + PAD > PAGE_W:
            x, y, shelf_h = 0, y + shelf_h + PAD, 0
        g["x"], g["y"] = x, y
        x += g["w"] + PAD
        shelf_h = max(shelf_h, g["h"])
    total_h = y + shelf_h
    page_h = 64
    while page_h < total_h:
        page_h *= 2
    page = Image.new("L", (PAGE_W, page_h), 0)
    for g in order:
        page.paste(g["img"], (g["x"], g["y"]))
    for g in glyphs:
        g.setdefault("x", 0)
        g.setdefault("y", 0)
    return font, ascent, descent, glyphs, page


def _write_fnt(path: Path, name: str, size: int, ascent: int, descent: int, glyphs, page_file: str, page_h: int):
    lines = [
        f'info face="{name}" size=-{size} bold=0 italic=0 charset="" unicode=1 stretchH=100 smooth=1 aa=1 '
        f"padding=0,0,0,0 spacing={PAD},{PAD} outline=0",
        f"common lineHeight={ascent + descent} base={ascent} scaleW={PAGE_W} scaleH={page_h} pages=1 packed=0 "
        f"alphaChnl=1 redChnl=0 greenChnl=0 blueChnl=0",
        f'page id=0 file="{page_file}"',
        f"chars count={len(glyphs)}",
    ]
    for g in glyphs:
        lines.append(
            f"char id={ord(g['ch'])} x={g['x']} y={g['y']} width={g['w']} height={g['h']} "
            f"xoffset={g['xoff']} yoffset={g['yoff']} xadvance={g['adv']} page=0 chnl=15"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate() -> dict:
    cfg = json.loads((FONT_DIR / "fonts.json").read_text(encoding="utf-8"))
    charset = read_charset()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    metrics = {"charset": charset, "fonts": {}}
    for name, fc in cfg["fonts"].items():
        _, ascent, descent, glyphs, page = _render_font(name, FONT_DIR / fc["ttf"], fc["size"], charset)
        page_file = f"{name}_0.png"
        page.save(OUT_DIR / page_file, optimize=True)
        _write_fnt(OUT_DIR / f"{name}.fnt", name, fc["size"], ascent, descent, glyphs, page_file, page.height)
        metrics["fonts"][name] = {
            "size": fc["size"],
            "ascent": ascent,
            "descent": descent,
            "lineHeight": ascent + descent,
            # cp -> [xadvance, top (dal top della riga), altezza, xoffset, larghezza]
            "glyphs": {str(ord(g["ch"])): [g["adv"], g["yoff"], g["h"], g["xoff"], g["w"]] for g in glyphs},
        }
    blob = json.dumps(metrics, sort_keys=True, ensure_ascii=False).encode("utf-8")
    font_id = hashlib.sha1(blob).hexdigest()[:10]
    metrics["fontId"] = font_id
    (OUT_DIR / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    aa = "true" if cfg.get("antialias", True) else "false"
    xml = ["<!-- Generato da pipeline/gwnotes/fontgen.py: non modificare a mano. -->", "<resources>", "    <fonts>"]
    for name in cfg["fonts"]:
        xml.append(f'        <font id="Font_{name}" filename="{name}.fnt" antialias="{aa}" />')
    xml += ["    </fonts>", "</resources>", ""]
    (OUT_DIR / "fonts.xml").write_text("\n".join(xml), encoding="utf-8")

    mc = [
        "// Generato da pipeline/gwnotes/fontgen.py: non modificare a mano.",
        "module FontInfo {",
        f'    const ID = "{font_id}";',
    ]
    for name, m in metrics["fonts"].items():
        mc.append(f"    const {name.upper()}_ASCENT = {m['ascent']};")
        mc.append(f"    const {name.upper()}_LINE = {m['lineHeight']};")
    mc.append("}")
    MC_OUT.parent.mkdir(parents=True, exist_ok=True)
    MC_OUT.write_text("\n".join(mc) + "\n", encoding="utf-8")
    return metrics


def main() -> int:
    m = generate()
    print(f"fontId={m['fontId']} glifi={len(m['charset'])} -> {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
