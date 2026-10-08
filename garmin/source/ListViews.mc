import Toybox.Graphics;
import Toybox.Lang;
import Toybox.WatchUi;

// Lista verticale con l'elemento selezionato al centro dello schermo rotondo.
class BaseListView extends WatchUi.View {
    var selected as Number = 0;
    // rettangoli disegnati: [top, bottom, indice]
    var hits as Array<Array<Number>> = [] as Array<Array<Number>>;

    function initialize() {
        View.initialize();
    }

    // da ridefinire
    function count() as Number {
        return 0;
    }
    function itemLines(i as Number) as Array<String> {
        return [] as Array<String>;
    }
    function itemWidths(i as Number) as Array<Number> {
        return [] as Array<Number>;
    }
    function itemSub(i as Number) as String or Null {
        return null;
    }
    function header() as String {
        return "";
    }
    function emptyText() as String {
        return "";
    }
    function open(i as Number) as Void {
    }

    function itemHeight(i as Number) as Number {
        var h = itemLines(i).size() * (FontInfo.BODY_LINE + 2) + 14;
        if (itemSub(i) != null) {
            h += FontInfo.SMALL_LINE;
        }
        return h;
    }

    function onUpdate(dc as Dc) as Void {
        var app = getApp();
        var rt = app.rich as RichText;
        dc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        dc.clear();
        hits = [] as Array<Array<Number>>;
        var w = dc.getWidth();
        var cx = w / 2;
        // intestazione e stato della sincronizzazione
        dc.setColor(Palette.color(2), Graphics.COLOR_TRANSPARENT);
        dc.drawText(cx, 14, rt.small, app.status, Graphics.TEXT_JUSTIFY_CENTER);
        var n = count();
        if (n == 0) {
            rt.drawWrapped(dc, emptyText(), cx, 150, 280, 0);
            drawMemory(dc, rt);
            return;
        }
        if (selected >= n) {
            selected = n - 1;
        }
        // elemento selezionato centrato verticalmente
        var h = itemHeight(selected);
        var top = dc.getHeight() / 2 - h / 2;
        drawItem(dc, rt, selected, top, true);
        // sopra
        var y = top;
        for (var i = selected - 1; i >= 0 && y > 40; i--) {
            var hi = itemHeight(i);
            y -= hi;
            drawItem(dc, rt, i, y, false);
        }
        // sotto
        y = top + h;
        for (var i = selected + 1; i < n && y < dc.getHeight() - 30; i++) {
            drawItem(dc, rt, i, y, false);
            y += itemHeight(i);
        }
        // separatori della selezione
        dc.setColor(Palette.color(1), Graphics.COLOR_TRANSPARENT);
        dc.fillRectangle(cx - 60, top + 2, 120, 2);
        dc.fillRectangle(cx - 60, top + h - 4, 120, 2);
        // titolo della lista
        var hd = header();
        if (hd.length() > 0) {
            dc.setColor(Palette.color(1), Graphics.COLOR_TRANSPARENT);
            dc.drawText(cx, 36, rt.small, hd, Graphics.TEXT_JUSTIFY_CENTER);
        }
        drawMemory(dc, rt);
    }

    private function drawItem(dc as Dc, rt as RichText, i as Number, top as Number, sel as Boolean) as Void {
        var lines = itemLines(i);
        var widths = itemWidths(i);
        var cx = dc.getWidth() / 2;
        rt.baseColor = sel ? 1 : 0;
        var y = top + 8 + FontInfo.BODY_ASCENT;
        for (var k = 0; k < lines.size(); k++) {
            var lw = k < widths.size() ? widths[k] : 200;
            rt.draw(dc, cx - lw / 2, y, lines[k]);
            y += FontInfo.BODY_LINE + 2;
        }
        rt.baseColor = 0;
        var sub = itemSub(i);
        if (sub != null) {
            dc.setColor(Palette.color(2), Graphics.COLOR_TRANSPARENT);
            dc.drawText(cx, y - FontInfo.BODY_ASCENT, rt.small, sub, Graphics.TEXT_JUSTIFY_CENTER);
        }
        hits.add([top, top + itemHeight(i), i]);
    }

