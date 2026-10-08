"""Scrittura del bundle notes-bundle.zip (formato: shared/FORMAT.md)."""
from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = 2
ZIP_DATE = (2020, 1, 1, 0, 0, 0)


def short_hash(s: str | bytes, n: int = 10) -> str:
    if isinstance(s, str):
        s = s.encode("utf-8")
    return hashlib.sha256(s).hexdigest()[:n]


def chunk_text(parts: list[str], limit: int, sep: str = "\n") -> list[str]:
    """Raggruppa parti consecutive in pezzi di al massimo `limit` byte UTF-8.
    Una parte più grande del limite viene spezzata a livello di carattere."""
    chunks, cur, cur_b = [], [], 0
    sep_b = len(sep.encode("utf-8"))
    for p in parts:
        b = len(p.encode("utf-8"))
        if b > limit:
            if cur:
                chunks.append(sep.join(cur))
                cur, cur_b = [], 0
            chunks.extend(split_bytes(p, limit))
            continue
        if cur and cur_b + sep_b + b > limit:
            chunks.append(sep.join(cur))
            cur, cur_b = [], 0
        cur.append(p)
        cur_b += b + (sep_b if len(cur) > 1 else 0)
    if cur:
        chunks.append(sep.join(cur))
    return chunks


def split_bytes(s: str, limit: int) -> list[str]:
    out, cur, cur_b = [], [], 0
    for ch in s:
        b = len(ch.encode("utf-8"))
        if cur_b + b > limit:
            out.append("".join(cur))
            cur, cur_b = [], 0
        cur.append(ch)
        cur_b += b
    if cur:
        out.append("".join(cur))
    return out


@dataclass
class Resource:
    key: str
    chunks: list[str]
    hash: str = ""

    def __post_init__(self):
        if not self.hash:
            self.hash = short_hash("\x00".join(self.chunks))

    @property
    def bytes(self) -> int:
        return sum(len(c.encode("utf-8")) for c in self.chunks)


@dataclass
class SectionPages:
    id: str
    title_plain: str
    title_lines: list  # [(testo codificato, larghezza px)] titolo completo (voce selezionata)
    pages: list[str]
    chapter: int
    qid: str = ""
    kind: str = "section"
    compact: list = field(default_factory=list)  # [(riga, larghezza)] versione larga e stretta


@dataclass
class BundleBuilder:
    chunk_bytes: int
    resources: dict = field(default_factory=dict)

    def add(self, res: Resource):
        self.resources[res.key] = res
        return res

    def section(self, sp: SectionPages) -> tuple[Resource, list[int]]:
        # pezzi formati da pagine intere; registra la prima pagina di ogni pezzo
        chunks, starts = [], []
        cur, cur_b, first = [], 0, 0
        for i, page in enumerate(sp.pages):
            b = len(page.encode("utf-8"))
            if cur and cur_b + 1 + b > self.chunk_bytes:
                chunks.append("\n".join(cur))
                starts.append(first)
                cur, cur_b = [], 0
            if not cur:
                first = i
            cur.append(page)
            cur_b += b + 1
        if cur:
            chunks.append("\n".join(cur))
            starts.append(first)
        return self.add(Resource("s:" + sp.id, chunks)), starts

    def image(self, encoded: str) -> str:
        key = "i:" + short_hash(encoded, 12)
        if key not in self.resources:
            self.add(Resource(key, split_bytes(encoded, self.chunk_bytes)))
        return key


TITLE_SEP = chr(0xE01E)  # separatore delle righe dei titoli (rich.TITLE_BREAK)


WEB_PACK_BYTES = 32000


def image_keys(pages: list[str]) -> list[str]:
    """Chiavi delle immagini citate dalle righe "I" delle pagine, in ordine."""
    out: list[str] = []
    for page in pages:
        for line in page.split("\n"):
            if line.startswith("I"):
                f = line[1:].split(",", 6)
                for k in f[5:7]:
                    if k and k not in out:
                        out.append(k)
    return out


