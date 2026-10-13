import Toybox.Graphics;
import Toybox.Lang;
import Toybox.System;
import Toybox.Time;
import Toybox.Time.Gregorian;
import Toybox.WatchUi;

// Schermata orologio che copre gli appunti: si apre all'istante con il
// pulsante in alto o con una pressione prolungata sullo schermo, e si chiude
// solo tenendo premuto lo schermo o un pulsante per ~2,5 s. Gli altri gesti non fanno nulla, come su un quadrante.
class ClockView extends WatchUi.View {
    function initialize() {
        View.initialize();
    }

    function onShow() as Void {
        getApp().ticker.schedule("clock", 5000, method(:tick), true);
    }

    function onHide() as Void {
        getApp().ticker.cancel("clock");
        getApp().ticker.cancel("unlock");
    }

    function tick() as Void {
        WatchUi.requestUpdate();
    }

    function onUpdate(dc as Dc) as Void {
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();
        var w = dc.getWidth();
        var h = dc.getHeight();
        var t = System.getClockTime();
        var hour = t.hour;
        if (!System.getDeviceSettings().is24Hour) {
            hour = hour % 12;
            if (hour == 0) {
                hour = 12;
            }
        }
        var time = hour.format("%02d") + ":" + t.min.format("%02d");
        var info = Gregorian.info(Time.now(), Time.FORMAT_MEDIUM);
        var date = info.day_of_week + " " + info.day.format("%d") + " " + info.month;

        dc.setColor(Graphics.COLOR_WHITE, Graphics.COLOR_TRANSPARENT);
        dc.drawText(w / 2, h / 2, Graphics.FONT_NUMBER_THAI_HOT, time,
            Graphics.TEXT_JUSTIFY_CENTER | Graphics.TEXT_JUSTIFY_VCENTER);
        dc.setColor(0x9A9A9A, Graphics.COLOR_TRANSPARENT);
        dc.drawText(w / 2, h / 2 - 110, Graphics.FONT_SMALL, date.toUpper(), Graphics.TEXT_JUSTIFY_CENTER);
        var batt = System.getSystemStats().battery;
        dc.drawText(w / 2, h / 2 + 80, Graphics.FONT_SMALL, batt.format("%d") + "%", Graphics.TEXT_JUSTIFY_CENTER);
    }
}

class ClockDelegate extends WatchUi.BehaviorDelegate {
    // tempo di pressione per tornare agli appunti
    const UNLOCK_MS = 2500;
    // il sistema segnala la pressione prolungata sullo schermo (onHold) dopo
    // circa mezzo secondo dall'appoggio del dito
    const HOLD_LAG_MS = 500;
    const MIN_MS = 50;

    // inizio della pressione in corso (System.getTimer); null = dito sollevato
    private var _downAt as Number or Null = null;

    function initialize() {
        BehaviorDelegate.initialize();
    }

    // Conto alla rovescia dall'inizio della pressione: se dura fino a
    // UNLOCK_MS si torna agli appunti; un rilascio prima lo annulla. Più
    // segnali della stessa pressione (inizio del trascinamento, onHold,
    // onMenu) non allungano l'attesa: conta il primo.
    private function press(startedAt as Number) as Boolean {
        if (_downAt == null || startedAt < (_downAt as Number)) {
            _downAt = startedAt;
        }
        var left = UNLOCK_MS - (System.getTimer() - (_downAt as Number));
        getApp().ticker.schedule("unlock", left < MIN_MS ? MIN_MS : left, method(:unlock), false);
        return true;
    }

    private function lift() as Boolean {
        _downAt = null;
        getApp().ticker.cancel("unlock");
        return true;
    }

    function unlock() as Void {
        _downAt = null;
        getApp().clockClosedAt = System.getTimer();
        WatchUi.popView(WatchUi.SLIDE_IMMEDIATE);
    }

    // pressione prolungata sullo schermo: il dito è giù da ~HOLD_LAG_MS
    function onHold(evt as WatchUi.ClickEvent) as Boolean {
        return press(System.getTimer() - HOLD_LAG_MS);
    }

    // il gesto "menu" del dispositivo è anch'esso una pressione prolungata
    function onMenu() as Boolean {
        return press(System.getTimer() - HOLD_LAG_MS);
    }

    // dito sollevato (anche dopo un trascinamento): annulla
    function onRelease(evt as WatchUi.ClickEvent) as Boolean {
        return lift();
    }

    // Se il dito si muove un poco il sistema può non segnalare onHold (lo
    // tratta come un trascinamento): l'inizio del trascinamento fa partire lo
    // stesso conto, così la pressione vale anche con il dito non fermo.
    function onDrag(evt as WatchUi.DragEvent) as Boolean {
        var t = evt.getType();
        if (t == WatchUi.DRAG_TYPE_START) {
            press(System.getTimer());
        } else if (t == WatchUi.DRAG_TYPE_STOP) {
            lift();
        }
        return true;
    }

    // pulsante: tenuto premuto per UNLOCK_MS
    function onKeyPressed(evt as WatchUi.KeyEvent) as Boolean {
        return press(System.getTimer());
    }

    function onKeyReleased(evt as WatchUi.KeyEvent) as Boolean {
        return lift();
    }

    // tutto il resto viene ignorato (anche il pulsante indietro)
    function onKey(evt as WatchUi.KeyEvent) as Boolean {
        return true;
    }

    function onBack() as Boolean {
        return true;
    }

    function onSelect() as Boolean {
        return true;
    }

    function onNextPage() as Boolean {
        return true;
    }

    function onPreviousPage() as Boolean {
        return true;
    }

    function onTap(evt as WatchUi.ClickEvent) as Boolean {
        return true;
    }

    function onSwipe(evt as WatchUi.SwipeEvent) as Boolean {
        return true;
    }
}

// Pressione fisica del pulsante in alto (non un tocco: sugli schermi touch un
// tocco genera anche onSelect, quindi l'orologio non può stare su onSelect).
function isClockKey(evt as WatchUi.KeyEvent) as Boolean {
    return evt.getKey() == WatchUi.KEY_ENTER && getApp().clockButton();
}

// Pressione prolungata sullo schermo (elenco, lettura, zoom): orologio se è
// attivo "Pulsante orologio", altrimenti il menu come prima. Il menu resta
// raggiungibile con un tocco (tre puntini in alto nell'elenco, numero di
// pagina in lettura).
function holdToClock() as Boolean {
    var app = getApp();
    if (!app.clockButton()) {
        showMainMenu();
        return true;
    }
    // appena tornati dall'orologio il dito può essere ancora sullo schermo:
    // niente rientro immediato
    if (System.getTimer() - app.clockClosedAt < 1500) {
        return true;
    }
    showClock();
    return true;
}

// Apre l'orologio sopra la vista corrente, senza animazione.
function showClock() as Void {
    var v = new ClockView();
    WatchUi.pushView(v, new ClockDelegate(), WatchUi.SLIDE_IMMEDIATE);
}
