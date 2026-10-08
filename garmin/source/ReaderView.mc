import Toybox.Graphics;
import Toybox.Lang;
import Toybox.WatchUi;

// Lettura di una sezione, una pagina alla volta (pagine già impaginate dalla pipeline).
class ReaderView extends WatchUi.View {
    const T_TEXT = 0;
    const T_IMAGE = 1;
    const T_RECT = 2;

    var section as Section;
    var page as Number;
    // elementi della pagina corrente: [tipo, ...]
    private var _items as Array<Array> or Null = null;
    private var _missing as Boolean = false;

    function initialize(sec as Section, p as Number) {
        View.initialize();
        section = sec;
        page = p;
    }

    function onShow() as Void {
        var app = getApp();
        app.store.pinned = ["idx", section.key()] as Array<String>;
        if (app.sync.state == ST_OFFLINE) {
            // riprova: il telefono potrebbe essere tornato raggiungibile
            app.startSync();
        }
        load();
    }

    function onHide() as Void {
        getApp().savePosition(section.id, page);
    }

    // ------------------------------------------------------------- caricamento
    function load() as Void {
        var app = getApp();
        _items = null;
        _missing = false;
        var n = section.chunkFor(page);
        var chunk = app.store.get(section.key(), n, section.hash);
        if (chunk == null) {
            app.sync.request(section.key(), n, section.hash, method(:onChunk), true);
            WatchUi.requestUpdate();
            return;
        }
        parse(chunk as String, page - section.starts[n]);
        Mem.log("pagina " + section.id + ":" + page);
        prefetch(n + 1);
        WatchUi.requestUpdate();
    }

    private function prefetch(n as Number) as Void {
        if (n >= section.starts.size()) {
            return;
        }
        var app = getApp();
        if (app.store.get(section.key(), n, section.hash) == null) {
            app.sync.request(section.key(), n, section.hash, method(:onPrefetch), false);
        }
    }

    function onPrefetch(key, n, total, hash, data) as Void {
        if (data != null) {
            getApp().store.put(key as String, n as Number, total as Number, hash as String, data as String);
        }
    }

    function onChunk(key, n, total, hash, data) as Void {
        if (data == null) {
            _missing = true;
            WatchUi.requestUpdate();
            return;
        }
        var app = getApp();
        app.store.put(key as String, n as Number, total as Number, hash as String, data as String);
        if ((n as Number) == section.chunkFor(page)) {
            parse(data as String, page - section.starts[n as Number]);
            Mem.log("pagina " + section.id + ":" + page + " (dal telefono)");
            prefetch((n as Number) + 1);
        }
        WatchUi.requestUpdate();
    }

    // Estrae la k-esima pagina dal pezzo e ne analizza gli elementi.
    private function parse(chunk as String, k as Number) as Void {
        var start = 0;
        if (chunk.length() >= 2 && chunk.substring(0, 2).equals("P\n")) {
            start = 2;
        }
        var rest = chunk.substring(start, chunk.length()) as String;
        var pages = Util.split(rest, "\nP\n");
        if (k < 0 || k >= pages.size()) {
            _items = [] as Array<Array>;
            return;
        }
        var lines = Util.split(pages[k], "\n");
        pages = null;
        var items = [] as Array<Array>;
        for (var i = 0; i < lines.size(); i++) {
            var l = lines[i];
            if (l.length() < 2) {
                continue;
            }
            var t = l.substring(0, 1);
            var body = l.substring(1, l.length()) as String;
            if (t.equals("T")) {
                var f = Util.splitN(body, ",", 3);
                if (f.size() == 3) {
                    items.add([T_TEXT, Util.toNum(f[0]), Util.toNum(f[1]), f[2]]);
                }
            } else if (t.equals("I")) {
                var f = Util.splitN(body, ",", 7);
                if (f.size() >= 6) {
                    items.add([T_IMAGE, Util.toNum(f[0]), Util.toNum(f[1]), Util.toNum(f[2]), Util.toNum(f[3]),
                               Util.toNum(f[4]), f[5], f.size() > 6 ? f[6] : ""]);
                }
            } else if (t.equals("R")) {
                var f = Util.split(body, ",");
                if (f.size() == 5) {
                    items.add([T_RECT, Util.toNum(f[0]), Util.toNum(f[1]), Util.toNum(f[2]), Util.toNum(f[3]),
                               Util.toNum(f[4])]);
                }
            }
        }
        _items = items;
    }

