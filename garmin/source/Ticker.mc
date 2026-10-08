import Toybox.Lang;
import Toybox.System;
import Toybox.Timer;

// Un solo Timer per tutta l'app. Connect IQ permette pochi timer attivi
// insieme (di default 3, "depends on the host system"): sincronizzazione,
// immagini, prefetch, scorrimento automatico e orologio li supererebbero.
// Ogni lavoro ha un nome; schedule() con lo stesso nome lo sostituisce.
class Ticker {
    const MIN_MS = 50;

    private var _timer as Timer.Timer;
    // nome -> [scadenza (System.getTimer), callback, periodo (0 = una volta)]
    private var _jobs as Dictionary = {} as Dictionary;

    function initialize() {
        _timer = new Timer.Timer();
    }

    function schedule(name as String, ms as Number, cb as Method, repeat as Boolean) as Void {
        _jobs[name] = [System.getTimer() + ms, cb, repeat ? ms : 0];
        arm();
    }

    function cancel(name as String) as Void {
        if (_jobs.hasKey(name)) {
            _jobs.remove(name);
            arm();
        }
    }

    function isScheduled(name as String) as Boolean {
        return _jobs.hasKey(name);
    }

    private function arm() as Void {
        _timer.stop();
        var keys = _jobs.keys();
        if (keys.size() == 0) {
            return;
        }
        var first = null;
        for (var i = 0; i < keys.size(); i++) {
            var at = (_jobs[keys[i]] as Array)[0] as Number;
            if (first == null || at < first) {
                first = at;
            }
        }
        var delay = (first as Number) - System.getTimer();
        _timer.start(method(:onFire), delay < MIN_MS ? MIN_MS : delay, false);
    }

    function onFire() as Void {
        var now = System.getTimer();
        var keys = _jobs.keys();
        var due = [] as Array<String>;
        for (var i = 0; i < keys.size(); i++) {
            if (((_jobs[keys[i]] as Array)[0] as Number) <= now + 5) {
                due.add(keys[i] as String);
            }
        }
        for (var i = 0; i < due.size(); i++) {
            var j = _jobs[due[i]] as Array or Null;
            // una callback precedente può averlo annullato o riprogrammato
            if (j == null || (j[0] as Number) > now + 5) {
                continue;
            }
            var period = j[2] as Number;
            if (period > 0) {
                j[0] = now + period;
            } else {
                _jobs.remove(due[i]);
            }
            (j[1] as Method).invoke();
        }
        arm();
    }
}
