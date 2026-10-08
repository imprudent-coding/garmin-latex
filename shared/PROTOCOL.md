# Protocollo orologio ↔ telefono (schema 1)

Trasporto: Connect IQ Communications (orologio: `Communications.transmit` /
`registerForPhoneAppMessages`; Android: `ConnectIQ.sendMessage` /
`registerForAppEvents`). Ogni messaggio è un dizionario con chiavi stringa.
La documentazione Garmin non indica un limite di dimensione dei messaggi: per
questo i dati viaggiano in pezzi di al massimo `chunkBytes` (default 1800 byte)
e c'è **un solo messaggio in volo alla volta**.

È l'orologio a chiedere (modello *pull*): il telefono risponde solo alle
richieste, tranne la notifica `update`.

## Orologio → telefono

| op | campi | significato |
|---|---|---|
| `hello` | `schema`, `font`, `ver` (versione in cache o `""`) | apertura: "che versione hai?" |
| `get` | `k` chiave, `n` indice del pezzo, `h` hash atteso (o `""`), `req` id richiesta | "dammi il pezzo n della risorsa k" |

## Telefono → orologio

| op | campi | significato |
|---|---|---|
| `hello` | `ok`, `schema`, `ver`, `ih` hash indice, `ic` pezzi indice, `err` | risposta a `hello`; `ok=false` se non c'è ancora un bundle (`err="nobundle"`) o lo schema non è supportato (`err="schema"`) |
| `chunk` | `k`, `n`, `of` totale pezzi, `h` hash risorsa, `d` dati, `req` | un pezzo |
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

## Affidabilità

- **Orologio**: timeout di 10 s per richiesta, fino a 3 tentativi, poi
  "telefono non raggiungibile" (si continua a leggere ciò che è in cache).
- **Telefono**: se `sendMessage` non riesce, ritenta fino a 3 volte
  (0,5 s, 1 s, 2 s).
- Gli hash rendono innocui i messaggi duplicati o fuori ordine: l'orologio
  scarta un `chunk` che non corrisponde alla richiesta in corso.

## Cache sull'orologio (`Application.Storage`)

Limiti documentati da Garmin: 8 KB per valore e 128 KB in totale secondo la
guida *Persisting Data*; 32 KB per valore e totale variabile per dispositivo
secondo l'API reference di `Storage`. L'app rispetta il limite più stretto:

- una chiave per pezzo: `c|<chiave>|<n>` → stringa (≤ `chunkBytes`);
- `meta` → dizionario con, per ogni risorsa, hash, pezzi presenti, byte e
  ultimo accesso;
- budget di default 96 KB; se lo supera, o se `setValue` lancia
  un'eccezione di spazio esaurito, elimina le risorse usate meno di recente
  (mai l'indice o la sezione aperta) e riprova.
