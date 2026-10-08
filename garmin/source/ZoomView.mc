import Toybox.Graphics;
import Toybox.Lang;
import Toybox.WatchUi;

// Versione ingrandita di una figura/equazione, spostabile con swipe o trascinamento.
class ZoomView extends WatchUi.View {
    private var _key as String;
    var ox as Number = 0;
    var oy as Number = 0;
    var iw as Number = 0;
    var ih as Number = 0;

    function initialize(key as String) {
        View.initialize();
        _key = key;
    }

    function onUpdate(dc as Dc) as Void {
        var app = getApp();
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();
        var bmp = app.images.get(_key);
        var w = dc.getWidth();
        var h = dc.getHeight();
        if (bmp == null) {
            var msg = app.images.isFailed(_key) ? (WatchUi.loadResource(Rez.Strings.Missing) as String)
                                                 : (WatchUi.loadResource(Rez.Strings.Loading) as String);
            (app.rich as RichText).drawWrapped(dc, msg, w / 2, h / 2 - 20, 260, 2);
            return;
        }
        var b = bmp as Graphics.BufferedBitmap;
        iw = b.getWidth();
        ih = b.getHeight();
        clamp(w, h);
        // immagine più piccola dello schermo: centrata
        var x = iw < w ? (w - iw) / 2 : -ox;
        var y = ih < h ? (h - ih) / 2 : -oy;
        dc.drawBitmap(x, y, b);
        // barre di posizione
        dc.setColor(Palette.color(4), Graphics.COLOR_TRANSPARENT);
        if (iw > w) {
            var bw = w * w / iw / 2;
            dc.fillRectangle(w / 4 + (w / 2 - bw) * ox / (iw - w), h - 24, bw, 4);
        }
        if (ih > h) {
            var bh = h * h / ih / 2;
            dc.fillRectangle(w - 24, h / 4 + (h / 2 - bh) * oy / (ih - h), 4, bh);
        }
    }

    function clamp(w as Number, h as Number) as Void {
        var mx = iw - w;
        var my = ih - h;
        if (ox > mx) { ox = mx; }
        if (oy > my) { oy = my; }
        if (ox < 0) { ox = 0; }
        if (oy < 0) { oy = 0; }
    }

    function pan(dx as Number, dy as Number) as Void {
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
            if (_view.ox <= 0) {
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

    function onKey(evt as WatchUi.KeyEvent) as Boolean {
        var k = evt.getKey();
        if (k == WatchUi.KEY_ENTER) {
            if (getApp().clockButton()) {
                showClock();
            } else {
                _view.pan(0, 150);
            }
            return true;
        }
        if (k == WatchUi.KEY_ESC) {
            WatchUi.popView(WatchUi.SLIDE_DOWN);
            return true;
        }
        return false;
    }
}
