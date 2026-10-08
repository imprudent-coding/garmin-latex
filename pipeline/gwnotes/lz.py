"""Compressione LZ senza perdita per i dati RLE delle immagini (shared/FORMAT.md).

Formato in stile LZ4, scelto perché la decodifica sull'orologio è solo copia di
byte: niente tabelle di Huffman (deflate sarebbe più compatto ma troppo pesante
in Monkey C). Una sequenza è:

    token            (lunghezza letterali << 4) | (lunghezza match - 4), 4 bit ciascuno
    [estensione]     se letterali = 15: byte da sommare, 255 = continua
    letterali
    offset           2 byte little-endian (distanza all'indietro, 1..65535)
    [estensione]     se match = 15: come sopra

L'ultima sequenza ha solo i letterali (nessun offset).
"""
from __future__ import annotations

MIN_MATCH = 4
MAX_OFFSET = 65535
MAX_MATCH = 4096      # limita il lavoro di un singolo passo di decodifica sull'orologio
CANDIDATES = 16


def _ext(out: bytearray, n: int) -> None:
    while n >= 255:
        out.append(255)
        n -= 255
    out.append(n)


def _emit(out: bytearray, lits: bytes, mlen: int, off: int) -> None:
    ll = len(lits)
    ml = mlen - MIN_MATCH if mlen else 0
    out.append((min(ll, 15) << 4) | min(ml, 15))
    if ll >= 15:
        _ext(out, ll - 15)
    out.extend(lits)
    if mlen:
        out.extend(off.to_bytes(2, "little"))
        if ml >= 15:
            _ext(out, ml - 15)


def compress(data: bytes) -> bytes:
    out = bytearray()
    n = len(data)
    table: dict[bytes, list[int]] = {}
    i = lit_start = 0
    while i + MIN_MATCH <= n:
        key = data[i:i + MIN_MATCH]
        best = off = 0
        for c in reversed(table.get(key, [])[-CANDIDATES:]):
            if i - c > MAX_OFFSET:
                break
            ln = 0
            while i + ln < n and ln < MAX_MATCH and data[c + ln] == data[i + ln]:
                ln += 1
            if ln > best:
                best, off = ln, i - c
        table.setdefault(key, []).append(i)
        if best >= MIN_MATCH:
            _emit(out, data[lit_start:i], best, off)
            for j in range(i + 1, min(i + best, n - MIN_MATCH + 1)):
                table.setdefault(data[j:j + MIN_MATCH], []).append(j)
            i += best
            lit_start = i
        else:
            i += 1
    _emit(out, data[lit_start:], 0, 0)
    return bytes(out)


def decompress(c: bytes, size: int | None = None) -> bytes:
    out = bytearray()
    i, n = 0, len(c)
    while i < n:
        tok = c[i]
        i += 1
        ll = tok >> 4
        if ll == 15:
            while True:
                b = c[i]
                i += 1
                ll += b
                if b != 255:
                    break
        out += c[i:i + ll]
        i += ll
        if i >= n:
            break
        off = c[i] | (c[i + 1] << 8)
        i += 2
        ml = tok & 15
        if ml == 15:
            while True:
                b = c[i]
                i += 1
                ml += b
                if b != 255:
                    break
        ml += MIN_MATCH
        if off == 0 or off > len(out):
            raise ValueError("LZ: offset non valido")
        s = len(out) - off
        for k in range(ml):
            out.append(out[s + k])
    if size is not None and len(out) != size:
        raise ValueError(f"LZ: attesi {size} byte, trovati {len(out)}")
    return bytes(out)
