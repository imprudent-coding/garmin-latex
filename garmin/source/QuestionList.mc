import Toybox.Graphics;
import Toybox.Lang;
import Toybox.System;
import Toybox.WatchUi;

// Elenco unico di tutte le sezioni (domande), raggruppate per capitolo.
//
// - righe compatte su una riga (font piccolo, id della domanda in evidenza);
// - la voce selezionata è al centro, espansa con il titolo completo;
// - swipe su/giù: voce precedente/successiva; trascinamento: scorrimento veloce;
// - swipe sinistra/destra: gruppo successivo/precedente;
// - tocco su una voce: la seleziona, secondo tocco (o pulsante): la apre.
// Disposizione identica all'anteprima pipeline/gwnotes/preview.py (render_index).
class QuestionListView extends WatchUi.View {
    const ROW_H = 30;
    const HEAD_H = 30;
    const NARROW_DY = 95;
    const T_HEAD = 0;
    const T_SEC = 1;

    // righe: [tipo, Chapter o Section, indice del capitolo]
    private var _rows as Array<Array> = [] as Array<Array>;
    private var _selectable as Array<Number> = [] as Array<Number>;
    var sel as Number = 0;              // posizione in _selectable
    private var _version as String = "";
    // rettangoli disegnati: [top, bottom, posizione in _selectable]
    private var _hits as Array<Array<Number>> = [] as Array<Array<Number>>;

    function initialize() {
        View.initialize();
    }

    function onShow() as Void {
        rebuild();
        WatchUi.requestUpdate();
    }

    // Ricostruisce le righe se l'indice è cambiato.
    function rebuild() as Void {
        var idx = getApp().index;
        if (idx == null) {
            _rows = [] as Array<Array>;
            _selectable = [] as Array<Number>;
            _version = "";
            return;
        }
        var ix = idx as Index;
        if (ix.version.equals(_version) && _rows.size() > 0) {
            return;
        }
        _version = ix.version;
        _rows = [] as Array<Array>;
        _selectable = [] as Array<Number>;
        var chs = ix.chapters;
        for (var c = 0; c < chs.size(); c++) {
            var ch = chs[c];
            if (ch.hLine != null && chs.size() > 1) {
                _rows.add([T_HEAD, ch, c]);
            }
            for (var s = 0; s < ch.sections.size(); s++) {
                _selectable.add(_rows.size());
                _rows.add([T_SEC, ch.sections[s], c]);
            }
        }
        // riparte dall'ultima voce aperta
        sel = 0;
        var last = getApp().store.getValue("sel");
        if (last instanceof Lang.String) {
            for (var i = 0; i < _selectable.size(); i++) {
                if ((_rows[_selectable[i]][1] as Section).id.equals(last as String)) {
                    sel = i;
                    break;
                }
            }
        }
        Mem.log("elenco: " + _selectable.size() + " voci");
    }

    function count() as Number {
        return _selectable.size();
    }

    private function selHeight(sec as Section) as Number {
        return 14 + sec.lines.size() * 34 + FontInfo.SMALL_LINE + 6;
    }

    private function rowHeight(r as Array) as Number {
        return (r[0] as Number) == T_HEAD ? HEAD_H : ROW_H;
    }

