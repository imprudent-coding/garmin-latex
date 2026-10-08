# Pipeline di conversione (LaTeX → bundle per l'orologio)

```bash
cd pipeline
pip install -r requirements.txt
python -m pytest -q tests                      # test (quelli end-to-end richiedono TeX Live e pandoc)
python -m gwnotes build --out ../dist           # PDF, notes-bundle.zip, anteprime, report
python -m gwnotes build --preview-sections q-a1 q-b2   # anteprime solo di alcune sezioni (regex sugli id)
python -m gwnotes.fontgen                       # rigenera i font dopo aver cambiato shared/font/
```

Richiede TeX Live (`latexmk`, `pdflatex`, pacchetti del documento), pandoc 3.x e
poppler (`pdftoppm`). La CI usa i pacchetti di Ubuntu 24.04: TeX Live 2023 e
pandoc 3.1.3.

## Fasi

| Modulo | Cosa fa |
|---|---|
| `texsource.py` | trova il documento principale, segue `\input`/`\include`, legge le definizioni (`\newcommand`, `\def`, `\newtcolorbox`, ...) e riconosce le macro di sezionamento |
| `latexbuild.py` | compila con `latexmk`; in caso di errore estrae file, riga e messaggio; legge le etichette dal `.aux` (per `\ref`/`\pageref`) |
| `prepare.py` | trasforma il sorgente per pandoc: sezionamento → marcatori, `longtable`/`tabularx` → `tabular`, ambienti grafici → segnaposto |
| `docmodel.py` | AST di pandoc → capitoli/sezioni/blocchi; testo ricco; elenchi, riquadri, tabelle in righe di testo |
| `mathconv.py` | matematica semplice → Unicode + stili; il resto solleva `Unconvertible` e diventa un'immagine |
| `render.py`, `eqsplit.py`, `assets.py` | compilazione delle formule (un solo documento `preview` con il preambolo originale), spezzamento delle equazioni larghe, figure, versioni zoom |
| `images.py` | 4 livelli di grigio, bianco su nero, RLE a 2 bit + base64 |
| `layout.py`, `profile.py` | impaginazione per il cerchio 390×390 con le metriche dei font dell'app |
| `bundle.py` | pezzi ≤ `chunk_bytes`, hash, `manifest.json`, zip deterministico |
| `preview.py` | PNG delle pagine come le disegna l'orologio (implementazione di riferimento del formato) |

Formato di uscita: [`../shared/FORMAT.md`](../shared/FORMAT.md).

## Regole (`rules.yaml`)

Il file contiene solo eccezioni: la pipeline funziona anche con il file vuoto.
Chiavi disponibili: `macros`, `structure`, `ignore_structure`, `image_envs`,
`image_macros`, `expand_envs`, `math_symbols`, `box_titles`, `front_title`,
`chunk_bytes`, `math_px_per_em`, `figure_zoom_dpi` (vedi `gwnotes/rules.py`).
Esempi nel README principale.

## Quando fallisce

- **Errore LaTeX vero**: codice di uscita 1 e messaggio con file e riga. È
  l'unico caso che blocca la build.
- **Una formula che non compila da sola** (per esempio usa una macro definita nel
  corpo del documento): avviso nel report; viene mostrata come testo TeX colorato.
- **Una figura illeggibile o mancante**: avviso nel report.
