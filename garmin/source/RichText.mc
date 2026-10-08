import Toybox.Graphics;
import Toybox.Lang;
import Toybox.WatchUi;

// Disegno del testo ricco (vedi shared/FORMAT.md; riferimento: pipeline/gwnotes/preview.py).
class RichText {
    const BASE = 0xE000;
    const END_CODE = 15;
    const GAP_CODE = 16;
    const PARAM_BASE = 0x100;

    var body;
    var bold;
    var small;
    // colore (indice palette) del testo senza codice colore
    var baseColor as Number = 0;

    // pila degli stili aperti
    private var _kinds as Array<Number> = [] as Array<Number>;
    private var _params as Array<Number> = [] as Array<Number>;
    private var _xs as Array<Number> = [] as Array<Number>;
    private var _x as Number = 0;

    function initialize() {
        body = WatchUi.loadResource(Rez.Fonts.Font_body);
        bold = WatchUi.loadResource(Rez.Fonts.Font_bold);
        small = WatchUi.loadResource(Rez.Fonts.Font_small);
    }

    private function fontNow() {
        var hasBold = false;
        for (var i = 0; i < _kinds.size(); i++) {
            var k = _kinds[i];
            if (k == 3 || k == 4) {
                return small;
            }
            if (k == 1) {
                hasBold = true;
            }
        }
        return hasBold ? bold : body;
    }

    private function ascentNow() as Number {
        var f = fontNow();
        if (f == small) {
            return FontInfo.SMALL_ASCENT;
        }
        if (f == bold) {
            return FontInfo.BOLD_ASCENT;
        }
        return FontInfo.BODY_ASCENT;
    }

    private function offsetNow(depth as Number) as Number {
        var off = 0;
        for (var i = 0; i < depth; i++) {
            if (_kinds[i] == 3) {
                off -= _params[i];
            } else if (_kinds[i] == 4) {
                off += _params[i];
            }
        }
        return off;
    }

    private function colorNow(depth as Number) as Number {
        var c = baseColor;
        for (var i = 0; i < depth; i++) {
            if (_kinds[i] == 2) {
                c = _params[i];
            }
        }
        return Palette.color(c);
    }

    private function flush(dc as Dc, text as String, from as Number, to as Number, baseline as Number) as Void {
        if (to <= from) {
            return;
        }
        var run = text.substring(from, to) as String;
        var f = fontNow();
        var d = _kinds.size();
        dc.setColor(colorNow(d), Graphics.COLOR_TRANSPARENT);
        dc.drawText(_x, baseline - offsetNow(d) - ascentNow(), f, run, Graphics.TEXT_JUSTIFY_LEFT);
        _x += dc.getTextWidthInPixels(run, f);
    }

    // Testo semplice nel font piccolo, centrato, con a capo (messaggi di stato).
    function drawWrapped(dc as Dc, text as String, cx as Number, top as Number, maxw as Number, color as Number) as Number {
        var words = Util.split(text, " ");
        var line = "";
        var y = top;
        dc.setColor(Palette.color(color), Graphics.COLOR_TRANSPARENT);
        for (var i = 0; i < words.size(); i++) {
            var cand = line.length() == 0 ? words[i] : line + " " + words[i];
            if (line.length() > 0 && dc.getTextWidthInPixels(cand, small) > maxw) {
                dc.drawText(cx, y, small, line, Graphics.TEXT_JUSTIFY_CENTER);
                y += FontInfo.SMALL_LINE;
                line = words[i];
            } else {
                line = cand;
            }
        }
        if (line.length() > 0) {
            dc.drawText(cx, y, small, line, Graphics.TEXT_JUSTIFY_CENTER);
            y += FontInfo.SMALL_LINE;
        }
        return y;
    }

    // Disegna una riga con la baseline in y. Ritorna la x finale.
    function draw(dc as Dc, x as Number, baseline as Number, text as String) as Number {
        _kinds = [] as Array<Number>;
        _params = [] as Array<Number>;
        _xs = [] as Array<Number>;
        _x = x;
        var chars = text.toCharArray();
        var n = chars.size();
        var runStart = 0;
        var i = 0;
        while (i < n) {
            var c = chars[i].toNumber();
            if (c >= BASE && c < BASE + 0x100) {
                flush(dc, text, runStart, i, baseline);
                var code = c - BASE;
                if (code == END_CODE) {
                    var d = _kinds.size();
                    if (d > 0) {
                        var kind = _kinds[d - 1];
                        var param = _params[d - 1];
                        var sx = _xs[d - 1];
                        _kinds = _kinds.slice(0, d - 1);
                        _params = _params.slice(0, d - 1);
                        _xs = _xs.slice(0, d - 1);
                        decor(dc, kind, param, sx, _x, baseline - offsetNow(d - 1), colorNow(d - 1));
                    }
                    i += 1;
                } else {
                    var p = 0;
                    if (i + 1 < n) {
                        p = chars[i + 1].toNumber() - PARAM_BASE;
                    }
                    if (code == GAP_CODE) {
                        _x += p;
                    } else {
                        _kinds.add(code);
                        _params.add(p);
                        _xs.add(_x);
                    }
                    i += 2;
                }
                runStart = i;
                continue;
            }
            i += 1;
        }
        flush(dc, text, runStart, n, baseline);
        return _x;
    }

    // Decorazioni dei vettori e degli accenti (codici 5..13).
    private function decor(dc as Dc, kind as Number, p as Number, sx as Number, ex as Number, base as Number, col as Number) as Void {
        var mid = (sx + ex) / 2;
        dc.setColor(col, Graphics.COLOR_TRANSPARENT);
        dc.setPenWidth(2);
        if (kind == 5) {
            dc.fillRectangle(sx, base + p, ex - sx, 2);
        } else if (kind == 6) {
            dc.fillRectangle(sx, base + p, ex - sx, 2);
            dc.fillRectangle(sx, base + p + 4, ex - sx, 2);
        } else if (kind == 7) {
            var y = base - p;
            dc.drawLine(mid - 5, y + 4, mid, y);
            dc.drawLine(mid, y, mid + 5, y + 4);
        } else if (kind == 8) {
            dc.fillRectangle(mid - 1, base - p - 2, 3, 3);
        } else if (kind == 9) {
            dc.fillRectangle(mid - 4, base - p - 2, 3, 3);
            dc.fillRectangle(mid + 2, base - p - 2, 3, 3);
        } else if (kind == 10) {
            var y = base - p;
            dc.drawLine(mid - 6, y + 1, mid - 3, y - 2);
            dc.drawLine(mid - 3, y - 2, mid + 3, y + 1);
            dc.drawLine(mid + 3, y + 1, mid + 6, y - 2);
        } else if (kind == 11) {
            dc.fillRectangle(sx, base - p - 1, ex - sx, 2);
        } else if (kind == 12 || kind == 13) {
            var y = (kind == 12) ? base - p : base + p;
            dc.fillRectangle(sx, y - 1, ex - sx, 2);
            dc.drawLine(ex - 5, y - 4, ex - 1, y);
            dc.drawLine(ex - 1, y, ex - 5, y + 3);
        }
        dc.setPenWidth(1);
    }
}
