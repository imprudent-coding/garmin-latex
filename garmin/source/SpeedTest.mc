import Toybox.Communications;
import Toybox.Lang;
import Toybox.PersistedContent;
import Toybox.System;
import Toybox.WatchUi;

// Prova di velocità delle richieste web (Communications.makeWebRequest), da
// confrontare con i messaggi app↔telefono (la velocità di questi la mostra
// l'app Android). Anche le richieste web passano dal telefono (Garmin Connect).
// Tre richieste:
//   1-2. due file della repository dall'API di GitHub (~10 e ~42 KB, un solo
//        testo base64): latenza e velocità;
//   3.   un vero file degli appunti da GitHub Pages, preso dall'indice (righe
//        "W"/"F"), come lo scarica il download in sottofondo: stesso server,
//        stessa forma (elenco di pezzi con i caratteri del testo ricco).
class SpeedTest {
    const API = "https://api.github.com/repos/imprudent-coding/garmin-latex/contents/";
    // circa 10 KB e 42 KB di risposta
    const FILES = ["shared/FORMAT.md", "README.md"];
    // campi JSON oltre al contenuto (nomi, link, sha): stima
    const META_BYTES = 1100;

    var running as Boolean = false;
    private var _i as Number = 0;
    private var _start as Number = 0;
    private var _parts as Array<String> = [] as Array<String>;
    private var _done as Method or Null = null;

    function initialize() {
    }

    // done.invoke() a prova finita; il risultato è in speedResult().
    function run(done as Method) as Void {
        if (running) {
            return;
        }
        running = true;
        _done = done;
        _i = 0;
        _parts = [] as Array<String>;
        next();
    }

    private function next() as Void {
        if (_i > FILES.size()) {
            running = false;
            var r = "";
            for (var k = 0; k < _parts.size(); k++) {
                r += (k == 0 ? "" : " · ") + _parts[k];
            }
            getApp().store.setValue("speed", r);
            System.println("[speed] " + r);
            if (_done != null) {
                (_done as Method).invoke();
            }
            return;
        }
        var url = null;
        var opts = {
            :method => Communications.HTTP_REQUEST_METHOD_GET,
            :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
        };
        if (_i < FILES.size()) {
            url = API + FILES[_i];
            opts[:headers] = {"Accept" => "application/vnd.github+json"};
        } else {
            url = pagesUrl();
            if (url == null) {
                _parts.add("pages: indice senza file web");
                _i += 1;
                next();
                return;
            }
        }
        _start = System.getTimer();
        try {
            Communications.makeWebRequest(url as String, null, opts, method(:onResponse));
        } catch (e) {
            _parts.add(label() + "errore");
            _i += 1;
            next();
        }
    }

    private function label() as String {
        return _i < FILES.size() ? "api: " : "pages: ";
    }

    // Il primo file della sezione con più file web: di solito è pieno (~32 KB).
    private function pagesUrl() as String or Null {
        var idx = getApp().index;
        if (idx == null || (idx as Index).webBase == null) {
            return null;
        }
        var best = null;
        var chs = (idx as Index).chapters;
        for (var c = 0; c < chs.size(); c++) {
            for (var s = 0; s < chs[c].sections.size(); s++) {
                var sec = chs[c].sections[s];
                if (sec.packs.size() > 0 && (best == null || sec.packs.size() > (best as Section).packs.size())) {
                    best = sec;
                }
            }
        }
        if (best == null) {
            return null;
        }
        return ((idx as Index).webBase as String) + (best as Section).packs[0] + ".json";
    }

    function onResponse(code as Number, data as Dictionary or String or PersistedContent.Iterator or Null) as Void {
        var ms = System.getTimer() - _start;
        if (ms < 1) {
            ms = 1;
        }
        var bytes = -1;
        if (code == 200 && data instanceof Lang.Dictionary) {
            var d = data as Dictionary;
            if (d["content"] instanceof Lang.String) {
                bytes = (d["content"] as String).length() + META_BYTES;
            } else if (d["r"] instanceof Lang.Array) {
                bytes = packBytes(d["r"] as Array);
            }
        }
        if (bytes >= 0) {
            // KB/s con un decimale
            var tenths = bytes * 10000 / 1024 / ms;
            _parts.add(label() + (tenths / 10) + "." + (tenths % 10) + " KB/s (" + (bytes / 1024) + " KB, " + ms + " ms)");
        } else {
            _parts.add(label() + "errore " + code);
        }
        _i += 1;
        next();
    }

    // Byte dei pezzi di un file web (le chiavi e gli hash sono pochi byte).
    private function packBytes(items as Array) as Number {
        var n = 0;
        for (var i = 0; i < items.size(); i++) {
            var it = items[i];
            if (it instanceof Lang.Array && (it as Array).size() == 3 && (it as Array)[2] instanceof Lang.Array) {
                var chunks = (it as Array)[2] as Array;
                for (var k = 0; k < chunks.size(); k++) {
                    n += (chunks[k] as String).length() + 3;
                }
                n += 40;
            }
        }
        return n;
    }
}

// Risultato dell'ultima prova (salvato), o null.
function speedResult() as String or Null {
    var v = getApp().store.getValue("speed");
    return (v instanceof Lang.String) ? v as String : null;
}
