import Toybox.Communications;
import Toybox.Lang;
import Toybox.System;
import Toybox.WatchUi;

class NotifyListener extends Communications.ConnectionListener {
    function initialize() {
        Communications.ConnectionListener.initialize();
    }

    function onComplete() as Void {
    }

    function onError() as Void {
    }
}

// Scaricamento in sottofondo di tutti gli appunti nella cache (Store), così la
// lettura non aspetta il Bluetooth. Prima tutte le sezioni, poi le immagini
// trovate nelle loro pagine (righe "I", shared/FORMAT.md).
// Lavora solo quando il collegamento è libero (Sync.idle): le richieste della
// lettura passano sempre per prime. Si ferma se il telefono non risponde e
// riparte al prossimo hello riuscito; la chiave "pf" ricorda la versione già
// scaricata per intero.
class Prefetch {
    // passi locali (risorse già in cache) per ciclo, per restare sotto il watchdog
    const LOCAL_STEPS = 3;
    const NOTIFY_EVERY = 10;

    var active as Boolean = false;
    var finished as Boolean = false;
    var secDone as Number = 0;
    var secTotal as Number = 0;
    var imgDone as Number = 0;
    var failed as Number = 0;

    private var _store as Store;
    private var _sync as Sync;
    private var _ticker as Ticker;
    private var _ver as String = "";
    private var _secs as Array<Section> = [] as Array<Section>;
    private var _si as Number = 0;
    private var _scanned as Dictionary = {} as Dictionary;  // pezzi della sezione corrente già esaminati
    private var _images as Array<String> = [] as Array<String>;
    private var _seen as Dictionary = {} as Dictionary;
    private var _ii as Number = 0;
    private var _waiting as Boolean = false;               // richiesta di prefetch in corso
    // risposta con più pezzi da salvare, un pezzo per passo (watchdog):
    // [chiave, primo n, totale, hash, Array<String>, sezione?, prossimo indice]
    private var _pend as Array or Null = null;
    // immagini non più usate da eliminare dopo un download completo, poche per passo
    private var _drop as Array<String> = [] as Array<String>;
    private var _sinceNotify as Number = 0;
    private var _listener as NotifyListener;

    function initialize(store as Store, sync as Sync, ticker as Ticker) {
        _store = store;
        _sync = sync;
        _ticker = ticker;
        _listener = new NotifyListener();
        sync.idle = method(:onIdle);
    }

    function imgTotal() as Number {
        return _images.size();
    }

    // Da chiamare quando l'indice è pronto e il telefono risponde.
    function start(index as Index) as Void {
        if (active && _ver.equals(index.version)) {
            onIdle();
            return;
        }
        _ver = index.version;
        _secs = [] as Array<Section>;
        for (var c = 0; c < index.chapters.size(); c++) {
            _secs.addAll(index.chapters[c].sections);
        }
        secTotal = _secs.size();
        var pf = _store.getValue("pf");
        if (pf instanceof Lang.String && (pf as String).equals(_ver)) {
            active = false;
            finished = true;
            secDone = secTotal;
            notify();
            return;
        }
        finished = false;
        active = true;
        _si = 0;
        _ii = 0;
        secDone = 0;
        imgDone = 0;
        failed = 0;
        _scanned = {} as Dictionary;
        _images = [] as Array<String>;
        _seen = {} as Dictionary;
        _waiting = false;
        _pend = null;
        notify();
        onIdle();
    }

    function stop() as Void {
        active = false;
        _waiting = false;
        _pend = null;
        _ticker.cancel("pf");
    }

    function onIdle() as Void {
        if (!active || _waiting || _ticker.isScheduled("pf") || _sync.busy() || _sync.state != ST_OK) {
            return;
        }
        step();
    }

    function onTick() as Void {
        if (_pend != null) {
            storeNext();
            return;
        }
        onIdle();
    }

    function onDrop() as Void {
        var k = 0;
        while (_drop.size() > 0 && k < 10) {
            _store.remove(_drop[_drop.size() - 1]);
            _drop = _drop.slice(0, _drop.size() - 1) as Array<String>;
            k += 1;
        }
        if (_drop.size() > 0) {
            _ticker.schedule("drop", 50, method(:onDrop), false);
        }
    }

    // Salva (e per le sezioni esamina) un pezzo della risposta in attesa.
    private function storeNext() as Void {
        var p = _pend as Array;
        var d = p[4] as Array;
        var i = p[6] as Number;
        if (i >= d.size()) {
            _pend = null;
            _waiting = false;
            onIdle();
            return;
        }
        var n = (p[1] as Number) + i;
        var c = d[i] as String;
        _store.put(p[0] as String, n, p[2] as Number, p[3] as String, c);
        if (p[5] as Boolean) {
            scan(c);
            _scanned[n] = true;
        }
        if (i + 1 < d.size()) {
            p[6] = i + 1;
            _ticker.schedule("pf", 50, method(:onTick), false);
            return;
        }
        _pend = null;
        _waiting = false;
        onIdle();
    }

    private function accept(key, n, total, hash, data, isSection as Boolean) as Void {
        var d = (data instanceof Lang.Array) ? data : [data];
        _pend = [key, n, total, hash, d, isSection, 0];
        _ticker.schedule("pf", 50, method(:onTick), false);
    }

