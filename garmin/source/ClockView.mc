import Toybox.Graphics;
import Toybox.Lang;
import Toybox.System;
import Toybox.Time;
import Toybox.Time.Gregorian;
import Toybox.WatchUi;

// Schermata orologio che copre gli appunti: si apre all'istante con il
// pulsante in alto e si chiude solo tenendo premuto lo schermo o un pulsante
// per ~2,5 s. Gli altri gesti non fanno nulla, come su un quadrante.
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
    // circa mezzo secondo-un secondo: da lì mancano ~2 s
    const AFTER_HOLD_MS = 2000;

    function initialize() {
        BehaviorDelegate.initialize();
    }

    // Parte il conto alla rovescia: se la pressione dura fino alla fine, si
    // torna agli appunti; un rilascio prima lo annulla.
    private function arm(ms as Number) as Boolean {
        getApp().ticker.schedule("unlock", ms, method(:unlock), false);
        return true;
    }

    private function disarm() as Boolean {
        getApp().ticker.cancel("unlock");
        return true;
    }

    function unlock() as Void {
        WatchUi.popView(WatchUi.SLIDE_IMMEDIATE);
    }

    // pressione prolungata sullo schermo
    function onHold(evt as WatchUi.ClickEvent) as Boolean {
        return arm(AFTER_HOLD_MS);
    }

    // il gesto "menu" del dispositivo è anch'esso una pressione prolungata
    function onMenu() as Boolean {
        return arm(AFTER_HOLD_MS);
    }

    // dito sollevato (anche dopo un trascinamento): annulla
    function onRelease(evt as WatchUi.ClickEvent) as Boolean {
        return disarm();
    }

    function onDrag(evt as WatchUi.DragEvent) as Boolean {
        if (evt.getType() == WatchUi.DRAG_TYPE_STOP) {
            disarm();
        }
        return true;
    }

    // pulsante: tenuto premuto per UNLOCK_MS
    function onKeyPressed(evt as WatchUi.KeyEvent) as Boolean {
        return arm(UNLOCK_MS);
    }

    function onKeyReleased(evt as WatchUi.KeyEvent) as Boolean {
        return disarm();
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

// Apre l'orologio sopra la vista corrente, senza animazione.
function showClock() as Void {
    var v = new ClockView();
    WatchUi.pushView(v, new ClockDelegate(), WatchUi.SLIDE_IMMEDIATE);
}