    function onUpdate(dc as Dc) as Void {
        rebuild();
        var app = getApp();
        var rt = app.rich as RichText;
        var w = dc.getWidth();
        var h = dc.getHeight();
        var cx = w / 2;
        var cy = h / 2;
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();
        _hits = [] as Array<Array<Number>>;
        dc.setColor(Palette.color(2), Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, 6, rt.small, app.status, Graphics.TEXT_JUSTIFY_CENTER);
        if (_selectable.size() == 0) {
            rt.drawWrapped(dc, WatchUi.loadResource(Rez.Strings.NoIndex) as String, cx, 150, 280, 0);
            return;
        }
        if (sel >= _selectable.size()) {
            sel = _selectable.size() - 1;
        }
        var si = _selectable[sel];
        var sec = _rows[si][1] as Section;

        // voce selezionata, espansa
        var sh = selHeight(sec);
        var top = cy - sh / 2;
        dc.setColor(0x1A1A1A, Graphics.COLOR_TRANSPARENT);
        dc.fillRoundedRectangle(20, top, w - 40, sh, 14);
        rt.baseColor = 1;
        var y = top + 8 + FontInfo.BODY_ASCENT;
        for (var k = 0; k < sec.lines.size(); k++) {
            var lw = k < sec.widths.size() ? sec.widths[k] : 200;
            rt.draw(dc, cx - lw / 2, y, sec.lines[k]);
            y += 34;
        }
        rt.baseColor = 0;
        var cached = app.store.hashOf(sec.key());
        var mark = (cached != null && (cached as String).equals(sec.hash)) ? "  ●" : "";
        dc.setColor(Palette.color(2), Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, y - FontInfo.BODY_ASCENT, rt.small, sec.pages.toString() + " pagine" + mark,
            Graphics.TEXT_JUSTIFY_CENTER);
        _hits.add([top, top + sh, sel]);

        // righe sopra
        var yy = top;
        for (var i = si - 1; i >= 0; i--) {
            var rh = rowHeight(_rows[i]);
            yy -= rh;
            if (yy < 28) {
                break;
            }
            drawRow(dc, rt, i, yy, cx, cy);
        }
        // righe sotto
        yy = top + sh;
        for (var i = si + 1; i < _rows.size(); i++) {
            var rh = rowHeight(_rows[i]);
            if (yy + rh > 352) {
                break;
            }
            drawRow(dc, rt, i, yy, cx, cy);
            yy += rh;
        }

        // posizione: contatore e arco a destra
        dc.setColor(Palette.color(2), Graphics.COLOR_TRANSPARENT);
        var pos = (sel + 1).toString() + "/" + _selectable.size();
        if (sec.qid.length() > 0) {
            pos = sec.qid + " · " + pos;
        }
        dc.drawText(cx, 362, rt.small, pos, Graphics.TEXT_JUSTIFY_CENTER);
        var n = _selectable.size();
        dc.setPenWidth(3);
        dc.setColor(0x333333, Graphics.COLOR_TRANSPARENT);
        dc.drawArc(cx, cy, cx - 3, Graphics.ARC_COUNTER_CLOCKWISE, -40, 40);
        var a = 40 - (n > 1 ? 80 * sel / (n - 1) : 0);
        dc.setPenWidth(6);
        dc.setColor(Palette.color(1), Graphics.COLOR_TRANSPARENT);
        dc.drawArc(cx, cy, cx - 3, Graphics.ARC_COUNTER_CLOCKWISE, a - 3, a + 3);
        dc.setPenWidth(1);
        if (app.showMemory) {
            dc.setColor(Palette.color(6), Graphics.COLOR_TRANSPARENT);
            dc.drawText(cx, 30, rt.small, Mem.label(), Graphics.TEXT_JUSTIFY_CENTER);
        }
    }

    private function drawRow(dc as Dc, rt as RichText, i as Number, rtop as Number, cx as Number, cy as Number) as Void {
        var r = _rows[i];
        var rh = rowHeight(r);
        var base = rtop + rh - 9;
        if ((r[0] as Number) == T_HEAD) {
            var ch = r[1] as Chapter;
            dc.setColor(0x3C3C3C, Graphics.COLOR_TRANSPARENT);
            dc.drawLine(cx - ch.hWidth / 2, rtop + 3, cx + ch.hWidth / 2, rtop + 3);
            rt.draw(dc, cx - ch.hWidth / 2, base, ch.hLine as String);
            return;
        }
        var sec = r[1] as Section;
        var mid = rtop + rh / 2;
        var k = (mid - cy > NARROW_DY || cy - mid > NARROW_DY) ? 1 : 0;
        if (sec.cLines != null && (sec.cLines as Array).size() > k) {
            var lw = (sec.cWidths as Array<Number>)[k];
            rt.draw(dc, cx - lw / 2, base, (sec.cLines as Array<String>)[k]);
        } else {
            // indice senza righe compatte (bundle vecchio): prima riga del titolo
            var lw = sec.widths.size() > 0 ? sec.widths[0] : 200;
            rt.draw(dc, cx - lw / 2, base, sec.lines[0]);
        }
        _hits.add([rtop, rtop + rh, _selectable.indexOf(i)]);
    }

    // ------------------------------------------------------------- navigazione
    function move(delta as Number) as Void {
        var n = _selectable.size();
        if (n == 0) {
            return;
        }
        var s = sel + delta;
        if (s < 0) {
            s = 0;
        }
        if (s >= n) {
            s = n - 1;
        }
        if (s != sel) {
            sel = s;
            WatchUi.requestUpdate();
        }
    }

