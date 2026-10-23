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


@dataclass
class RawChapter:
    """Capitolo copiato dall'indice di un bundle precedente (build incrementale).

    head: righe C/H/L; sections: (id, righe S/Q) per ogni sezione. Le righe F (file
    web) si rigenerano: dipendono da tutte le sezioni del nuovo bundle."""
    head: list[str]
    sections: list[tuple[str, list[str]]]
    resources: dict = field(default_factory=dict, repr=False)


def index_sections(chapter) -> list[tuple[str, str, list[str]]]:
    """(id sezione, chiave risorsa, chiavi immagini) di un capitolo di build_index."""
    if isinstance(chapter, RawChapter):
        return [(sid, "s:" + sid, image_keys(["\n".join(chapter.resources["s:" + sid].chunks)]))
                for sid, _ in chapter.sections]
    return [(sp.id, res.key, image_keys(sp.pages)) for sp, res, _ in chapter[2]]


class PrevBundle:
    """Bundle di una Release precedente, per le build incrementali."""

    def __init__(self, manifest: dict, resources: dict[str, Resource]):
        self.manifest = manifest
        self.resources = resources
        self.exams: dict = manifest.get("exams") or {}
        idx = "\n".join(resources["idx"].chunks) if "idx" in resources else ""
        self.index_lines = idx.split("\n") if idx else []
        v = self.index_lines[0].split("|", 4) if self.index_lines else []
        self.title = v[4] if len(v) == 5 else manifest.get("title", "")

    @classmethod
    def load(cls, path: Path) -> "PrevBundle | None":
        if not path.exists():
            return None
        try:
            with zipfile.ZipFile(path) as z:
                manifest = json.loads(z.read("manifest.json"))
                res = {}
                for name in z.namelist():
                    if name.startswith("res/") and name.endswith(".json"):
                        d = json.loads(z.read(name))
                        res[d["key"]] = Resource(d["key"], d["chunks"], d["hash"])
        except (zipfile.BadZipFile, KeyError, ValueError) as e:
            print(f"Bundle precedente illeggibile ({e}): ignorato")
            return None
        return cls(manifest, res)

    def compatible(self, font_id: str, chunk_bytes: int) -> bool:
        m = self.manifest
        return m.get("schema") == SCHEMA and m.get("fontId") == font_id and m.get("chunkBytes") == chunk_bytes

    def has_section(self, sid: str) -> bool:
        return "s:" + sid in self.resources

    def section_pages(self, sid: str) -> list[str]:
        """Pagine di una sezione (ognuna inizia con la riga "P")."""
        pages: list[list[str]] = []
        for line in "\n".join(self.resources["s:" + sid].chunks).split("\n"):
            if line == "P":
                pages.append([])
            pages[-1].append(line)
        return ["\n".join(p) for p in pages]

    def notes_chapters(self) -> list[RawChapter]:
        """Capitoli degli appunti (senza la libreria "esami"), righe pronte per build_index."""
        out: list[RawChapter] = []
        cur = None
        for line in self.index_lines[1:]:
            t = line[:1]
            if t == "C":
                cur = RawChapter([line], [], self.resources)
                out.append(cur)
            elif cur is None or t in ("V", "W", "F"):
                continue
            elif t in ("H", "L"):
                cur.head.append(line)
            elif t == "S":
                cur.sections.append((line.split("|", 2)[1], [line]))
            elif cur.sections:
                cur.sections[-1][1].append(line)  # Q e righe future legate alla sezione
        return [c for c in out if "L|esami" not in c.head]


def build_index(title: str, font_id: str, content_version: str, chapters: list,
                web_base: str = "", web_packs: dict[str, list[str]] | None = None) -> list[str]:
    """chapters: [(title_lines, header_line, [(SectionPages, Resource, starts)][, libreria])]

    La libreria (es. "esami") diventa la riga "L" del capitolo; senza, il capitolo
    fa parte degli appunti.

    Le righe "H" e "Q" (titoli compatti per scorrere l'elenco) e "W"/"F" (download
    via web) sono aggiunte compatibili: le versioni dell'app che non le conoscono
    le ignorano."""
    lines = [f"V|{SCHEMA}|{content_version}|{font_id}|{title}"]
    if web_base and web_packs:
        lines.append(f"W|{web_base}")
    for chapter in chapters:
        if isinstance(chapter, RawChapter):
            lines += chapter.head
            for sid, rows in chapter.sections:
                lines += rows
                if web_base and web_packs and web_packs.get(sid):
                    lines.append(f"F|{sid}|" + ";".join(web_packs[sid]))
            continue
        title_lines, header, secs, *lib = chapter
        ws = ";".join(str(w) for _, w in title_lines)
        lines.append(f"C|{len(secs)}|{ws}|" + TITLE_SEP.join(t for t, _ in title_lines))
        if header:
            lines.append(f"H|{header[1]}|{header[0]}")
        if lib and lib[0]:
            lines.append(f"L|{lib[0]}")
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