    function drawMemory(dc as Dc, rt as RichText) as Void {
        if (getApp().showMemory) {
            dc.setColor(Palette.color(6), Graphics.COLOR_TRANSPARENT);
            dc.drawText(dc.getWidth() / 2, dc.getHeight() - 30, rt.small, Mem.label(), Graphics.TEXT_JUSTIFY_CENTER);
        }
    }

    function move(delta as Number) as Void {
        var n = count();
        if (n == 0) {
            return;
        }
        selected = (selected + delta + n) % n;
        WatchUi.requestUpdate();
    }

    function tapAt(y as Number) as Boolean {
        for (var i = 0; i < hits.size(); i++) {
            var r = hits[i];
            if (y >= r[0] && y < r[1]) {
                if (r[2] == selected) {
                    open(selected);
                } else {
                    selected = r[2];
                    WatchUi.requestUpdate();
                }
                return true;
            }
        }
        return false;
    }
}

class ChapterListView extends BaseListView {
    function initialize() {
        BaseListView.initialize();
    }

    function onShow() as Void {
        WatchUi.requestUpdate();
    }

    private function chapters() as Array<Chapter> {
        var idx = getApp().index;
        return idx == null ? ([] as Array<Chapter>) : (idx as Index).chapters;
    }

    function count() as Number {
        return chapters().size();
    }
    function itemLines(i as Number) as Array<String> {
        return chapters()[i].lines;
    }
    function itemWidths(i as Number) as Array<Number> {
        return chapters()[i].widths;
    }
    function itemSub(i as Number) as String or Null {
        var n = chapters()[i].sections.size();
        return n == 1 ? "1 sezione" : n + " sezioni";
    }
    function header() as String {
        var idx = getApp().index;
        return idx == null ? "" : (idx as Index).title;
    }
    function emptyText() as String {
        return WatchUi.loadResource(Rez.Strings.NoIndex) as String;
    }
    function open(i as Number) as Void {
        var ch = chapters()[i];
        if (ch.sections.size() == 1) {
            openReader(ch.sections[0], 0);
            return;
        }
        var v = new SectionListView(ch);
        WatchUi.pushView(v, new ListDelegate(v), WatchUi.SLIDE_LEFT);
    }
}

class SectionListView extends BaseListView {
    private var _chapter as Chapter;

    function initialize(ch as Chapter) {
        BaseListView.initialize();
        _chapter = ch;
    }

    function count() as Number {
        return _chapter.sections.size();
    }
    function itemLines(i as Number) as Array<String> {
        return _chapter.sections[i].lines;
    }
    function itemWidths(i as Number) as Array<Number> {
        return _chapter.sections[i].widths;
    }
    function itemSub(i as Number) as String or Null {
        var s = _chapter.sections[i];
        var cached = getApp().store.hashOf(s.key());
        var mark = (cached != null && (cached as String).equals(s.hash)) ? " ●" : "";
        return s.pages + " pagine" + mark;
    }
    function header() as String {
        return "";
    }
    function open(i as Number) as Void {
        openReader(_chapter.sections[i], 0);
    }
}

function openReader(sec as Section, page as Number) as Void {
    var v = new ReaderView(sec, page);
    WatchUi.pushView(v, new ReaderDelegate(v), WatchUi.SLIDE_LEFT);
}

class ListDelegate extends WatchUi.BehaviorDelegate {
    private var _view as BaseListView;

    function initialize(v as BaseListView) {
        BehaviorDelegate.initialize();
        _view = v;
    }

    function onNextPage() as Boolean {
        _view.move(1);
        return true;
    }

    function onPreviousPage() as Boolean {
        _view.move(-1);
        return true;
    }

    function onSelect() as Boolean {
        if (_view.count() > 0) {
            _view.open(_view.selected);
        }
        return true;
    }

    function onTap(evt as WatchUi.ClickEvent) as Boolean {
        var c = evt.getCoordinates();
        return _view.tapAt(c[1]);
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
