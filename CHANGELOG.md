# Versioni

Le app si rilasciano con i tag `garmin-vX.Y.Z` e `android-vX.Y.Z` (vedi README,
«Prima compilazione e Release»). Le Release degli appunti (`notes-…`) sono
automatiche a ogni push su `main`.

## Orologio 1.1.0

- Download in sottofondo dai file web su GitHub Pages (~10 KB/s misurati),
  con il telefono come riserva per ogni file che non arriva: la prima
  sincronizzazione completa passa da ~50 a pochi minuti.
- Accanto a «Sezioni …/…» compare «web» quando i file arrivano dal web.
- Appunti: il workflow `notes` pubblica anche i file web (GitHub Pages, da
  attivare una volta). Formato del bundle invariato (schema 2): le righe nuove
  dell'indice sono ignorate dalle versioni precedenti.

## 1.0.1

- Orologio: il timeout di una richiesta con più pezzi cresce con i pezzi (+5 s
  ciascuno) e i nuovi tentativi chiedono un pezzo solo. Prima una risposta da
  ~7 KB poteva scadere e veniva rispedita, raddoppiando il traffico.
- Orologio: se il telefono non risponde a download incompleto, nuovo tentativo
  ogni 30 s (prima il download restava fermo).
- Android: una richiesta ripetuta mentre la risposta è ancora in invio viene
  ignorata; la scheda *Orologio* mostra la velocità misurata degli invii.
- Orologio: voce di menu *Test velocità* (richieste web verso GitHub tramite il
  telefono), per confrontarle con i messaggi app↔telefono (~0,4 KB/s misurati).

## 1.0.0 — prima versione stabile (orologio e Android)

Bundle schema 2. Comprende le versioni 0.x qui sotto e in più, sull'orologio:

- Corretti due crash della sincronizzazione dopo il passaggio allo schema 2:
  - watchdog: i metadati della cache si salvavano a ogni pezzo e a ogni eliminazione;
  - eccezione quando una richiesta multipla riguardava un solo pezzo.
- I metadati si salvano al più una volta al secondo e alla chiusura; le risposte
  con più pezzi si salvano un pezzo per passo.

## Orologio 0.4.0 · Android 0.3.0 — schema 2

- Immagini compresse senza perdita (LZ sopra l'RLE): −31% di dati sulle immagini.
- Più pezzi per messaggio (fino a 8, ~7 KB): circa un terzo degli scambi con il telefono.
- Richiede entrambe le app aggiornate.

## Orologio 0.3.1

- Il tocco sulle domande apriva l'orologio: ora l'orologio parte solo dal pulsante fisico.
- Menu raggiungibile con un tocco (tre puntini in alto nell'elenco, numero di pagina in lettura).

## Orologio 0.3.0 · Android 0.2.0

- Tutti gli appunti scaricati in sottofondo nella memoria dell'orologio (cache da 6 MB).
- Avanzamento del download sull'orologio e nell'app Android.
- Scorrimento automatico delle pagine (5–60 s) e schermata orologio sul pulsante in alto.

## Orologio 0.2.0

- Elenco veloce di tutte le domande, raggruppate per capitolo.

## Orologio 0.1.0 · Android 0.1.0 — prima alfa

- Pipeline LaTeX → bundle, app Android companion, app Connect IQ per vívoactive 5.
