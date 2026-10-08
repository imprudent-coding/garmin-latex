import Toybox.Graphics;
import Toybox.Lang;
import Toybox.System;
import Toybox.Time;
import Toybox.Time.Gregorian;
import Toybox.WatchUi;

// Schermata orologio che copre gli appunti: si apre all'istante con il
// pulsante in alto e si chiude solo con una pressione prolungata (schermo o
// pulsante). Gli altri gesti non fanno nulla, come su un quadrante.
class ClockView extends WatchUi.View {
    function initialize() {
        View.initialize();
    }

    function onShow() as Void {
        getApp().ticker.schedule("clock", 5000, method(:tick), true);
    }

    function onHide() as Void {
        getApp().ticker.cancel("clock");
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
    const HOLD_MS = 700;

    private var _pressedAt as Number or Null = null;

    function initialize() {
        BehaviorDelegate.initialize();
    }

    private function close() as Boolean {
        WatchUi.popView(WatchUi.SLIDE_IMMEDIATE);
        return true;
    }

    // pressione prolungata sullo schermo
    function onHold(evt as WatchUi.ClickEvent) as Boolean {
        return close();
    }

    // il gesto "menu" del dispositivo è anch'esso una pressione prolungata
    function onMenu() as Boolean {
        return close();
    }

    // pressione prolungata di un pulsante: misurata tra pressione e rilascio
    function onKeyPressed(evt as WatchUi.KeyEvent) as Boolean {
        _pressedAt = System.getTimer();
        return true;
    }

    function onKeyReleased(evt as WatchUi.KeyEvent) as Boolean {
        var at = _pressedAt;
        _pressedAt = null;
        if (at != null && System.getTimer() - (at as Number) >= HOLD_MS) {
            return close();
        }
        return true;
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

// Apre l'orologio sopra la vista corrente, senza animazione.
function showClock() as Void {
    var v = new ClockView();
    WatchUi.pushView(v, new ClockDelegate(), WatchUi.SLIDE_IMMEDIATE);
}
