import Toybox.Communications;
import Toybox.Lang;
import Toybox.PersistedContent;
import Toybox.System;
import Toybox.WatchUi;

// Prova di velocità delle richieste web (Communications.makeWebRequest), da
// confrontare con i messaggi app↔telefono (la velocità di questi la mostra
// l'app Android). Anche le richieste web passano dal telefono (Garmin
// Connect), ma per un'altra strada: se fossero molto più veloci, l'orologio
// potrebbe scaricare gli appunti direttamente da GitHub.
// Scarica due file della repository tramite l'API di GitHub (JSON, contenuto
// in base64): uno piccolo e uno medio, per separare latenza e velocità.
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
        if (_i >= FILES.size()) {
            running = false;
            var r = "web:";
            for (var k = 0; k < _parts.size(); k++) {
                r += (k == 0 ? " " : " · ") + _parts[k];
            }
            getApp().store.setValue("speed", r);
            System.println("[speed] " + r);
            if (_done != null) {
                (_done as Method).invoke();
            }
            return;
        }
        _start = System.getTimer();
        try {
            Communications.makeWebRequest(API + FILES[_i], null, {
                :method => Communications.HTTP_REQUEST_METHOD_GET,
                :headers => {"Accept" => "application/vnd.github+json"},
                :responseType => Communications.HTTP_RESPONSE_CONTENT_TYPE_JSON
            }, method(:onResponse));
        } catch (e) {
            _parts.add("errore");
            _i += 1;
            next();
        }
    }

    function onResponse(code as Number, data as Dictionary or String or PersistedContent.Iterator or Null) as Void {
        var ms = System.getTimer() - _start;
        if (code == 200 && data instanceof Lang.Dictionary && (data as Dictionary)["content"] instanceof Lang.String) {
            var bytes = ((data as Dictionary)["content"] as String).length() + META_BYTES;
            if (ms < 1) {
                ms = 1;
            }
            // KB/s con un decimale
            var tenths = bytes * 10000 / 1024 / ms;
            _parts.add((tenths / 10) + "." + (tenths % 10) + " KB/s (" + (bytes / 1024) + " KB, " + ms + " ms)");
        } else {
            _parts.add("errore " + code);
        }
        _i += 1;
        next();
    }

}

// Risultato dell'ultima prova (salvato), o null.
function speedResult() as String or Null {
    var v = getApp().store.getValue("speed");
    return (v instanceof Lang.String) ? v as String : null;
}