    // Prima voce del gruppo successivo (dir = 1) o del gruppo corrente/precedente (dir = -1).
    function jumpGroup(dir as Number) as Void {
        var n = _selectable.size();
        if (n == 0) {
            return;
        }
        var cur = _rows[_selectable[sel]][2] as Number;
        if (dir > 0) {
            for (var i = sel + 1; i < n; i++) {
                if ((_rows[_selectable[i]][2] as Number) != cur) {
                    sel = i;
                    break;
                }
            }
        } else {
            // se non sei sulla prima voce del gruppo, vai lì; altrimenti al gruppo precedente
            var first = sel;
            while (first > 0 && (_rows[_selectable[first - 1]][2] as Number) == cur) {
                first -= 1;
            }
            if (first != sel) {
                sel = first;
            } else if (first > 0) {
                var prev = _rows[_selectable[first - 1]][2] as Number;
                sel = first - 1;
                while (sel > 0 && (_rows[_selectable[sel - 1]][2] as Number) == prev) {
                    sel -= 1;
                }
            }
        }
        WatchUi.requestUpdate();
    }

    function openSelected() as Void {
        if (_selectable.size() == 0) {
            return;
        }
        var sec = _rows[_selectable[sel]][1] as Section;
        getApp().store.setValue("sel", sec.id);
        openReader(sec, 0);
    }

    function tapAt(y as Number) as Boolean {
        for (var i = 0; i < _hits.size(); i++) {
            var r = _hits[i];
            if (y >= r[0] && y < r[1] && r[2] >= 0) {
                if (r[2] == sel) {
                    openSelected();
                } else {
                    sel = r[2];
                    WatchUi.requestUpdate();
                }
                return true;
            }
        }
        return false;
    }
}

function openReader(sec as Section, page as Number) as Void {
    var v = new ReaderView(sec, page);
    WatchUi.pushView(v, new ReaderDelegate(v), WatchUi.SLIDE_LEFT);
}

class QuestionListDelegate extends WatchUi.BehaviorDelegate {
    const DRAG_STEP = 30;  // pixel di trascinamento per voce

    private var _view as QuestionListView;
    private var _dragY as Number or Null = null;
    private var _dragMovedAt as Number = 0;

    function initialize(v as QuestionListView) {
        BehaviorDelegate.initialize();
        _view = v;
    }

    function onNextPage() as Boolean {
        if (!justDragged()) {
            _view.move(1);
        }
        return true;
    }

    function onPreviousPage() as Boolean {
        if (!justDragged()) {
            _view.move(-1);
        }
        return true;
    }

    function onSwipe(evt as WatchUi.SwipeEvent) as Boolean {
        if (justDragged()) {
            return true;
        }
        var d = evt.getDirection();
        if (d == WatchUi.SWIPE_LEFT) {
            _view.jumpGroup(1);
            return true;
        }
        if (d == WatchUi.SWIPE_RIGHT) {
            _view.jumpGroup(-1);
            return true;
        }
        return false; // su/giù: onNextPage/onPreviousPage
    }

    // trascinamento verticale: una voce ogni DRAG_STEP pixel
    function onDrag(evt as WatchUi.DragEvent) as Boolean {
        var c = evt.getCoordinates();
        var t = evt.getType();
        if (t == WatchUi.DRAG_TYPE_START) {
            _dragY = c[1];
            return true;
        }
        if (_dragY == null) {
            return false;
        }
        var dy = (_dragY as Number) - c[1];
        var steps = dy / DRAG_STEP;
        if (steps != 0) {
            _view.move(steps);
            _dragY = (_dragY as Number) - steps * DRAG_STEP;
            _dragMovedAt = System.getTimer();
        }
        if (t == WatchUi.DRAG_TYPE_STOP) {
            _dragY = null;
        }
        return true;
    }

    // dopo un trascinamento il sistema può generare anche uno swipe: va ignorato
    private function justDragged() as Boolean {
        return System.getTimer() - _dragMovedAt < 400;
    }

    // pulsante in alto: orologio (o apre la domanda, se l'orologio è disattivato)
    function onSelect() as Boolean {
        if (getApp().clockButton()) {
            showClock();
        } else {
            _view.openSelected();
        }
        return true;
    }

    function onTap(evt as WatchUi.ClickEvent) as Boolean {
        if (justDragged()) {
            return true;
        }
        var c = evt.getCoordinates();
        return _view.tapAt(c[1]);
    }

    function onMenu() as Boolean {
        showMainMenu();
        return true;
    }

    function onHold(evt as WatchUi.ClickEvent) as Boolean {
        showMainMenu();
        return true;
    }
}