    private function later() as Void {
        if (!_ticker.isScheduled("pf")) {
            _ticker.schedule("pf", 50, method(:onTick), false);
        }
    }

    private function step() as Void {
        if (_store.nearlyFull()) {
            // gli appunti non stanno nel budget: il resto si scarica quando serve
            System.println("prefetch: cache quasi piena, mi fermo");
            stop();
            notify();
            return;
        }
        var local = 0;
        while (_si < _secs.size()) {
            var sec = _secs[_si];
            var key = sec.key();
            var total = sec.starts.size();
            var missing = -1;
            for (var n = 0; n < total; n++) {
                if (_scanned[n] != null) {
                    continue;
                }
                var c = _store.get(key, n, sec.hash);
                if (c == null) {
                    missing = n;
                    break;
                }
                scan(c);
                _scanned[n] = true;
                local += 1;
                if (local >= LOCAL_STEPS) {
                    later();
                    return;
                }
            }
            if (missing >= 0) {
                _waiting = true;
                _sync.requestBatch(key, missing, total - missing, sec.hash, method(:onSection));
                return;
            }
            _si += 1;
            secDone += 1;
            _scanned = {} as Dictionary;
            progressed();
            local += 1;
            if (local >= LOCAL_STEPS) {
                later();
                return;
            }
        }
        while (_ii < _images.size()) {
            var key = _images[_ii];
            if (_store.isComplete(key, "")) {
                _ii += 1;
                imgDone += 1;
                progressed();
                local += 1;
                if (local >= LOCAL_STEPS) {
                    later();
                    return;
                }
                continue;
            }
            var n = 0;
            var total = _store.totalOf(key);
            for (var i = 0; i < total; i++) {
                if (_store.get(key, i, "") == null) {
                    n = i;
                    break;
                }
            }
            _waiting = true;
            _sync.requestBatch(key, n, total > 0 ? total - n : MAX_BATCH, "", method(:onImage));
            return;
        }
        active = false;
        finished = failed == 0;
        if (finished) {
            _store.setValue("pf", _ver);
            _drop = _store.imagesExcept(_seen);
            if (_drop.size() > 0) {
                _ticker.schedule("drop", 50, method(:onDrop), false);
            }
        }
        Mem.log("prefetch completato");
        notify();
        getApp().refreshStatus();
    }

    // Raccoglie le chiavi delle immagini dalle righe "I" di un pezzo di sezione.
    private function scan(chunk as String) as Void {
        var rest = chunk;
        while (rest.length() > 0) {
            var nl = rest.find("\n");
            var line = nl == null ? rest : rest.substring(0, nl) as String;
            rest = nl == null ? "" : rest.substring(nl + 1, rest.length()) as String;
            if (line.length() > 1 && line.substring(0, 1).equals("I")) {
                var f = Util.splitN(line, ",", 7);
                if (f.size() == 7) {
                    addImage(f[5]);
                    addImage(f[6]);
                }
            }
        }
    }

    private function addImage(key as String) as Void {
        if (key.length() > 2 && _seen[key] == null) {
            _seen[key] = true;
            _images.add(key);
        }
    }

    // Callback di Sync per i pezzi richiesti dal prefetch.
    // _waiting resta vero finché i pezzi non sono tutti salvati (storeNext).
    function onSection(key, n, total, hash, data) as Void {
        if (data == null) {
            _waiting = false;
            onFailure();
            return;
        }
        accept(key, n, total, hash, data, true);
    }

    function onImage(key, n, total, hash, data) as Void {
        if (data == null) {
            _waiting = false;
            onFailure();
            return;
        }
        accept(key, n, total, hash, data, false);
    }

    // Telefono non raggiungibile o bundle cambiato: si riprende al prossimo hello.
    // Altrimenti (risorsa inesistente) si salta la risorsa.
    private function onFailure() as Void {
        if (_sync.state != ST_OK || _sync.lastError.equals("stale")) {
            stop();
            return;
        }
        failed += 1;
        if (_si < _secs.size()) {
            _si += 1;
            secDone += 1;
            _scanned = {} as Dictionary;
        } else {
            _ii += 1;
            imgDone += 1;
        }
    }

    private function progressed() as Void {
        _sinceNotify += 1;
        if (_sinceNotify >= NOTIFY_EVERY) {
            notify();
        }
        getApp().refreshStatus();
    }

    // Avvisa il telefono dello stato (op "progress", shared/PROTOCOL.md). Nessuna risposta.
    private function notify() as Void {
        _sinceNotify = 0;
        try {
            Communications.transmit({"op" => "progress", "ver" => _ver, "sec" => secDone, "secs" => secTotal,
                "img" => imgDone, "imgs" => _images.size(), "fin" => finished}, null, _listener);
        } catch (e) {
        }
    }

    // Testo per la riga di stato; null quando non c'è nulla da mostrare.
    function label() as String or Null {
        if (!active) {
            return null;
        }
        if (_si < _secs.size()) {
            return (WatchUi.loadResource(Rez.Strings.PrefetchSections) as String) + " " + secDone + "/" + secTotal;
        }
        return (WatchUi.loadResource(Rez.Strings.PrefetchImages) as String) + " " + imgDone + "/" + _images.size();
    }
}
