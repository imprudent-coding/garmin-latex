import Toybox.Application;
import Toybox.Communications;
import Toybox.Lang;
import Toybox.PersistedContent;
import Toybox.System;
import Toybox.WatchUi;

function getApp() as NotesApp {
    return Application.getApp() as NotesApp;
}

class NotesApp extends Application.AppBase {
    const RETRY_MS = 30000;
    // schema del bundle che l'app sa leggere (come Sync.SCHEMA)
    const WEB_SCHEMA = 2;

    var ticker as Ticker;
    var store as Store;
    var sync as Sync;
    var images as ImageCache;
    var prefetch as Prefetch;
    var speed as SpeedTest;
    var motion as Motion;
    var rich as RichText or Null = null;
    var index as Index or Null = null;
    var showMemory as Boolean = false;
    // ultima chiusura dell'orologio stealth (System.getTimer)
    var clockClosedAt as Number = -100000;
    var status as String = "";
    // il telefono ha un bundle più vecchio dell'indice preso dal web: non gli si chiede
    // nulla finché non si aggiorna (tutto arriva dai file web)
    var phoneBehind as Boolean = false;
    private var _webIdxBusy as Boolean = false;
    // indice in arrivo dal telefono
    private var _idxHash as String = "";
    private var _idxChunks as Number = 0;
    private var _idxVersion as String = "";

    function initialize() {
        AppBase.initialize();
        ticker = new Ticker();
        store = new Store(ticker);
        sync = new Sync(ticker);
        images = new ImageCache(store, sync, ticker);
        prefetch = new Prefetch(store, sync, ticker);
        speed = new SpeedTest();
        motion = new Motion();
        if (Communications has :registerForPhoneAppMessages) {
            Communications.registerForPhoneAppMessages(method(:onPhoneMessage));
        }
    }

    function onPhoneMessage(msg as Communications.PhoneAppMessage) as Void {
        sync.onPhone(msg);
    }

    function onStart(state as Dictionary or Null) as Void {
        Mem.log("avvio");
        rich = new RichText();
        Mem.log("font caricati");
        loadCachedIndex();
        Mem.log("indice in cache caricato");
        startSync();
        motion.apply();
    }

    function onStop(state as Dictionary or Null) as Void {
        motion.stop();
        store.save();
    }

    function getInitialView() {
        var v = new QuestionListView();
        return [v, new QuestionListDelegate(v)];
    }

    // ------------------------------------------------------------- indice
    function loadCachedIndex() as Void {
        var h = store.hashOf("idx");
        if (h == null) {
            return;
        }
        var text = store.getAll("idx", h, "\n");
        if (text != null) {
            try {
                index = new Index(text);
            } catch (e) {
                index = null;
            }
        }
    }

    function startSync() as Void {
        status = WatchUi.loadResource(Rez.Strings.Syncing) as String;
        var ver = store.getValue("ver");
        sync.hello(ver instanceof Lang.String ? ver as String : "", method(:onHello));
        webCheck();
    }

    // ------------------------------------------------------------- indice dal web
    // All'avvio e con "Sincronizza ora" l'orologio controlla anche l'indice pubblicato
    // su GitHub Pages (w/idx.json): se è più recente lo usa subito, senza aspettare che
    // l'app del telefono scarichi la nuova Release. Serve un indice già in cache (da lì
    // viene l'indirizzo dei file web).
    function webCheck() as Void {
        if (_webIdxBusy || index == null || (index as Index).webBase == null) {
            return;
        }
        _webIdxBusy = true;
        try {
            Communications.makeWebRequest(((index as Index).webBase as String) + "idx.json", null, {
                :method => Communications.HTTP_REQUEST_METHOD_GET,
                :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
            }, method(:onWebIndex));
        } catch (e) {
            _webIdxBusy = false;
        }
    }

