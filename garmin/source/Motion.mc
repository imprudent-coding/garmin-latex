import Toybox.Lang;
import Toybox.Sensor;
import Toybox.System;
import Toybox.WatchUi;

// valori di "Movimento" nel menu: soglia in milli-g oltre (o sotto) 1 g a
// riposo; 0 = spento. Camminare muove il polso di ~300-600 mg, uno scatto
// deciso del polso supera 1 g.
const MOTION_STEPS = [0, 1500, 1100, 800];

// valori di "Orologio se verticale": quanto deve restare verticale
// l'orologio prima di aprire l'orologio stealth, in ms; 0 = spento.
const VERTICAL_STEPS = [0, 500, 1000, 2000];

// Accelerometro, due gesti che valgono come una pressione prolungata sullo
// schermo (holdToClock), solo nell'elenco, in lettura e nello zoom:
// - "Movimento": uno scatto deciso del polso;
// - "Orologio se verticale": l'orologio passa da orizzontale (schermo verso
//   l'alto) a verticale (braccio abbassato o polso girato) e resta così per
//   il tempo scelto.
// Il sensore resta spento se entrambe le opzioni sono su No.
class Motion {
    // campioni al secondo; i dati arrivano a blocchi di 1 s
    const RATE = 25;
    const SAMPLE_MS = 40;
    // campioni oltre soglia nello stesso blocco: un urto singolo non basta
    const MIN_HITS = 2;
    // dopo uno scatto, il polso torna fermo: niente secondo scatto per un po'
    const COOLDOWN_MS = 3000;
    // componente della gravità perpendicolare allo schermo (milli-g, filtrata):
    // sotto VERT_Z l'orologio è verticale (~65° o più), sopra FLAT_Z è
    // orizzontale (~45° o meno); in mezzo non cambia nulla
    const VERT_Z = 400;
    const FLAT_Z = 700;

    // la vista in primo piano accetta il gesto (elenco, lettura, zoom)
    var target as Boolean = false;
    private var _on as Boolean = false;
    private var _lastAt as Number = -100000;
    // z filtrata (passa-basso), per ignorare le scosse
    private var _zf as Number = 1000;
    // da quanto l'orologio è verticale (ms)
    private var _vertMs as Number = 0;
    // l'orologio è stato orizzontale dall'ultimo scatto: solo il passaggio
    // da orizzontale a verticale apre l'orologio, non il restare verticale
    private var _armed as Boolean = false;

    function initialize() {
    }

    // Accende o spegne il sensore secondo le impostazioni.
    function apply() as Void {
        if (!(Toybox has :Sensor) || !(Sensor has :registerSensorDataListener)) {
            return;
        }
        stop();
        var app = getApp();
        if (app.motionThreshold() <= 0 && app.verticalDelay() <= 0) {
            return;
        }
        _vertMs = 0;
        _armed = false;
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
        if (acc == null) {
            return;
        }
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
        var app = getApp();
        // tutti e due a ogni blocco: il verticale segue lo stato campione per campione
        var shook = shake(xs, ys, zs, n, app.motionThreshold());
        var tilted = vertical(zs, n, app.verticalDelay());
        if (shook || tilted) {
            _lastAt = System.getTimer();
            // come se il dito fosse rimasto premuto sullo schermo
            holdToClock();
            WatchUi.requestUpdate();
        }
    }

    private function ready() as Boolean {
        return target && System.getTimer() - _lastAt >= COOLDOWN_MS;
    }

    // Scatto: almeno MIN_HITS campioni con |a| > 1 g + t oppure |a| < 1 g - t
    // (confronto sui quadrati, niente radice).
    private function shake(xs as Array<Number>, ys as Array<Number>, zs as Array<Number>, n as Number,
            t as Number) as Boolean {
        if (t <= 0 || !ready()) {
            return false;
        }
        var hi = (1000 + t) * (1000 + t);
        var lo = t < 1000 ? (1000 - t) * (1000 - t) : -1;
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
        return hits >= MIN_HITS;
    }

    // Verticale: lo stato si segue anche quando il gesto non è accettato
    // (orologio o menu aperti), ma un passaggio a verticale avvenuto lì non
    // conta: dopo lo sblocco serve tornare orizzontali.
    private function vertical(zs as Array<Number>, n as Number, delay as Number) as Boolean {
        if (delay <= 0) {
            return false;
        }
        var fire = false;
        for (var i = 0; i < n; i++) {
            var z = zs[i];
            _zf += (z - _zf) / 4;
            var az = _zf < 0 ? -_zf : _zf;
            if (az > FLAT_Z) {
                _armed = true;
                _vertMs = 0;
            } else if (az < VERT_Z) {
                if (!ready()) {
                    _armed = false;
                }
                _vertMs += SAMPLE_MS;
                if (_armed && _vertMs >= delay) {
                    _armed = false;
                    fire = true;
                }
            } else {
                _vertMs = 0;
            }
        }
        return fire;
    }
}

function verticalLabel(ms as Number) as String {
    if (ms == 0) {
        return WatchUi.loadResource(Rez.Strings.Off) as String;
    }
    if (ms % 1000 == 0) {
        return (ms / 1000).toString() + " s";
    }
    return (ms / 1000).toString() + "," + (ms % 1000 / 100).toString() + " s";
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
