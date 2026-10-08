import Toybox.Communications;
import Toybox.Lang;
import Toybox.System;
import Toybox.WatchUi;

// stato della sincronizzazione
const ST_IDLE = 0;
const ST_HELLO = 1;
const ST_OK = 2;
const ST_OFFLINE = 3;
const ST_NOBUNDLE = 4;
const ST_SCHEMA = 5;

// pezzi al massimo per richiesta multipla (il telefono si ferma prima, a ~7 KB)
const MAX_BATCH = 8;

class CommListener extends Communications.ConnectionListener {
    private var _sync;

    function initialize(sync) {
        Communications.ConnectionListener.initialize();
        _sync = sync;
    }

    function onComplete() as Void {
    }

    function onError() as Void {
        _sync.onTransmitError();
    }
}

// Protocollo con l'app del telefono (shared/PROTOCOL.md): l'orologio chiede,
// il telefono risponde; un solo messaggio in volo, timeout e tentativi.
class Sync {
    const SCHEMA = 2;
    const TIMEOUT_MS = 10000;
    // tempo in più per ogni pezzo oltre il primo: una risposta da ~7 KB può
    // metterci più di 10 s, e ripetere la richiesta raddoppierebbe il traffico
    const PIECE_MS = 5000;
    const MAX_TRIES = 3;


    var state as Number = ST_IDLE;
    var phoneVersion as String = "";
    var lastError as String = "";

    // chiamato quando non c'è nulla in volo né in coda (usato dal prefetch)
    var idle as Method or Null = null;

    // richieste in coda: [chiave, n, hash, callback, pezzi]; callback è un Array di
    // [Method, multiplo] (più richieste uguali condividono la stessa risposta)
    private var _queue as Array<Array> = [] as Array<Array>;
    // [chiave, n, hash, callback, req, tentativi, pezzi]
    private var _inflight as Array or Null = null;
    private var _req as Number = 0;
    private var _ticker as Ticker;
    private var _listener as CommListener;

    function initialize(ticker as Ticker) {
        _ticker = ticker;
        _listener = new CommListener(self);
    }

    function busy() as Boolean {
        return _inflight != null || _queue.size() > 0;
    }

    function pending() as Number {
        return _queue.size() + (_inflight != null ? 1 : 0);
    }

    // ------------------------------------------------------------- hello
    function hello(cachedVersion as String, cb as Method) as Void {
        if (_inflight != null && !((_inflight as Array)[0] as String).equals("hello")) {
            // la richiesta interrotta torna in testa alla coda e riparte dopo l'hello
            var f = _inflight as Array;
            _queue = [[f[0], f[1], f[2], f[3], f[6]]].addAll(_queue) as Array<Array>;
        }
        state = ST_HELLO;
        _inflight = ["hello", 0, cachedVersion, cb, nextReq(), 0, 1];
        sendCurrent();
    }

    // ------------------------------------------------------------- richieste
    // Un pezzo: cb.invoke(chiave, n, totale, hash, dati); dati = String, o null se fallita.
    function request(key as String, n as Number, hash as String, cb as Method, urgent as Boolean) as Void {
        add(key, n, hash, cb, urgent, 1, false);
    }

    // Fino a `count` pezzi consecutivi da n in un messaggio (op "chunks"):
    // cb.invoke(chiave, n, totale, hash, dati); dati = Array<String> (almeno un pezzo) o null.
    function requestBatch(key as String, n as Number, count as Number, hash as String, cb as Method) as Void {
        // anche con count = 1 la callback riceve un Array: dipende da chi chiede, non da quanti pezzi
        add(key, n, hash, cb, false, count > MAX_BATCH ? MAX_BATCH : (count < 1 ? 1 : count), true);
    }

    private function add(key as String, n as Number, hash as String, cb as Method, urgent as Boolean,
                         count as Number, wantsArray as Boolean) as Void {
        var entry = [cb, wantsArray];
        if (_inflight != null && (_inflight[0] as String).equals(key) && (_inflight[1] as Number) == n
            && (_inflight[3] instanceof Lang.Array)) {
            (_inflight[3] as Array).add(entry);
            return;
        }
        for (var i = 0; i < _queue.size(); i++) {
            var q = _queue[i];
            if ((q[0] as String).equals(key) && (q[1] as Number) == n) {
                (q[3] as Array).add(entry);
                if (count > (q[4] as Number)) {
                    q[4] = count;
                }
                if (urgent && i > 0) {
                    _queue.remove(q);
                    _queue = [q].addAll(_queue) as Array<Array>;
                }
                return;
            }
        }
        var item = [key, n, hash, [entry], count];
        if (urgent) {
            _queue = [item].addAll(_queue) as Array<Array>;
        } else {
            _queue.add(item);
        }
        pump();
    }

    function cancelAll() as Void {
        _queue = [] as Array<Array>;
    }

    private function nextReq() as Number {
        _req += 1;
        return _req;
    }

