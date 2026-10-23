# Versioni

Le app si rilasciano con i tag `garmin-vX.Y.Z` e `android-vX.Y.Z` (vedi README,
«Prima compilazione e Release»). Le Release degli appunti (`notes-…`) sono
automatiche a ogni push su `main`.

## Orologio 1.6.0

- Simulazioni d'esame: nuovo gruppo *Simulazioni d'esame* in fondo all'elenco,
  una voce per esercizio, letto dai PDF formato orologio della repository di
  Gasdinamica (tagliati in strisce; figure, tabelle ed equazioni lunghe con lo
  zoom). Si aggiornano senza reinstallare nulla (workflow `notes`, ogni 6 ore
  o a mano).
- Opzione *In memoria* nel menu: Appunti ed esami (di default), Solo appunti,
  Solo esami. Il download in sottofondo scarica solo la scelta e, finito,
  libera la memoria occupata dal resto.
- Indice: riga `L` (libreria del capitolo); le versioni precedenti la ignorano
  e scaricano tutto.
- Workflow: build incrementale quando cambiano solo gli esami (appunti copiati
  dall'ultima Release, esami invariati riusati), cache dei pacchetti TeX Live
  con tempi massimi per lo specchio di Ubuntu; app orologio: CLI dell'SDK in
  cache e pacchetto `.iq` solo per le Release.

## Orologio 1.5.0

- Orologio stealth: opzione *Orologio se verticale* nel menu (No di default,
  0,5 s, 1 s, 2 s). Con l'accelerometro, il passaggio da orizzontale (schermo
  verso l'alto) a verticale (braccio abbassato o polso girato) mantenuto per
  il tempo scelto vale come una pressione prolungata sullo schermo (elenco,
  lettura, zoom). Dopo lo sblocco serve tornare orizzontali prima che scatti
  di nuovo.
- Orologio stealth: opzione *Sblocco orologio* nel menu per scegliere quanto
  tenere premuto lo schermo (o un pulsante) per tornare agli appunti: 1, 1,5,
  2, 2,5 (di default), 3 o 4 s.

## Orologio 1.4.0

- Elenco: opzione *Frecce nell'elenco* nel menu (di default spenta). Se
  attiva, ai lati compaiono due frecce ▲▼: un tocco sopra la voce selezionata
  passa alla precedente, sotto alla successiva, sulla voce la apre. Swipe e
  trascinamento continuano a funzionare.

## Orologio 1.3.1

- Orologio stealth: lo sblocco con la pressione prolungata è più affidabile.
  Il conto dei ~2,5 s parte dall'appoggio del dito e non ricomincia quando il
  sistema segnala la stessa pressione due volte (pressione prolungata e gesto
  *menu*: prima l'attesa poteva allungarsi oltre i 3 s). Vale anche se il dito
  si muove un poco: prima il sistema la trattava come un trascinamento e lo
  sblocco non partiva.

## Orologio 1.3.0

- Movimento: con l'accelerometro uno scatto deciso del polso vale come una
  pressione prolungata sullo schermo (elenco, lettura, zoom), quindi apre
  l'orologio stealth (o il menu se è disattivato). Voce di menu *Movimento*:
  No (di default), Scatto forte, Scatto medio, Scatto lieve. Nuovo permesso
  `Sensor` nel manifest.

## Orologio 1.2.1

- Orologio stealth: si apre anche con una pressione prolungata sullo schermo
  (elenco, lettura, zoom). Il menu si apre con un tocco sui tre puntini in alto
  o sul numero di pagina; la voce di menu si chiama ora *Orologio stealth*.

## Orologio 1.2.0

- Zoom: lo spostamento arriva fino a portare ogni angolo dell'immagine dentro
  il cerchio dello schermo (prima gli angoli in alto a destra e a sinistra
  restavano tagliati, es. la ground track).
- Orologio stealth: per tornare agli appunti serve tenere premuto ~2,5 s
  (prima 0,7 s); sollevare prima il dito annulla.
- Appunti: le figure a griglia (più righe e più colonne di grafici, oggi solo
  la ground track 2×2) si vedono prima intere e poi un grafico per pagina, a
  schermo pieno; le figure a striscia restano intere con lo zoom. Eccezioni in
  `rules.yaml` (`figure_panels`).
- Appunti: le immagini non si spezzano più tra due pagine. Se non entrano nella
  pagina corrente vanno all'inizio della successiva; le figure grandi hanno una
  pagina tutta per sé, centrata (sugli appunti attuali: 0 immagini spezzate
  invece di 55, 27 pagine solo-immagine).

## Orologio 1.1.1

- Accanto a «Sezioni …/…» compare la fonte: «web» o «tel» (telefono).
- Nel menu, sotto *Sincronizza ora*, l'esito del web: «web: ok», «web: indice
  senza file web» o «web: errore <codice>».
- *Test velocità* scarica anche un vero file degli appunti da GitHub Pages
  («pages: …»), come il download in sottofondo.
- Appunti: il `contentHash` del bundle copre anche l'indice. Prima l'app Android
  scartava un bundle che cambiava solo l'indice (le righe dei file web della
  1.1.0) come «già aggiornato», e l'orologio non riceveva mai gli indirizzi web.

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
