import Toybox.Lang;
import Toybox.Sensor;
import Toybox.System;
import Toybox.WatchUi;

// valori di "Movimento" nel menu: soglia in milli-g oltre (o sotto) 1 g a
// riposo; 0 = spento. Camminare muove il polso di ~300-600 mg, uno scatto
// deciso del polso supera 1 g.
const MOTION_STEPS = [0, 1500, 1100, 800];

// Accelerometro: uno scatto del polso vale come una pressione prolungata
// sullo schermo (holdToClock), solo nell'elenco, in lettura e nello zoom. Il
// sensore resta spento se "Movimento" è su No.
class Motion {
    // campioni al secondo; i dati arrivano a blocchi di 1 s
    const RATE = 25;
    // campioni oltre soglia nello stesso blocco: un urto singolo non basta
    const MIN_HITS = 2;
    // dopo uno scatto, il polso torna fermo: niente secondo scatto per un po'
    const COOLDOWN_MS = 3000;

    // la vista in primo piano accetta il gesto (elenco, lettura, zoom)
    var target as Boolean = false;
    private var _on as Boolean = false;
    private var _lastAt as Number = -100000;

    function initialize() {
    }

    // Accende o spegne il sensore secondo l'impostazione.
    function apply(threshold as Number) as Void {
        if (!(Toybox has :Sensor) || !(Sensor has :registerSensorDataListener)) {
            return;
        }
        if (_on) {
            Sensor.unregisterSensorDataListener();
            _on = false;
        }
        if (threshold <= 0) {
            return;
        }
        try {
            Sensor.registerSensorDataListener(method(:onData), {
                :period => 1,
                :accelerometer => {:enabled => true, :sampleRate => RATE}
            });
            _on = true;
        } catch (e) {
            _on = false;
        }
    }

    function stop() as Void {
        if (_on) {
            Sensor.unregisterSensorDataListener();
            _on = false;
        }
    }

    function onData(data as Sensor.SensorData) as Void {
        var acc = data.accelerometerData;
        if (acc == null || !target) {
            return;
        }
        var app = getApp();
        var now = System.getTimer();
        if (now - _lastAt < COOLDOWN_MS) {
            return;
        }
        var t = app.motionThreshold();
        if (t <= 0) {
            return;
        }
        // confronto sui quadrati (niente radice): |a| > 1 g + t oppure |a| < 1 g - t
        var hi = (1000 + t) * (1000 + t);
        var lo = t < 1000 ? (1000 - t) * (1000 - t) : -1;
        var xs = acc.x;
        var ys = acc.y;
        var zs = acc.z;
        var n = xs.size();
        if (ys.size() < n) {
            n = ys.size();
        }
        if (zs.size() < n) {
            n = zs.size();
        }
        var hits = 0;
        for (var i = 0; i < n; i++) {
            var x = xs[i];
            var y = ys[i];
            var z = zs[i];
            var m2 = x * x + y * y + z * z;
            if (m2 > hi || m2 < lo) {
                hits++;
            }
        }
        if (hits < MIN_HITS) {
            return;
        }
        _lastAt = now;
        // come se il dito fosse rimasto premuto sullo schermo
        holdToClock();
        WatchUi.requestUpdate();
    }
}

function motionLabel(t as Number) as String {
    if (t == 0) {
        return WatchUi.loadResource(Rez.Strings.Off) as String;
    }
    if (t >= 1500) {
        return WatchUi.loadResource(Rez.Strings.MotionStrong) as String;
    }
    if (t >= 1100) {
        return WatchUi.loadResource(Rez.Strings.MotionMedium) as String;
    }
    return WatchUi.loadResource(Rez.Strings.MotionLight) as String;
}
