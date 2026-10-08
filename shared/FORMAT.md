# Formato del bundle (schema 1)

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

- `C` apre un capitolo; le righe `S` che seguono sono le sue sezioni.
- `<pagine iniziali dei pezzi>`: `0;5;11` significa che il pezzo 0 contiene
  le pagine 0–4, il pezzo 1 le pagine 5–10, ecc. Serve per chiedere al telefono
  solo il pezzo della pagina da mostrare.
- Il titolo è testo ricco già diviso in righe (separatore U+E01E);
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

Gli spostamenti di pedici/apici si sommano lungo la pila. Le decorazioni
(5–13) si disegnano alla chiusura, sull'intervallo orizzontale coperto dal
gruppo, rispetto alla baseline del livello che le contiene.
L'implementazione di riferimento è `pipeline/gwnotes/preview.py`.

Palette (indice → colore): 0 testo `#FFFFFF`, 1 titoli `#FFB54A`,
2 attenuato `#9A9A9A`, 3 enfasi `#7FD4FF`, 4 riquadri `#6FE3B4`,
5 link `#7FD4FF`, 6 avvisi `#FF6B6B`.

## Immagine (`i:<hash>`)

Stringa (pezzi concatenati senza separatore):

```
<w>,<h>,2|<base64 dei dati RLE>
```

4 livelli di grigio (0 nero = sfondo, 3 bianco). RLE in ordine raster:
ogni byte è `(valore << 6) | (lunghezza − 1)` con lunghezza 1–64.
Palette dei livelli: `#000000`, `#555555`, `#AAAAAA`, `#FFFFFF`.
La chiave è l'hash del contenuto: immagini identiche sono condivise.