def build_web_packs(sections: list[tuple[str, str, list[str]]], resources: dict,
                    limit: int = WEB_PACK_BYTES) -> tuple[dict[str, bytes], dict[str, list[str]]]:
    """File per il download via web (GitHub Pages): per ogni sezione, la sezione e
    le immagini che usa per prime, divise in file di al massimo ~`limit` byte di dati.

    sections: [(id sezione, chiave risorsa, chiavi immagini)] in ordine di indice.
    Ritorna ({nome file: JSON}, {id sezione: [nomi file]}). Il nome è l'hash del
    contenuto: un file che non cambia nome non va riscaricato."""
    files: dict[str, bytes] = {}
    by_section: dict[str, list[str]] = {}
    seen: set[str] = set()

    def flush(items):
        body = json.dumps({"r": [[k, resources[k].hash, resources[k].chunks] for k in items]},
                          ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        name = "p" + short_hash("|".join(f"{k}:{resources[k].hash}" for k in items), 12)
        files[name] = body
        return name

    for sid, skey, imgs in sections:
        names, cur, cur_b = [], [], 0
        for k in [skey] + imgs:
            if k in seen or k not in resources:
                continue
            seen.add(k)
            b = resources[k].bytes
            if cur and cur_b + b > limit:
                names.append(flush(cur))
                cur, cur_b = [], 0
            cur.append(k)
            cur_b += b
        if cur:
            names.append(flush(cur))
        by_section[sid] = names
    return files, by_section


def build_index(title: str, font_id: str, content_version: str, chapters: list,
                web_base: str = "", web_packs: dict[str, list[str]] | None = None) -> list[str]:
    """chapters: [(title_lines, header_line, [(SectionPages, Resource, starts)])]

    Le righe "H" e "Q" (titoli compatti per scorrere l'elenco) e "W"/"F" (download
    via web) sono aggiunte compatibili: le versioni dell'app che non le conoscono
    le ignorano."""
    lines = [f"V|{SCHEMA}|{content_version}|{font_id}|{title}"]
    if web_base and web_packs:
        lines.append(f"W|{web_base}")
    for title_lines, header, secs in chapters:
        ws = ";".join(str(w) for _, w in title_lines)
        lines.append(f"C|{len(secs)}|{ws}|" + TITLE_SEP.join(t for t, _ in title_lines))
        if header:
            lines.append(f"H|{header[1]}|{header[0]}")
        for sp, res, starts in secs:
            ws = ";".join(str(w) for _, w in sp.title_lines)
            st = ";".join(str(s) for s in starts)
            lines.append(f"S|{sp.id}|{res.hash}|{len(sp.pages)}|{st}|{ws}|"
                         + TITLE_SEP.join(t for t, _ in sp.title_lines))
            if sp.compact:
                cw = ";".join(str(w) for _, w in sp.compact)
                lines.append(f"Q|{sp.id}|{sp.kind}|{sp.qid}|{cw}|" + TITLE_SEP.join(t for t, _ in sp.compact))
            if web_base and web_packs and web_packs.get(sp.id):
                lines.append(f"F|{sp.id}|" + ";".join(web_packs[sp.id]))
    return lines


def write_zip(out: Path, manifest: dict, resources: dict, extra: dict[str, bytes] | None = None):
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        def put(name, data: bytes):
            zi = zipfile.ZipInfo(name, ZIP_DATE)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, data)

        put("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True).encode("utf-8"))
        for key in sorted(resources):
            r = resources[key]
            put(manifest["resources"][key]["file"],
                json.dumps({"key": key, "hash": r.hash, "chunks": r.chunks}, ensure_ascii=False).encode("utf-8"))
        for name, data in sorted((extra or {}).items()):
            put(name, data)


def res_file(key: str) -> str:
    return "res/" + key.replace(":", "_") + ".json"
