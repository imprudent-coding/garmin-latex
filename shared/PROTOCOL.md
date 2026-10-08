# Protocollo orologio ↔ telefono (schema 2)

Trasporto: Connect IQ Communications (orologio: `Communications.transmit` /
`registerForPhoneAppMessages`; Android: `ConnectIQ.sendMessage` /
`registerForAppEvents`). Ogni messaggio è un dizionario con chiavi stringa.
La documentazione Garmin non indica un limite di dimensione dei messaggi: per
questo i dati viaggiano in pezzi di al massimo `chunkBytes` (default 1800 byte)
e c'è **un solo messaggio in volo alla volta**.

È l'orologio a chiedere (modello *pull*): il telefono risponde solo alle
richieste, tranne la notifica `update`. `progress` è una notifica
dell'orologio: il telefono la mostra e non risponde. Chi riceve un `op`
sconosciuto lo ignora.

## Orologio → telefono

| op | campi | significato |
|---|---|---|
| `hello` | `schema`, `font`, `ver` (versione in cache o `""`) | apertura: "che versione hai?" |
| `get` | `k` chiave, `n` indice del pezzo, `h` hash atteso (o `""`), `req` id richiesta, `c` (facoltativo) numero di pezzi | "dammi il pezzo n della risorsa k" (con `c` > 1: "dammi fino a c pezzi da n") |
| `progress` | `ver`, `sec`/`secs` sezioni in cache/totali, `img`/`imgs` immagini in cache/trovate, `fin` tutto in cache | stato del download in sottofondo; **nessuna risposta** |

## Telefono → orologio

| op | campi | significato |
|---|---|---|
| `hello` | `ok`, `schema`, `ver`, `ih` hash indice, `ic` pezzi indice, `err` | risposta a `hello`; `ok=false` se non c'è ancora un bundle (`err="nobundle"`) o lo schema non è supportato (`err="schema"`) |
| `chunk` | `k`, `n`, `of` totale pezzi, `h` hash risorsa, `d` dati, `req` | un pezzo |
| `chunks` | come `chunk`, ma `d` è un array: i pezzi `n`, `n+1`, … | risposta a `get` con `c` > 1: almeno un pezzo, al massimo `c`, entro ~7 KB di dati |
| `err` | `k`, `n`, `req`, `err` | `notfound` (chiave inesistente) o `stale` (l'hash atteso non è quello del bundle attuale: l'orologio deve ripetere `hello` e ricaricare l'indice) |
| `update` | `ver` | è arrivato un nuovo bundle: l'orologio, se aperto, ripete `hello` |

## Flusso tipico

```
orologio                         telefono
  hello(ver="A") ───────────────▶
                ◀─────────────── hello(ok, ver="B", ih, ic=3)
  (ver diversa: invalida l'indice in cache)
  get(idx, 0) ──────────────────▶
                ◀─────────────── chunk(idx, 0, of=3, …)
  get(idx, 1) …                  …
  (l'utente apre la sezione q-a1, pagina 7 → pezzo 2)
  get(s:q-a1, 2, h=…) ──────────▶
                ◀─────────────── chunk(s:q-a1, 2, of=5, …)
  (la pagina usa l'immagine i:3fa…)
  get(i:3fa…, 0) ───────────────▶
                ◀─────────────── chunk(i:3fa…, 0, of=2, …)
```

## Download dal web (prima scelta)

Il download in sottofondo prova prima i file web dell'indice (righe `W`/`F`,
shared/FORMAT.md) con `Communications.makeWebRequest`: misurati ~8-12 KB/s su un
vívoactive 5, contro ~0,4 KB/s dei messaggi tra app. I messaggi con il telefono
restano la riserva:

- un file web che fallisce (errore HTTP o di rete) viene saltato e il suo
  contenuto arriva dal telefono; dopo due errori di fila il web si spegne fino
  al giro successivo del download;
- senza righe `W`/`F` (indice vecchio o Pages non configurato) si usa solo il
  telefono;
- se l'app del telefono non risponde ma l'indice è in cache, il download dal web
  parte lo stesso;
- la lettura chiede sempre al telefono, perché il pezzo della pagina aperta
  arriva prima così;
- `hello`, indice e notifica `update` passano sempre dal telefono.

## Più pezzi per messaggio

Il tempo di un download completo dipende soprattutto dal numero di scambi
(ognuno passa per Garmin Connect), non dai byte. Per questo il download in
sottofondo e le immagini chiedono più pezzi alla volta (`get` con `c`, fino a
8). Il telefono risponde con `chunks` e si ferma prima di superare
7200 byte di dati. Garmin non documenta un limite per i messaggi: se l'invio
fallisce con `FAILURE_MESSAGE_TOO_LARGE`, il telefono dimezza il limite (fino a
un pezzo per messaggio) e l'orologio, scaduto il timeout, ripete la richiesta.
La lettura chiede sempre un pezzo solo, per mostrare subito la pagina.

I pezzi salvati sull'orologio restano quelli del bundle (≤ `chunkBytes`):
una risposta `chunks` diventa più valori nello Storage.

## Affidabilità

- **Orologio**: timeout di 10 s per richiesta, più 5 s per ogni pezzo oltre il
  primo in una richiesta multipla; fino a 3 tentativi, dal secondo con un pezzo
  solo (stesso `req`: una risposta multipla in ritardo resta valida). Poi
  "telefono non raggiungibile": si continua a leggere ciò che è in cache e, se
  il download in sottofondo non è finito, l'orologio ripete `hello` ogni 30 s.
- **Telefono**: una richiesta ripetuta (stesso `req`, `k`, `n`) mentre la sua
  risposta è ancora in invio viene ignorata, per non raddoppiare il traffico.
  L'app mostra la velocità misurata degli invii.
- **Telefono**: se `sendMessage` non riesce, ritenta fino a 3 volte
  (0,5 s, 1 s, 2 s).
- Gli hash rendono innocui i messaggi duplicati o fuori ordine: l'orologio
  scarta un `chunk` che non corrisponde alla richiesta in corso.

## Cache sull'orologio (`Application.Storage`)

Spazio: 10 MB per app sul vívoactive 5 (`appStorageCapacity` nel device file
`simulator.json`). La guida *Persisting Data* indica 8 KB per valore e 128 KB
in totale, l'API reference di `Storage` 32 KB per valore e un totale variabile
per dispositivo: il totale della guida non vale qui, il limite per valore lo
rispettiamo comunque.

- una chiave per pezzo: `c|<chiave>|<n>` → stringa (≤ `chunkBytes`);
- `m0` … `m15` → metadati divisi in 16 dizionari (per hash della chiave):
  per ogni risorsa hash, pezzi presenti, byte e ultimo accesso. Un dizionario
  unico con tutte le risorse supererebbe gli 8 KB. Il vecchio valore unico
  `meta` viene convertito al primo avvio;
- `pf` → versione degli appunti già scaricata per intero;
- budget di 6 MB (gli appunti interi sono ~1,6 MB); se lo supera, o se
  `setValue` lancia un'eccezione di spazio esaurito, elimina le risorse usate
  meno di recente (mai l'indice o la sezione aperta) e riprova.

## Download in sottofondo

Dopo l'indice, l'orologio scarica tutte le sezioni (in ordine di indice) e
poi le immagini citate nelle loro righe `I`. Chiede un pezzo solo quando non
c'è nulla in volo né in coda: le richieste della lettura passano sempre
prima. Si ferma se il telefono non risponde e riprende al prossimo `hello`
riuscito, saltando le risorse già in cache. Ogni 10 risorse e alla fine invia
`progress`.
