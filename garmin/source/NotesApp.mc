import Toybox.Application;
import Toybox.Communications;
import Toybox.Lang;
import Toybox.System;
import Toybox.WatchUi;

function getApp() as NotesApp {
    return Application.getApp() as NotesApp;
}

class NotesApp extends Application.AppBase {
    var store as Store;
    var sync as Sync;
    var images as ImageCache;
    var rich as RichText or Null = null;
    var index as Index or Null = null;
    var showMemory as Boolean = false;
    var status as String = "";
    // indice in arrivo dal telefono
    private var _idxHash as String = "";
    private var _idxChunks as Number = 0;
    private var _idxVersion as String = "";

    function initialize() {
        AppBase.initialize();
        store = new Store();
        sync = new Sync();
        images = new ImageCache(store, sync);
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
    }

    function onStop(state as Dictionary or Null) as Void {
        store.save();
    }

    function getInitialView() {
        var v = new ChapterListView();
        return [v, new ListDelegate(v)];
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
    }

    function onPhoneUpdate() as Void {
        startSync();
    }

    function onHello(res) as Void {
        if (res == false || !(res instanceof Lang.Dictionary)) {
            status = statusText();
            WatchUi.requestUpdate();
            return;
        }
        var d = res as Dictionary;
        _idxVersion = d["ver"].toString();
        _idxHash = d["ih"].toString();
        _idxChunks = Util.toNum(d["ic"]);
        var cachedVer = store.getValue("ver");
        if (index != null && cachedVer != null && _idxVersion.equals(cachedVer) && store.isComplete("idx", _idxHash)) {
            status = statusText();
            WatchUi.requestUpdate();
            return;
        }
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
            index = new Index(text as String);
            store.setValue("ver", _idxVersion);
            var valid = {} as Dictionary;
            var chs = (index as Index).chapters;
            for (var c = 0; c < chs.size(); c++) {
                for (var s = 0; s < chs[c].sections.size(); s++) {
                    var sec = chs[c].sections[s];
                    valid[sec.key()] = sec.hash;
                }
            }
            store.dropStale(valid);
            Mem.log("nuovo indice");
        }
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
        if (st == ST_OK) {
            if (index != null && !(index as Index).fontId.equals(FontInfo.ID)) {
                return WatchUi.loadResource(Rez.Strings.OldApp) as String;
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

    // ------------------------------------------------------------- posizione di lettura
    function savePosition(id as String, page as Number) as Void {
        store.setValue("pos", [id, page]);
    }

    function lastPosition() as Array or Null {
        var p = store.getValue("pos");
        return (p instanceof Lang.Array) ? p as Array : null;
    }
}
