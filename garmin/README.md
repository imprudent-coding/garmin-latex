# App Connect IQ (vívoactive 5)

Watch-app in Monkey C che mostra gli appunti già impaginati dalla pipeline.

```bash
monkeyc -f monkey.jungle -d vivoactive5 -o bin/appunti.prg -y developer_key.der   # serve il device vivoactive5 nell'SDK Manager
connectiq & monkeydo bin/appunti.prg vivoactive5
```

## Struttura

| File | Ruolo |
|---|---|
| `NotesApp.mc` | applicazione: avvio, indice, sincronizzazione, posizione di lettura |
| `Sync.mc` | protocollo con il telefono ([`../shared/PROTOCOL.md`](../shared/PROTOCOL.md)): un messaggio in volo, timeout 10 s, 3 tentativi |
| `Store.mc` | cache in `Application.Storage`: un valore per pezzo (~1,8 KB), metadati divisi in 16 valori, LRU, budget 6 MB, recupero se lo spazio finisce |
| `Prefetch.mc` | scaricamento in sottofondo di tutte le sezioni e immagini quando il collegamento è libero; avanzamento sull'orologio e sul telefono |
| `Index.mc` | indice: capitoli, sezioni, pezzo che contiene ogni pagina |
| `QuestionList.mc` | elenco unico delle domande raggruppate per capitolo: righe compatte, voce selezionata espansa al centro, trascinamento veloce, salto di gruppo con swipe laterale |
| `ReaderView.mc` | lettura: carica solo il pezzo della pagina corrente, precarica il successivo |
| `RichText.mc` | disegno del testo ricco (pedici, apici, vettori, accenti) con i font custom |
| `ImageCache.mc` | immagini: RLE a 2 bit → `BufferedBitmap` a palette, decodifica a blocchi (watchdog), al massimo 4 in memoria |
| `ZoomView.mc` | versione ingrandita con swipe/trascinamento |
| `ClockView.mc` | schermata orologio sul pulsante in alto; si chiude con una pressione prolungata |
| `Ticker.mc` | un solo `Timer` per tutta l'app (Connect IQ permette di default 3 timer attivi): sincronizzazione, immagini, prefetch, scorrimento automatico, orologio |
| `FontInfo.mc` | **generato** da `pipeline/gwnotes/fontgen.py` (id e metriche dei font) |

I font sono in `../shared/font/generated`, aggiunta al `resourcePath` del jungle:
sono gli stessi file che la pipeline usa per impaginare. Se cambiano, la pipeline
scrive un nuovo `fontId` nel bundle e l'orologio avvisa che l'app va aggiornata.

## Limiti del dispositivo

Dalla [Device Reference](https://developer.garmin.com/connect-iq/device-reference/vivoactive5/):
watch-app 786.432 byte, glance 65.536, background 65.536; schermo 390×390, 65.536
colori, touch. La CI stampa nel riepilogo del job i valori letti dai device file
(`compiler.json`).

Storage: il device file `simulator.json` del vívoactive 5 indica
`appStorageCapacity` = 10.485.760 byte (10 MB per app); il pool grafico
(`graphicsResourcePoolSize`) è di 2 MB. La guida *Persisting Data* parla di
128 KB totali e 8 KB per valore: il totale non vale per questo dispositivo, il
limite per valore lo rispettiamo comunque (pezzi da 1,8 KB, metadati divisi in
16 valori). Budget della cache: 6 MB; gli appunti interi sono ~1,6 MB.

## Memoria (da misurare)

L'app scrive righe `[mem] …` nella console del simulatore nei punti critici:
- avvio;
- dopo il caricamento dei font;
- indice in cache;
- ogni pagina;
- prima e dopo ogni immagine.

Dal menu, *Mostra memoria* aggiunge un indicatore sullo schermo. Le voci più
pesanti previste:
- i tre font antialiasing (349 glifi ciascuno);
- le bitmap delle immagini (≤ 4; zoom ≤ 700×700 a 2 bit).

Se la memoria non basta: `antialias: false` in `shared/font/fonts.json` (font a
1 bit) oppure `zoom_max` più piccolo in `pipeline/gwnotes/profile.py`.

## Tipo di app

Watch-app. Una glance (ultima sezione letta e stato della sincronizzazione)
sarebbe possibile entro i 64 KB, ma non è inclusa. Un widget non serve: l'app si
apre dal menu *Attività e app*.
