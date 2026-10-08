import Toybox.Communications;
import Toybox.Lang;
import Toybox.System;
import Toybox.Timer;
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
    private var _timer as Timer.Timer;
    private var _timerOn as Boolean = false;
    private var _ver as String = "";
    private var _secs as Array<Section> = [] as Array<Section>;
    private var _si as Number = 0;
    private var _scanned as Dictionary = {} as Dictionary;  // pezzi della sezione corrente già esaminati
    private var _images as Array<String> = [] as Array<String>;
    private var _seen as Dictionary = {} as Dictionary;
    private var _ii as Number = 0;
    private var _waiting as Boolean = false;               // richiesta di prefetch in corso
    private var _sinceNotify as Number = 0;
    private var _listener as NotifyListener;

    function initialize(store as Store, sync as Sync) {
        _store = store;
        _sync = sync;
        _timer = new Timer.Timer();
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
        notify();
        onIdle();
    }

    function stop() as Void {
        active = false;
        _waiting = false;
        _timer.stop();
        _timerOn = false;
    }

    function onIdle() as Void {
        if (!active || _waiting || _timerOn || _sync.busy() || _sync.state != ST_OK) {
            return;
        }
        step();
    }

    function onTick() as Void {
        _timerOn = false;
        onIdle();
    }

    private function later() as Void {
        if (!_timerOn) {
            _timerOn = true;
            _timer.start(method(:onTick), 50, false);
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
            }
            if (missing >= 0) {
                _waiting = true;
                _sync.request(key, missing, sec.hash, method(:onSection), false);
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
            _sync.request(key, n, "", method(:onImage), false);
            return;
        }
        active = false;
        finished = failed == 0;
        if (finished) {
            _store.setValue("pf", _ver);
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
    function onSection(key, n, total, hash, data) as Void {
        _waiting = false;
        if (data == null) {
            onFailure();
            return;
        }
        _store.put(key as String, n as Number, total as Number, hash as String, data as String);
        scan(data as String);
        _scanned[n] = true;
    }

    function onImage(key, n, total, hash, data) as Void {
        _waiting = false;
        if (data == null) {
            onFailure();
            return;
        }
        _store.put(key as String, n as Number, total as Number, hash as String, data as String);
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