    function onWebIndex(code as Number, data as Dictionary or String or PersistedContent.Iterator or Null) as Void {
        _webIdxBusy = false;
        if (code != 200 || !(data instanceof Lang.Dictionary)) {
            System.println("indice web: " + code);
            return;
        }
        var d = data as Dictionary;
        var ver = d["ver"];
        var hash = d["hash"];
        var chunks = d["chunks"];
        if (!(ver instanceof Lang.String) || !(hash instanceof Lang.String) || !(chunks instanceof Lang.Array)) {
            return;
        }
        // indice di un'app più recente (font o schema diversi): ci pensa il telefono
        if (Util.toNum(d["schema"]) != WEB_SCHEMA || !FontInfo.ID.equals(d["font"])) {
            return;
        }
        var cached = store.getValue("ver");
        if (cached instanceof Lang.String && !Util.newer(ver as String, cached as String)) {
            return;
        }
        prefetch.stop();
        var cs = chunks as Array;
        for (var i = 0; i < cs.size(); i++) {
            if (!store.put("idx", i, cs.size(), hash as String, cs[i] as String)) {
                return;
            }
        }
        var text = store.getAll("idx", hash as String, "\n");
        if (text != null) {
            Mem.log("indice dal web");
            installIndex(text as String, ver as String);
            if (sync.state == ST_OK && !sync.phoneVersion.equals(ver)) {
                // il telefono ha ancora il bundle precedente
                phoneBehind = true;
                sync.state = ST_OFFLINE;
            }
            status = statusText();
            prefetch.start(index as Index);
            WatchUi.requestUpdate();
        }
    }

    // Telefono non raggiungibile con il download incompleto: nuovo hello tra
    // RETRY_MS, finché il download non finisce (prima si fermava fino alla
    // riapertura della lettura o a "Sincronizza ora").
    function retrySoon() as Void {
        if (sync.state == ST_OFFLINE && !prefetch.finished && !ticker.isScheduled("rehello")) {
            ticker.schedule("rehello", RETRY_MS, method(:startSync), false);
        }
    }

    function onPhoneUpdate() as Void {
        startSync();
    }

    function onHello(res) as Void {
        if (res == false || !(res instanceof Lang.Dictionary)) {
            status = statusText();
            // anche senza l'app del telefono si può scaricare dal web (indice in cache)
            if (index != null && sync.state == ST_OFFLINE) {
                prefetch.start(index as Index);
            }
            retrySoon();
            WatchUi.requestUpdate();
            return;
        }
        var d = res as Dictionary;
        _idxVersion = d["ver"].toString();
        _idxHash = d["ih"].toString();
        _idxChunks = Util.toNum(d["ic"]);
        var cachedVer = store.getValue("ver");
        phoneBehind = false;
        if (index != null && cachedVer instanceof Lang.String && Util.newer(cachedVer as String, _idxVersion)) {
            // l'indice in cache (dal web) è più recente del bundle del telefono: niente
            // richieste al telefono, che risponderebbe "stale"; tutto arriva dal web
            phoneBehind = true;
            sync.state = ST_OFFLINE;
            status = statusText();
            prefetch.start(index as Index);
            retrySoon();
            WatchUi.requestUpdate();
            return;
        }
        if (index != null && cachedVer != null && _idxVersion.equals(cachedVer) && store.isComplete("idx", _idxHash)) {
            status = statusText();
            prefetch.start(index as Index);
            WatchUi.requestUpdate();
            return;
        }
        prefetch.stop();
        if (store.hashOf("idx") != null && !_idxHash.equals(store.hashOf("idx"))) {
            store.pinned = [] as Array<String>;
            store.remove("idx");
            store.pinned = ["idx"] as Array<String>;
        }
        requestIndexChunk(0);
    }

    private function requestIndexChunk(n as Number) as Void {
        for (var i = n; i < _idxChunks; i++) {
            if (store.get("idx", i, _idxHash) == null) {
                status = (WatchUi.loadResource(Rez.Strings.Syncing) as String) + " " + (i + 1) + "/" + _idxChunks;
                sync.request("idx", i, _idxHash, method(:onIndexChunk), true);
                WatchUi.requestUpdate();
                return;
            }
        }
        // indice completo
        var text = store.getAll("idx", _idxHash, "\n");
        if (text != null) {
            installIndex(text as String, _idxVersion);
            Mem.log("nuovo indice");
            status = statusText();
            prefetch.start(index as Index);
        }
        status = statusText();
        WatchUi.requestUpdate();
    }

    // Nuovo indice (dal telefono o dal web): lo rende attuale ed elimina le sezioni
    // che non ne fanno più parte (es. una simulazione d'esame cancellata).
    private function installIndex(text as String, ver as String) as Void {
        index = new Index(text);
        store.setValue("ver", ver);
        var valid = {} as Dictionary;
        var chs = (index as Index).chapters;
        for (var c = 0; c < chs.size(); c++) {
            for (var s = 0; s < chs[c].sections.size(); s++) {
                var sec = chs[c].sections[s];
                valid[sec.key()] = sec.hash;
            }
        }
        store.dropStale(valid);
    }

