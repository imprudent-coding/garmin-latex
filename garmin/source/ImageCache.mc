import Toybox.Graphics;
import Toybox.Lang;
import Toybox.StringUtil;
import Toybox.System;
import Toybox.WatchUi;

// Immagini delle formule/figure: pezzi -> base64 -> [LZ, schema 2] -> RLE a 2 bit -> BufferedBitmap.
// La decodifica è incrementale (a blocchi su un timer) per non superare il
// limite di tempo di esecuzione del watchdog; si tengono in memoria poche
// bitmap alla volta (LRU).
// perché un'immagine non c'è (ImageCache.failReason)
const F_MISSING = 1;   // non ancora scaricata (telefono non disponibile): arriverà dal download
const F_DATA = 2;      // dati in cache rovinati: eliminati e riscaricati
const F_MEMORY = 3;    // memoria grafica insufficiente
const F_BROKEN = 4;    // rovinata anche dopo due nuovi download: non si riprova

class ImageCache {
    // bitmap tenute in memoria: le immagini della pagina e le strisce di uno zoom
    const MAX_BITMAPS = 8;
    const BYTES_PER_TICK = 1500;
    const LZ_PER_TICK = 4000;   // byte prodotti dalla decompressione LZ per passo

    private var _store as Store;
    private var _sync as Sync;
    private var _refs as Dictionary = {} as Dictionary;       // chiave -> BufferedBitmapReference
    private var _sizes as Dictionary = {} as Dictionary;      // chiave -> [w, h]
    private var _order as Array<String> = [] as Array<String>;
    private var _failed as Dictionary = {} as Dictionary;
    private var _repairs as Dictionary = {} as Dictionary;   // nuovi download per dati rovinati
    private var _wanted as Array<String> = [] as Array<String>;

    // stato della decodifica in corso
    private var _decKey as String or Null = null;
    private var _decBytes as ByteArray or Null = null;
    private var _decPos as Number = 0;
    private var _decX as Number = 0;
    private var _decY as Number = 0;
    private var _decW as Number = 0;
    private var _decH as Number = 0;
    private var _decRef = null;
    // immagine a colori (terzo campo 4, shared/FORMAT.md): palette letta dai dati
    private var _decColor as Boolean = false;
    private var _decPal as Array<Number> = [] as Array<Number>;
    // decompressione LZ in corso (schema 2): ingresso e posizioni
    private var _lzIn as ByteArray or Null = null;
    private var _lzI as Number = 0;
    private var _lzO as Number = 0;
    private var _ticker as Ticker;

    function initialize(store as Store, sync as Sync, ticker as Ticker) {
        _store = store;
        _sync = sync;
        _ticker = ticker;
    }

    // Bitmap pronta o null (in quel caso viene avviato il caricamento).
    function get(key as String) {
        var ref = _refs[key];
        if (ref != null) {
            var bmp = (ref as Graphics.BufferedBitmapReference).get();
            if (bmp != null) {
                _order.remove(key);
                _order.add(key);
                return bmp;
            }
            // eliminata dal pool grafico: va ricostruita
            _refs.remove(key);
            _order.remove(key);
        }
        want(key);
        return null;
    }

    function isFailed(key as String) as Boolean {
        return _failed[key] != null;
    }

    // F_MISSING, F_DATA, F_MEMORY o 0
    function failReason(key as String) as Number {
        var r = _failed[key];
        return r instanceof Lang.Number ? r as Number : 0;
    }

    function retryFailed() as Void {
        _failed = {} as Dictionary;
    }

    // Nuovo tentativo per una sola immagine (es. riaprendo lo zoom).
    function retry(key as String) as Void {
        _failed.remove(key);
    }

