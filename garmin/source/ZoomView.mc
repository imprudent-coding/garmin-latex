import Toybox.Graphics;
import Toybox.Lang;
import Toybox.WatchUi;

// Versione ingrandita di una figura/equazione, spostabile con swipe o trascinamento.
// Lo schermo è rotondo: gli angoli del quadrato 390x390 non si vedono. Lo
// spostamento arriva quindi fino a portare ogni bordo dell'immagine dentro il
// quadrato inscritto nel cerchio (margine MARGIN per lato), così ogni angolo
// dell'immagine si può vedere per intero.
class ZoomView extends WatchUi.View {
    private var _key as String;
    // spostamento: punto dell'immagine nell'angolo in alto a sinistra dello schermo
    // (negativo = immagine spostata verso destra/basso); parte dall'angolo in alto a sinistra
    var ox as Number = -100000;
    var oy as Number = -100000;
    var iw as Number = 0;
    var ih as Number = 0;
    private var _w as Number = 390;

    function initialize(key as String) {
        View.initialize();
        _key = key;
    }

    function onShow() as Void {
        getApp().motion.target = true;
    }

    function onHide() as Void {
        getApp().motion.target = false;
    }

    // margine tra il quadrato dello schermo e quello inscritto nel cerchio (~57 px a 390)
    private function margin() as Number {
        return _w / 2 - _w * 707 / 2000;
    }

    function minX() as Number {
        return -margin();
    }

    private function maxOff(n as Number) as Number {
        return n - _w + margin();
    }

    // l'immagine entra nel quadrato inscritto: centrata, niente spostamento
    private function fits(n as Number) as Boolean {
        return n <= _w - 2 * margin();
    }

    function onUpdate(dc as Dc) as Void {
        var app = getApp();
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();
        var bmp = app.images.get(_key);
        var w = dc.getWidth();
        var h = dc.getHeight();
        _w = w;
        if (bmp == null) {
            var msg = app.images.isFailed(_key) ? (WatchUi.loadResource(Rez.Strings.Missing) as String)
                                                 : (WatchUi.loadResource(Rez.Strings.Loading) as String);
            (app.rich as RichText).drawWrapped(dc, msg, w / 2, h / 2 - 20, 260, 2);
            return;
        }
        var b = bmp as Graphics.BufferedBitmap;
        iw = b.getWidth();
        ih = b.getHeight();
        clamp();
        var x = fits(iw) ? (w - iw) / 2 : -ox;
        var y = fits(ih) ? (h - ih) / 2 : -oy;
        dc.drawBitmap(x, y, b);
        // barre di posizione (dentro il quadrato inscritto, visibili)
        var m = margin();
        var side = w - 2 * m;
        dc.setColor(Palette.color(4), Graphics.COLOR_TRANSPARENT);
        if (!fits(iw)) {
            var bw = side * side / iw;
            var range = maxOff(iw) - minX();
            dc.fillRectangle(m + (side - bw) * (ox - minX()) / (range > 0 ? range : 1), h - m - 6, bw, 4);
        }
        if (!fits(ih)) {
            var bh = side * side / ih;
            var range = maxOff(ih) - minX();
            dc.fillRectangle(w - m - 6, m + (side - bh) * (oy - minX()) / (range > 0 ? range : 1), 4, bh);
        }
    }

    function clamp() as Void {
        var mx = maxOff(iw);
        var my = maxOff(ih);
        if (ox > mx) { ox = mx; }
        if (oy > my) { oy = my; }
        if (ox < minX()) { ox = minX(); }
        if (oy < minX()) { oy = minX(); }
    }

    function atLeft() as Boolean {
        return fits(iw) || ox <= minX();
    }

    function pan(dx as Number, dy as Number) as Void {
        clamp();
        ox += dx;
        oy += dy;
        WatchUi.requestUpdate();
    }
}

class ZoomDelegate extends WatchUi.InputDelegate {
    private var _view as ZoomView;
    private var _last as Array<Number> or Null = null;

    function initialize(v as ZoomView) {
        InputDelegate.initialize();
        _view = v;
    }

    function onSwipe(evt as WatchUi.SwipeEvent) as Boolean {
        var d = evt.getDirection();
        if (d == WatchUi.SWIPE_LEFT) {
            _view.pan(150, 0);
        } else if (d == WatchUi.SWIPE_RIGHT) {
            if (_view.atLeft()) {
                WatchUi.popView(WatchUi.SLIDE_DOWN);
            } else {
                _view.pan(-150, 0);
            }
        } else if (d == WatchUi.SWIPE_UP) {
            _view.pan(0, 150);
        } else if (d == WatchUi.SWIPE_DOWN) {
            _view.pan(0, -150);
        }
        return true;
    }

    // pressione prolungata: orologio (vedi holdToClock)
    function onHold(evt as WatchUi.ClickEvent) as Boolean {
        _last = null;
        return holdToClock();
    }

    function onDrag(evt as WatchUi.DragEvent) as Boolean {
        var c = evt.getCoordinates();
        var t = evt.getType();
        if (t == WatchUi.DRAG_TYPE_START) {
            _last = [c[0], c[1]];
        } else if (_last != null) {
            var l = _last as Array<Number>;
            _view.pan(l[0] - c[0], l[1] - c[1]);
            _last = [c[0], c[1]];
            if (t == WatchUi.DRAG_TYPE_STOP) {
                _last = null;
            }
        }
        return true;
    }

    // pulsante in alto (pressione fisica): orologio, oppure sposta in basso
    function onKeyPressed(evt as WatchUi.KeyEvent) as Boolean {
        if (evt.getKey() != WatchUi.KEY_ENTER) {
            return false;
        }
        if (isClockKey(evt)) {
            showClock();
        } else {
            _view.pan(0, 150);
        }
        return true;
    }

    function onKey(evt as WatchUi.KeyEvent) as Boolean {
        var k = evt.getKey();
        if (k == WatchUi.KEY_ESC) {
            WatchUi.popView(WatchUi.SLIDE_DOWN);
            return true;
        }
        return false;
    }
}
