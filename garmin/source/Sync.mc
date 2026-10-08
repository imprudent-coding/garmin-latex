import Toybox.Communications;
import Toybox.Lang;
import Toybox.System;
import Toybox.Timer;
import Toybox.WatchUi;

// stato della sincronizzazione
const ST_IDLE = 0;
const ST_HELLO = 1;
const ST_OK = 2;
const ST_OFFLINE = 3;
const ST_NOBUNDLE = 4;
const ST_SCHEMA = 5;

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
    const SCHEMA = 1;
    const TIMEOUT_MS = 10000;
    const MAX_TRIES = 3;


    var state as Number = ST_IDLE;
    var phoneVersion as String = "";
    var lastError as String = "";

    // richieste in coda: [chiave, n, hash, callback]
    private var _queue as Array<Array> = [] as Array<Array>;
    private var _inflight as Array or Null = null;  // [chiave, n, hash, callback, req, tentativi]
    private var _req as Number = 0;
    private var _timer as Timer.Timer;
    private var _listener as CommListener;

    function initialize() {
        _timer = new Timer.Timer();
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
        state = ST_HELLO;
        _inflight = ["hello", 0, cachedVersion, cb, nextReq(), 0];
        sendCurrent();
    }

    // ------------------------------------------------------------- richieste
    // cb.invoke(chiave, n, totale, hash, dati) ; dati = null se fallita
    function request(key as String, n as Number, hash as String, cb as Method, urgent as Boolean) as Void {
        if (_inflight != null && (_inflight[0] as String).equals(key) && (_inflight[1] as Number) == n) {
            return;
        }
        for (var i = 0; i < _queue.size(); i++) {
            var q = _queue[i];
            if ((q[0] as String).equals(key) && (q[1] as Number) == n) {
                return;
            }
        }
        var item = [key, n, hash, cb];
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

    private function pump() as Void {
        if (_inflight != null || _queue.size() == 0) {
            return;
        }
        if (state == ST_OFFLINE || state == ST_NOBUNDLE || state == ST_SCHEMA) {
            // non insistere: fallisce subito, la vista mostrerà "non in cache"
            var q = _queue[0];
            _queue = _queue.slice(1, null) as Array<Array>;
            (q[3] as Method).invoke(q[0], q[1], 0, q[2], null);
            pump();
            return;
        }
        var q = _queue[0];
        _queue = _queue.slice(1, null) as Array<Array>;
        _inflight = [q[0], q[1], q[2], q[3], nextReq(), 0];
        sendCurrent();
    }

    private function sendCurrent() as Void {
        var f = _inflight as Array;
        var msg;
        if ((f[0] as String).equals("hello")) {
            msg = {"op" => "hello", "schema" => SCHEMA, "font" => FontInfo.ID, "ver" => f[2], "req" => f[4]};
        } else {
            msg = {"op" => "get", "k" => f[0], "n" => f[1], "h" => f[2], "req" => f[4]};
        }
        _timer.stop();
        _timer.start(method(:onTimeout), TIMEOUT_MS, false);
        try {
            Communications.transmit(msg, null, _listener);
        } catch (e) {
            onTransmitError();
        }
    }

    function onTransmitError() as Void {
        // trattato come un timeout anticipato
        _timer.stop();
        _timer.start(method(:onTimeout), 1000, false);
    }

    function onTimeout() as Void {
        if (_inflight == null) {
            return;
        }
        var f = _inflight as Array;
        f[5] = (f[5] as Number) + 1;
        if ((f[5] as Number) < MAX_TRIES) {
            sendCurrent();
            return;
        }
        _inflight = null;
        state = ST_OFFLINE;
        lastError = "timeout";
        if ((f[0] as String).equals("hello")) {
            (f[3] as Method).invoke(false);
        } else {
            (f[3] as Method).invoke(f[0], f[1], 0, f[2], null);
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
            _timer.stop();
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
        if (op.equals("chunk") || op.equals("err")) {
            var k = data["k"];
            if (k == null || !k.toString().equals(f[0] as String) || Util.toNum(data["n"]) != (f[1] as Number)) {
                return;
            }
            _timer.stop();
            _inflight = null;
            if (op.equals("chunk")) {
                (f[3] as Method).invoke(f[0], f[1], Util.toNum(data["of"]), data["h"].toString(), data["d"]);
            } else {
                lastError = data["err"] != null ? data["err"].toString() : "err";
                (f[3] as Method).invoke(f[0], f[1], 0, f[2], null);
                if (lastError.equals("stale")) {
                    getApp().onPhoneUpdate();
                }
            }
            pump();
        }
    }
}