    private function fail(key as String, reason as Number) as Void {
        if (reason == F_DATA) {
            var n = _repairs[key] == null ? 0 : _repairs[key] as Number;
            if (n >= 2) {
                _failed[key] = F_BROKEN;
                return;
            }
            _repairs[key] = n + 1;
        }
        _failed[key] = reason;
        if (reason == F_DATA) {
            // dati rovinati (es. salvati da una versione precedente): via dalla cache, e il
            // download in sottofondo li riprende dal web
            _store.remove(key);
            getApp().prefetch.repair(key);
        } else if (reason == F_MISSING) {
            getApp().prefetch.ensure();
        }
    }

    private function want(key as String) as Void {
        var r = _failed[key];
        // mancante o da riscaricare, e intanto arrivata dal download: si riprova da sola
        if (r != null && r != F_MEMORY && r != F_BROKEN && _store.isComplete(key, "")) {
            _failed.remove(key);
            r = null;
        }
        if (r != null || key.equals(_decKey) || _wanted.indexOf(key) >= 0) {
            return;
        }
        _wanted.add(key);
        next();
    }

    // Prossima immagine da preparare: se tutti i pezzi sono in cache decodifica,
    // altrimenti chiede al telefono il primo pezzo mancante.
    private function next() as Void {
        if (_decKey != null || _wanted.size() == 0) {
            return;
        }
        var key = _wanted[0];
        var total = _store.totalOf(key);
        if (total > 0 && _store.isComplete(key, "")) {
            _wanted = _wanted.slice(1, null) as Array<String>;
            startDecode(key);
            return;
        }
        var st = _sync.state;
        if (st == ST_OFFLINE || st == ST_NOBUNDLE || st == ST_SCHEMA) {
            // telefono non disponibile (o con un bundle più vecchio dell'indice preso dal
            // web): niente richiesta, che fallirebbe subito; l'immagine arriva dal web
            _wanted = _wanted.slice(1, null) as Array<String>;
            fail(key, F_MISSING);
            WatchUi.requestUpdate();
            next();
            return;
        }
        // trova il primo pezzo mancante
        var n = 0;
        if (total > 0) {
            for (var i = 0; i < total; i++) {
                if (_store.get(key, i, "") == null) {
                    n = i;
                    break;
                }
            }
        }
        _sync.requestBatch(key, n, total > 0 ? total - n : MAX_BATCH, "", method(:onChunk));
    }

    function onChunk(key, n, total, hash, data) as Void {
        if (data == null) {
            fail(key as String, F_MISSING);
            _wanted.remove(key);
            next();
            WatchUi.requestUpdate();
            return;
        }
        var d = data as Array;
        for (var i = 0; i < d.size(); i++) {
            _store.put(key as String, (n as Number) + i, total as Number, hash as String, d[i] as String);
        }
        var after = (n as Number) + d.size();
        if (after < (total as Number)) {
            _sync.requestBatch(key as String, after, (total as Number) - after, hash as String, method(:onChunk));
        } else {
            next();
        }
    }

    private function startDecode(key as String) as Void {
        var s = _store.getAll(key, "", "");
        if (s == null) {
            fail(key, F_DATA);
            return;
        }
        var bar = s.find("|");
        if (bar == null) {
            fail(key, F_DATA);
            return;
        }
        var head = Util.split(s.substring(0, bar) as String, ",");
        var w = Util.toNum(head[0]);
        var h = Util.toNum(head[1]);
        var b64 = s.substring(bar + 1, s.length()) as String;
        s = null;
        Mem.log("immagine " + key + " " + w + "x" + h + " prima della decodifica");
        var bytes = StringUtil.convertEncodedString(b64, {
            :fromRepresentation => StringUtil.REPRESENTATION_STRING_BASE64,
            :toRepresentation => StringUtil.REPRESENTATION_BYTE_ARRAY
        }) as ByteArray;
        b64 = null;
        // immagine a colori: la palette è all'inizio dei dati compressi, quindi la bitmap
        // si crea dopo la decompressione (startColor)
        var color = head.size() >= 4 && head[2].equals("4");
        // schema 2: "<w>,<h>,2,<byte RLE>" = RLE compresso con LZ, da decomprimere prima
        var lzIn = null;
        if (head.size() >= 4) {
            var rawLen = Util.toNum(head[3]);
            if (rawLen <= 0) {
                fail(key, F_DATA);
                return;
            }
            lzIn = bytes;
            bytes = new [rawLen]b;
        }
        var ref = null;
        if (!color) {
            ref = newBitmap(w, h, Palette.LEVELS);
            if (ref == null) {
                fail(key, F_MEMORY);
                return;
            }
        }
        _decKey = key;
        _decColor = color;
        _decH = h;
        _decBytes = bytes;
        _decPos = 0;
        _decX = 0;
        _decY = 0;
        _decW = w;
        _decRef = ref;
        _lzIn = lzIn;
        _lzI = 0;
        _lzO = 0;
        _sizes[key] = [w, h];
        _ticker.schedule("img", 50, method(:onDecodeTick), true);
    }