    // Risposta a tutte le callback di una richiesta: chi ha chiesto un pezzo
    // riceve una String, chi ne ha chiesti più di uno un Array<String>.
    private function deliver(f as Array, total as Number, hash, data) as Void {
        var cbs = f[3] as Array;
        for (var i = 0; i < cbs.size(); i++) {
            var e = cbs[i] as Array;
            var d = data;
            if (data != null) {
                if (e[1] as Boolean) {
                    d = (data instanceof Lang.Array) ? data : [data];
                } else if (data instanceof Lang.Array) {
                    d = (data as Array).size() > 0 ? (data as Array)[0] : null;
                }
            }
            (e[0] as Method).invoke(f[0], f[1], total, hash, d);
        }
    }

    private function pump() as Void {
        if (_inflight != null) {
            return;
        }
        if (_queue.size() == 0) {
            if (idle != null) {
                (idle as Method).invoke();
            }
            return;
        }
        if (state == ST_OFFLINE || state == ST_NOBUNDLE || state == ST_SCHEMA) {
            // non insistere: fallisce subito, la vista mostrerà "non in cache"
            var q = _queue[0];
            _queue = _queue.slice(1, null) as Array<Array>;
            deliver(q, 0, q[2], null);
            pump();
            return;
        }
        var q = _queue[0];
        _queue = _queue.slice(1, null) as Array<Array>;
        _inflight = [q[0], q[1], q[2], q[3], nextReq(), 0, q[4]];
        sendCurrent();
    }

    private function sendCurrent() as Void {
        var f = _inflight as Array;
        var msg;
        if ((f[0] as String).equals("hello")) {
            msg = {"op" => "hello", "schema" => SCHEMA, "font" => FontInfo.ID, "ver" => f[2], "req" => f[4]};
        } else {
            msg = {"op" => "get", "k" => f[0], "n" => f[1], "h" => f[2], "req" => f[4]};
            if ((f[6] as Number) > 1) {
                msg["c"] = f[6];
            }
        }
        _ticker.schedule("sync", TIMEOUT_MS + ((f[6] as Number) - 1) * PIECE_MS, method(:onTimeout), false);
        try {
            Communications.transmit(msg, null, _listener);
        } catch (e) {
            onTransmitError();
        }
    }

    function onTransmitError() as Void {
        // trattato come un timeout anticipato
        _ticker.schedule("sync", 1000, method(:onTimeout), false);
    }

    function onTimeout() as Void {
        if (_inflight == null) {
            return;
        }
        var f = _inflight as Array;
        f[5] = (f[5] as Number) + 1;
        if ((f[5] as Number) < MAX_TRIES) {
            // nuovo tentativo con un pezzo solo (stesso req: una risposta multipla
            // in ritardo resta valida); le callback multiple ricevono un Array
            f[6] = 1;
            sendCurrent();
            return;
        }
        _inflight = null;
        state = ST_OFFLINE;
        lastError = "timeout";
        if ((f[0] as String).equals("hello")) {
            (f[3] as Method).invoke(false);
        } else {
            deliver(f, 0, f[2], null);
        }
        // le richieste rimaste falliscono subito (telefono non raggiungibile)
        pump();
        WatchUi.requestUpdate();
    }

    // ------------------------------------------------------------- messaggi dal telefono
    function onPhone(msg as Communications.PhoneAppMessage) as Void {
        var d = msg.data;
        if (!(d instanceof Lang.Dictionary)) {
            return;
        }
        var data = d as Dictionary;
        var op = data["op"];
        if (op == null) {
            return;
        }
        if (op.equals("update")) {
            // nuovo bundle sul telefono: ricomincia dall'hello
            var app = getApp();
            app.onPhoneUpdate();
            return;
        }
        if (_inflight == null) {
            return;
        }
        var f = _inflight as Array;
        var req = data["req"];
        if (req != null && Util.toNum(req) != (f[4] as Number)) {
            return; // risposta a una richiesta vecchia
        }
        if (op.equals("hello") && (f[0] as String).equals("hello")) {
            _ticker.cancel("sync");
            _inflight = null;
            var ok = data["ok"] == true;
            if (ok) {
                state = ST_OK;
                phoneVersion = data["ver"] != null ? data["ver"].toString() : "";
            } else {
                var err = data["err"] != null ? data["err"].toString() : "";
                lastError = err;
                state = err.equals("schema") ? ST_SCHEMA : ST_NOBUNDLE;
            }
            (f[3] as Method).invoke(ok ? data : false);
            pump();
            WatchUi.requestUpdate();
            return;
        }
        if (op.equals("chunk") || op.equals("chunks") || op.equals("err")) {
            var k = data["k"];
            if (k == null || !k.toString().equals(f[0] as String) || Util.toNum(data["n"]) != (f[1] as Number)) {
                return;
            }
            _ticker.cancel("sync");
            _inflight = null;
            if (op.equals("chunk") || op.equals("chunks")) {
                var payload = data["d"];
                if (op.equals("chunks") && !(payload instanceof Lang.Array && (payload as Array).size() > 0)) {
                    payload = null;
                }
                deliver(f, Util.toNum(data["of"]), data["h"].toString(), payload);
            } else {
                lastError = data["err"] != null ? data["err"].toString() : "err";
                deliver(f, 0, f[2], null);
                if (lastError.equals("stale")) {
                    getApp().onPhoneUpdate();
                }
            }
            pump();
        }
    }
}