    // ------------------------------------------------------------- disegno
    function onUpdate(dc as Dc) as Void {
        var app = getApp();
        var rt = app.rich as RichText;
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();
        var w = dc.getWidth();
        var h = dc.getHeight();
        if (_items == null) {
            var msg = _missing ? (WatchUi.loadResource(Rez.Strings.Missing) as String)
                               : (WatchUi.loadResource(Rez.Strings.Loading) as String);
            rt.drawWrapped(dc, msg, w / 2, h / 2 - 20, 260, _missing ? 6 : 2);
        } else {
            var items = _items as Array<Array>;
            for (var i = 0; i < items.size(); i++) {
                var it = items[i];
                var t = it[0] as Number;
                if (t == T_TEXT) {
                    rt.draw(dc, it[1] as Number, it[2] as Number, it[3] as String);
                } else if (t == T_RECT) {
                    dc.setColor(Palette.color(it[5] as Number), Graphics.COLOR_TRANSPARENT);
                    dc.fillRectangle(it[1] as Number, it[2] as Number, it[3] as Number, it[4] as Number);
                } else {
                    drawImage(dc, app, it);
                }
            }
        }
        // numero di pagina e avanzamento
        dc.setColor(Palette.color(2), Graphics.COLOR_TRANSPARENT);
        dc.drawText(w / 2, 362, rt.small, (page + 1).toString() + "/" + section.pages, Graphics.TEXT_JUSTIFY_CENTER);
        if (section.pages > 1) {
            var deg = 300 * page / (section.pages - 1);
            dc.setPenWidth(3);
            dc.setColor(0x333333, Graphics.COLOR_TRANSPARENT);
            dc.drawArc(w / 2, h / 2, w / 2 - 3, Graphics.ARC_CLOCKWISE, 240, -60);
            dc.setColor(Palette.color(1), Graphics.COLOR_TRANSPARENT);
            if (deg > 0) {
                dc.drawArc(w / 2, h / 2, w / 2 - 3, Graphics.ARC_CLOCKWISE, 240, 240 - deg);
            }
            dc.setPenWidth(1);
        }
        if (app.showMemory) {
            dc.setColor(Palette.color(6), Graphics.COLOR_TRANSPARENT);
            dc.drawText(w / 2, 8, rt.small, Mem.label(), Graphics.TEXT_JUSTIFY_CENTER);
        }
    }

    private function drawImage(dc as Dc, app as NotesApp, it as Array) as Void {
        var x = it[1] as Number;
        var y = it[2] as Number;
        var iw = it[3] as Number;
        var ih = it[4] as Number;
        var sy = it[5] as Number;
        var key = it[6] as String;
        var bmp = app.images.get(key);
        if (bmp != null) {
            dc.setClip(x, y, iw, ih);
            dc.drawBitmap(x, y - sy, bmp);
            dc.clearClip();
            if ((it[7] as String).length() > 0) {
                // indicatore "tocca per ingrandire"
                dc.setColor(Palette.color(4), Graphics.COLOR_TRANSPARENT);
                dc.fillPolygon([[x + iw - 10, y], [x + iw, y], [x + iw, y + 10]]);
            }
        } else {
            dc.setColor(0x333333, Graphics.COLOR_TRANSPARENT);
            dc.drawRectangle(x, y, iw, ih);
            if (app.images.isFailed(key)) {
                dc.setColor(Palette.color(6), Graphics.COLOR_TRANSPARENT);
                dc.drawText(x + iw / 2, y + ih / 2 - 10, (app.rich as RichText).small, "×", Graphics.TEXT_JUSTIFY_CENTER);
            }
        }
    }

    // ------------------------------------------------------------- navigazione
    function go(delta as Number) as Boolean {
        var p = page + delta;
        if (p < 0 || p >= section.pages) {
            return false;
        }
        page = p;
        getApp().savePosition(section.id, page);
        load();
        return true;
    }

    // immagine con zoom sotto il tocco
    function zoomAt(x as Number, y as Number) as String or Null {
        if (_items == null) {
            return null;
        }
        var items = _items as Array<Array>;
        for (var i = 0; i < items.size(); i++) {
            var it = items[i];
            if ((it[0] as Number) == T_IMAGE && (it[7] as String).length() > 0) {
                if (x >= it[1] && x < (it[1] as Number) + (it[3] as Number)
                    && y >= it[2] && y < (it[2] as Number) + (it[4] as Number)) {
                    return it[7] as String;
                }
            }
        }
        return null;
    }
}

class ReaderDelegate extends WatchUi.BehaviorDelegate {
    private var _view as ReaderView;

    function initialize(v as ReaderView) {
        BehaviorDelegate.initialize();
        _view = v;
    }

    function onNextPage() as Boolean {
        _view.go(1);
        return true;
    }

    function onPreviousPage() as Boolean {
        _view.go(-1);
        return true;
    }

    // pulsante in alto: pagina successiva
    function onSelect() as Boolean {
        _view.go(1);
        return true;
    }

    function onTap(evt as WatchUi.ClickEvent) as Boolean {
        var c = evt.getCoordinates();
        var z = _view.zoomAt(c[0], c[1]);
        if (z != null) {
            var v = new ZoomView(z as String);
            WatchUi.pushView(v, new ZoomDelegate(v), WatchUi.SLIDE_UP);
            return true;
        }
        // metà superiore: indietro, metà inferiore: avanti
        _view.go(c[1] < 195 ? -1 : 1);
        return true;
    }

    function onMenu() as Boolean {
        showMainMenu();
        return true;
    }

    // pressione prolungata sullo schermo: stesso menu
    function onHold(evt as WatchUi.ClickEvent) as Boolean {
        showMainMenu();
        return true;
    }
}