    function onDecodeTick() as Void {
        if (_decKey == null) {
            _ticker.cancel("img");
            return;
        }
        if (_lzIn != null) {
            // prima fase: decompressione LZ, a passi
            var r = lzStep();
            if (r < 0) {
                abortDecode(F_DATA);
            } else if (r > 0) {
                _lzIn = null;
                if (_decColor) {
                    var c = startColor();
                    if (c != 0) {
                        abortDecode(c);
                    }
                }
            }
            return;
        }
        var bmp = (_decRef as Graphics.BufferedBitmapReference).get();
        if (bmp == null) {
            abortDecode(F_MEMORY);
            return;
        }
        var dc = (bmp as Graphics.BufferedBitmap).getDc();
        var bytes = _decBytes as ByteArray;
        var stop = _decPos + BYTES_PER_TICK;
        if (stop > bytes.size()) {
            stop = bytes.size();
        }
        var w = _decW;
        var x = _decX;
        var y = _decY;
        var lastV = -1;
        var color = _decColor;
        for (var i = _decPos; i < stop; i++) {
            var b = bytes[i];
            var v = color ? (b >> 4) & 15 : (b >> 6) & 3;
            var len = color ? (b & 15) + 1 : (b & 63) + 1;
            if (v == 0) {
                x += len;
                while (x >= w) {
                    x -= w;
                    y += 1;
                }
                continue;
            }
            if (v != lastV) {
                if (color && v >= _decPal.size()) {
                    v = _decPal.size() - 1;
                }
                dc.setColor(color ? _decPal[v] : Palette.LEVELS[v], Graphics.COLOR_TRANSPARENT);
                lastV = v;
            }
            while (len > 0) {
                var seg = w - x;
                if (seg > len) {
                    seg = len;
                }
                dc.fillRectangle(x, y, seg, 1);
                len -= seg;
                x += seg;
                if (x >= w) {
                    x = 0;
                    y += 1;
                }
            }
        }
        _decPos = stop;
        _decX = x;
        _decY = y;
        if (_decPos >= bytes.size()) {
            _ticker.cancel("img");
            var key = _decKey as String;
            _refs[key] = _decRef;
            _order.add(key);
            _decKey = null;
            _decBytes = null;
            _decRef = null;
            Mem.log("immagine " + key + " decodificata");
            WatchUi.requestUpdate();
            next();
        }
    }

    // Bitmap con palette, sfondo nero; null se non c'è memoria grafica nemmeno dopo
    // aver liberato tutte le altre bitmap.
    private function newBitmap(w as Number, h as Number, palette as Array<Number>) {
        freeRoom();
        var ref = allocBitmap(w, h, palette);
        if (ref == null && _order.size() > 0) {
            // zoom grandi: si liberano le altre immagini in memoria e si riprova
            _refs = {} as Dictionary;
            _order = [] as Array<String>;
            ref = allocBitmap(w, h, palette);
        }
        if (ref == null) {
            return null;
        }
        var bmp = (ref as Graphics.BufferedBitmapReference).get() as Graphics.BufferedBitmap;
        var bdc = bmp.getDc();
        bdc.setColor(Graphics.COLOR_BLACK, Graphics.COLOR_BLACK);
        bdc.clear();
        return ref;
    }

