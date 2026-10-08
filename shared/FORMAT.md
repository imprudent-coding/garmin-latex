# Formato del bundle (schema 2)

Il bundle è prodotto dalla pipeline (`pipeline/`), pubblicato come asset
`notes-bundle.zip` nelle Release GitHub (tag `notes-*`), scaricato dall'app
Android e inviato all'orologio a pezzi.

Ogni cambiamento incompatibile del formato **deve** incrementare `schema`.
Le app rifiutano un bundle con schema maggiore di quello che conoscono e
mostrano "aggiorna l'app".

## Struttura dello zip

```
notes-bundle.zip
├── manifest.json
└── res/
    ├── idx.json          indice (chiave "idx")
    ├── s_<id>.json       una sezione (chiave "s:<id>")
    └── i_<hash>.json     un'immagine (chiave "i:<hash>")
```

Ogni file `res/*.json` è `{"key": "...", "hash": "...", "chunks": ["...", ...]}`.
I **pezzi** (chunk) sono stringhe UTF-8 di al massimo `chunkBytes` byte
(default 1800): sono l'unità di trasmissione Bluetooth e di salvataggio
nell'`Application.Storage` dell'orologio.

## manifest.json

| campo | significato |
|---|---|
| `schema` | versione del formato (intero) |
| `contentVersion` | `AAAAMMGG.hhmmss-<hash>`: cambia a ogni modifica dei contenuti |
| `contentHash` | hash di tutte le risorse: uguale ⇒ niente da sincronizzare |
| `generatedAt`, `sourceCommit` | tracciabilità |
| `title` | titolo degli appunti |
| `fontId` | id dei font con cui è stata fatta l'impaginazione (vedi sotto) |
| `chunkBytes` | dimensione massima dei pezzi |
| `profile` | geometria del dispositivo usata per impaginare (vivoactive5) |
| `index` | `{key: "idx", hash, chunks}` |
| `toc` | indice leggibile (per l'app Android): capitoli → sezioni `{id, title, pages, key, hash}` |
| `resources` | `chiave → {hash, chunks, bytes, file}` |

`fontId` deve coincidere con `FontInfo.ID` compilato nell'app dell'orologio;
se non coincide l'orologio avvisa che l'app va aggiornata (il testo potrebbe
essere impaginato con metriche diverse).

## Indice (`idx`)

Le righe dell'indice (pezzi concatenati con `\n`) sono:

```
V|<schema>|<contentVersion>|<fontId>|<titolo>
C|<n. sezioni>|<larghezze>|<titolo>
S|<id>|<hash>|<n. pagine>|<pagine iniziali dei pezzi>|<larghezze>|<titolo>
```

```
H|<larghezza>|<intestazione compatta del gruppo>
Q|<id>|<tipo>|<id domanda>|<largh. larga>;<largh. stretta>|<riga larga>U+E01E<riga stretta>
W|<indirizzo dei file web, con / finale>
F|<id>|<file>;<file>…
```

- `C` apre un capitolo; le righe `S` che seguono sono le sue sezioni.
- `H` (facoltativa, subito dopo `C`) è l'intestazione del gruppo nell'elenco
  compatto; manca se il gruppo ha una sola sezione.
- `Q` (facoltativa, subito dopo la sua `S`) descrive la voce nell'elenco compatto:
  `tipo` è `question` (con `id domanda`, es. `A1`, preso dal `\def\@currentlabel`
  della macro di sezionamento o dall'etichetta nel `.aux`), `intro` (testo prima
  della prima sezione del gruppo) o `section`. Le due righe sono il titolo su una
  riga nel font piccolo, troncato con «…» a 290 px (vicino al centro) e a 230 px
  (verso i bordi del cerchio).
- `W` (facoltativa, subito dopo `V`) e `F` (facoltativa, dopo la sua `S`):
  file web della sezione, vedi «File web» sotto.
- Le app ignorano le righe di tipo sconosciuto: aggiungere tipi di riga non
  richiede di cambiare `schema`.
- `<pagine iniziali dei pezzi>`: `0;5;11` significa che il pezzo 0 contiene
  le pagine 0–4, il pezzo 1 le pagine 5–10, ecc. Serve per chiedere al telefono
  solo il pezzo della pagina da mostrare.
- Il titolo è testo ricco già diviso in righe (separatore U+E01E, al massimo 3);
  `<larghezze>` sono le larghezze in pixel di ciascuna riga (`;`), per centrarle.
- Il titolo è l'ultimo campo: può contenere `|`.

## Sezione (`s:<id>`)

I pezzi, concatenati con `\n`, sono una sequenza di pagine. Ogni pagina inizia
con una riga `P` ed è seguita da elementi già posizionati (coordinate in pixel
dello schermo 390×390):

```
P
T<x>,<y>,<testo ricco>                         testo; y = baseline
I<x>,<y>,<w>,<h>,<sy>,<chiave>,<chiave zoom>   righe sy..sy+h dell'immagine, angolo in alto a sinistra in (x,y)
R<x>,<y>,<w>,<h>,<colore>                      rettangolo pieno (barre dei riquadri)
```

Il testo può contenere virgole: solo le prime due separano i campi.
`<chiave zoom>` è vuota se l'immagine non ha una versione ingrandita.

## Testo ricco

Unicode + codici di stile nell'area privata. Ogni **apertura** è il carattere
`U+E000 + codice` seguito da un carattere parametro `chr(0x100 + valore)`;
la **chiusura** è `U+E00F` e chiude l'ultimo stile aperto (pila).

| codice | stile | parametro |
|---|---|---|
| 1 | grassetto (font `bold`) | – |
| 2 | colore | indice nella palette |
| 3 | pedice (font `small`) | spostamento in basso (px) |
| 4 | apice (font `small`) | spostamento in alto (px) |
| 5 | sottolineato (vettore) | distanza sotto la baseline |
| 6 | doppio sottolineato (matrice) | distanza sotto la baseline |
| 7 | accento circonflesso (versore) | altezza sopra la baseline |
| 8 | punto (derivata) | altezza sopra la baseline |
| 9 | due punti | altezza sopra la baseline |
| 10 | tilde | altezza sopra la baseline |
| 11 | barra sopra | altezza sopra la baseline |
| 12 | freccia sopra | altezza sopra la baseline |
| 13 | freccia sotto (diade) | distanza sotto la baseline |
| 16 | spazio vuoto (per un'immagine inline), **senza chiusura** | larghezza (px) |
| 17 | testo nel font `small` (righe compatte dell'elenco) | – |

Gli spostamenti di pedici/apici si sommano lungo la pila. Le decorazioni
(5–13) si disegnano alla chiusura, sull'intervallo orizzontale coperto dal
gruppo, rispetto alla baseline del livello che le contiene.
L'implementazione di riferimento è `pipeline/gwnotes/preview.py`.

Palette (indice → colore): 0 testo `#FFFFFF`, 1 titoli `#FFB54A`,
2 attenuato `#9A9A9A`, 3 enfasi `#7FD4FF`, 4 riquadri `#6FE3B4`,
5 link `#7FD4FF`, 6 avvisi `#FF6B6B`.

## File web (GitHub Pages)

Oltre al bundle, la pipeline scrive `web/w/<file>.json`, pubblicati dal workflow
`notes` su GitHub Pages. Per ogni sezione, in ordine di indice: la sezione e le
immagini che usa **per prime** (un'immagine già in un file precedente non si
ripete), divise in file con al massimo ~32 KB di dati.

```json
{"r": [["s:q-a1", "<hash>", ["<pezzo 0>", "<pezzo 1>"]], ["i:3fa…", "<hash>", ["…"]]]}
```

Ogni voce è `[chiave, hash, pezzi]`, con gli stessi pezzi del bundle. Il nome del
file è un hash del contenuto (`p` + 12 caratteri esadecimali): un file con lo
stesso nome non va riscaricato. L'orologio li scarica con `makeWebRequest`
(JSON), che passa da Garmin Connect ma è molto più veloce dei messaggi tra app;
per ogni file che non arriva usa l'app del telefono (shared/PROTOCOL.md).

## Immagine (`i:<hash>`)

Stringa (pezzi concatenati senza separatore):

```
<w>,<h>,2,<n>|<base64 di LZ(RLE)>      schema 2
<w>,<h>,2|<base64 dei dati RLE>        schema 1
```

4 livelli di grigio (0 nero = sfondo, 3 bianco). RLE in ordine raster:
ogni byte è `(valore << 6) | (lunghezza − 1)` con lunghezza 1–64.

Dallo schema 2 i byte RLE sono compressi **senza perdita** con un LZ in stile
LZ4 (`pipeline/gwnotes/lz.py`); `<n>` è il numero di byte RLE dopo la
decompressione. Sulle immagini degli appunti riduce i dati del ~30%. La
decompressione è solo copia di byte, per restare leggera sull'orologio.
Sequenze:

| campo | contenuto |
|---|---|
| token | `(letterali << 4) \| (match − 4)`, 4 bit ciascuno |
| estensione letterali | se letterali = 15: byte da sommare, `255` = continua |
| letterali | byte copiati così come sono |
| offset | 2 byte little-endian: distanza all'indietro (1–65535) |
| estensione match | se match = 15: come sopra (match ≤ 4096) |

L'ultima sequenza ha solo i letterali. Implementazioni: `pipeline/gwnotes/lz.py`
(compressione e riferimento), `garmin/source/ImageCache.mc` (a passi, per il
watchdog), `android/…/render/Lz.kt` (anteprima).
Palette dei livelli: `#000000`, `#555555`, `#AAAAAA`, `#FFFFFF`.
La chiave è l'hash del contenuto: immagini identiche sono condivise.