    // Aggiorna la riga di stato (avanzamento del prefetch).
    function refreshStatus() as Void {
        status = statusText();
        WatchUi.requestUpdate();
    }

    function onIndexChunk(key, n, total, hash, data) as Void {
        if (data == null) {
            status = statusText();
            WatchUi.requestUpdate();
            return;
        }
        store.put("idx", n as Number, total as Number, hash as String, data as String);
        requestIndexChunk((n as Number) + 1);
    }

    function statusText() as String {
        var st = sync.state;
        if (phoneBehind) {
            var pw = prefetch.label();
            if (pw != null) {
                return pw as String;
            }
            return WatchUi.loadResource(prefetch.finished ? Rez.Strings.AllOnWatch : Rez.Strings.FromWeb) as String;
        }
        if (st == ST_OK) {
            if (index != null && !(index as Index).fontId.equals(FontInfo.ID)) {
                return WatchUi.loadResource(Rez.Strings.OldApp) as String;
            }
            var p = prefetch.label();
            if (p != null) {
                return p as String;
            }
            if (prefetch.finished) {
                return WatchUi.loadResource(Rez.Strings.AllOnWatch) as String;
            }
            return WatchUi.loadResource(Rez.Strings.Synced) as String;
        }
        if (st == ST_NOBUNDLE) {
            return WatchUi.loadResource(Rez.Strings.NoBundle) as String;
        }
        if (st == ST_SCHEMA) {
            return WatchUi.loadResource(Rez.Strings.OldApp) as String;
        }
        if (st == ST_OFFLINE) {
            return WatchUi.loadResource(Rez.Strings.Offline) as String;
        }
        return WatchUi.loadResource(Rez.Strings.Syncing) as String;
    }

    // ------------------------------------------------------------- impostazioni
    // secondi per pagina dello scorrimento automatico (0 = spento)
    function autoSeconds() as Number {
        var v = store.getValue("auto");
        return (v instanceof Lang.Number) ? v as Number : 0;
    }

    // pulsante in alto = orologio (di default sì)
    function clockButton() as Boolean {
        var v = store.getValue("clockKey");
        return !(v instanceof Lang.Boolean) || (v as Boolean);
    }

    // elenco: tocchi sopra/sotto la voce selezionata per scorrere (di default no)
    function listArrows() as Boolean {
        var v = store.getValue("arrows");
        return (v instanceof Lang.Boolean) && (v as Boolean);
    }

    // soglia dell'accelerometro in milli-g (0 = spento, di default)
    function motionThreshold() as Number {
        var v = store.getValue("motion");
        return (v instanceof Lang.Number) ? v as Number : 0;
    }

    // pressione per tornare agli appunti dall'orologio stealth, in ms (di default 2,5 s)
    function unlockMs() as Number {
        var v = store.getValue("unlock");
        return (v instanceof Lang.Number && UNLOCK_STEPS.indexOf(v) >= 0) ? v as Number : 2500;
    }

    // ms di orologio verticale prima di aprire l'orologio stealth (0 = spento, di default)
    function verticalDelay() as Number {
        var v = store.getValue("vert");
        return (v instanceof Lang.Number) ? v as Number : 0;
    }

    // libreria mostrata nell'elenco e tenuta in memoria: LIB_NOTES (di default) o LIB_EXAMS
    function library() as Number {
        var v = store.getValue("lib");
        return (v instanceof Lang.Number && (v as Number) == LIB_EXAMS) ? LIB_EXAMS : LIB_NOTES;
    }

    // suffisso delle chiavi salvate per libreria (voce selezionata, posizione di lettura):
    // gli appunti usano le chiavi di sempre
    function libKey(k as String) as String {
        return library() == LIB_EXAMS ? k + "2" : k;
    }

    // ------------------------------------------------------------- posizione di lettura
    function savePosition(id as String, page as Number) as Void {
        store.setValue(libKey("pos"), [id, page]);
    }

    function lastPosition() as Array or Null {
        var p = store.getValue(libKey("pos"));
        return (p instanceof Lang.Array) ? p as Array : null;
    }
}