    private function allocBitmap(w as Number, h as Number, palette as Array<Number>) {
        try {
            var ref = Graphics.createBufferedBitmap({:width => w, :height => h, :palette => palette});
            return (ref as Graphics.BufferedBitmapReference).get() != null ? ref : null;
        } catch (e) {
            return null;
        }
    }

    // Immagine a colori decompressa: legge la palette (K, poi K colori RGB; l'indice 0 è
    // lo sfondo nero), crea la bitmap e fa partire l'RLE dopo la palette.
    // 0 se la decodifica può partire, altrimenti il motivo (F_DATA, F_MEMORY).
    private function startColor() as Number {
        var bytes = _decBytes as ByteArray;
        var k = bytes.size() > 0 ? bytes[0] : 0;
        if (k < 1 || k > 15 || bytes.size() < 1 + 3 * k) {
            return F_DATA;
        }
        var pal = [0x000000] as Array<Number>;
        for (var i = 0; i < k; i++) {
            var o = 1 + 3 * i;
            pal.add((bytes[o] << 16) | (bytes[o + 1] << 8) | bytes[o + 2]);
        }
        var ref = newBitmap(_decW, _decH, pal);
        if (ref == null) {
            return F_MEMORY;
        }
        _decPal = pal;
        _decRef = ref;
        _decPos = 1 + 3 * k;
        return 0;
    }

    // Un passo di decompressione LZ (formato: pipeline/gwnotes/lz.py) da _lzIn a
    // _decBytes. Ritorna 0 se c'è ancora lavoro, 1 se ha finito, -1 se i dati sono errati.
    private function lzStep() as Number {
        var c = _lzIn as ByteArray;
        var out = _decBytes as ByteArray;
        var n = c.size();
        var size = out.size();
        var i = _lzI;
        var o = _lzO;
        var limit = o + LZ_PER_TICK;
        while (i < n && o < limit) {
            var tok = c[i];
            i += 1;
            var ll = tok >> 4;
            if (ll == 15) {
                var b = 255;
                while (b == 255 && i < n) {
                    b = c[i];
                    i += 1;
                    ll += b;
                }
            }
            if (o + ll > size || i + ll > n) {
                return -1;
            }
            for (var k = 0; k < ll; k++) {
                out[o] = c[i];
                o += 1;
                i += 1;
            }
            if (i >= n) {
                break;
            }
            if (i + 1 >= n) {
                return -1;
            }
            var off = c[i] | (c[i + 1] << 8);
            i += 2;
            var ml = tok & 15;
            if (ml == 15) {
                var b = 255;
                while (b == 255 && i < n) {
                    b = c[i];
                    i += 1;
                    ml += b;
                }
            }
            ml += 4;
            if (off <= 0 || off > o || o + ml > size) {
                return -1;
            }
            for (var k = 0; k < ml; k++) {
                out[o] = out[o - off];
                o += 1;
            }
        }
        _lzI = i;
        _lzO = o;
        if (i >= n) {
            return o == size ? 1 : -1;
        }
        return 0;
    }

    private function abortDecode(reason as Number) as Void {
        _ticker.cancel("img");
        var key = _decKey;
        _decKey = null;
        if (key != null) {
            fail(key as String, reason);
        }
        _decBytes = null;
        _decRef = null;
        _lzIn = null;
        next();
    }

    private function freeRoom() as Void {
        while (_order.size() >= MAX_BITMAPS) {
            var k = _order[0];
            _order = _order.slice(1, null) as Array<String>;
            _refs.remove(k);
        }
    }

    // Libera tutto (es. uscendo dalla lettura).
    function clear() as Void {
        _refs = {} as Dictionary;
        _order = [] as Array<String>;
        _wanted = [] as Array<String>;
    }
}
