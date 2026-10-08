import Toybox.Application;
import Toybox.Application.Storage;
import Toybox.Lang;
import Toybox.System;

// Cache delle risorse in Application.Storage (vedi shared/PROTOCOL.md).
//
// Spazio: il device file del vívoactive 5 (simulator.json) indica
// appStorageCapacity = 10 MB per app. Il bundle intero è ~1,6 MB, quindi la
// cache può contenere tutti gli appunti: budget di 6 MB, con margine. Se
// setValue lancia comunque un'eccezione di spazio esaurito, si liberano le
// risorse usate meno di recente.
// Valori: pezzi di ~1,8 KB; i metadati sono divisi in BUCKETS valori ("m0"…)
// perché con tutte le risorse un solo dizionario supererebbe gli 8 KB per
// valore indicati dalla guida "Persisting Data" (l'API reference dice 32 KB).
class Store {
    const BUDGET = 6 * 1024 * 1024;
    const BUCKETS = 16;

    // chiave risorsa -> [hash, pezzi totali, byte salvati, ultimo uso, pezzi presenti]
    private var _meta as Dictionary;
    private var _stamp as Number = 0;
    private var _used as Number = 0;
    // gruppi di metadati modificati e non ancora salvati
    private var _dirty as Dictionary = {} as Dictionary;
    // risorse da non eliminare (indice, sezione aperta)
    var pinned as Array<String> = ["idx"] as Array<String>;

    function initialize() {
        var st = read("stamp");
        _stamp = (st instanceof Lang.Number) ? (st as Number) : 0;
        _meta = {} as Dictionary;
        for (var b = 0; b < BUCKETS; b++) {
            var m = read("m" + b);
            if (m instanceof Lang.Dictionary) {
                var ks = (m as Dictionary).keys();
                for (var i = 0; i < ks.size(); i++) {
                    _meta[ks[i]] = (m as Dictionary)[ks[i]];
                }
            }
        }
        // versioni precedenti: un solo valore "meta"
        var old = read("meta");
        if (old instanceof Lang.Dictionary) {
            var ks = (old as Dictionary).keys();
            for (var i = 0; i < ks.size(); i++) {
                _meta[ks[i]] = (old as Dictionary)[ks[i]];
                markDirty(ks[i] as String);
            }
            Storage.deleteValue("meta");
            save();
        }
        var keys = _meta.keys();
        for (var i = 0; i < keys.size(); i++) {
            _used += ((_meta[keys[i]] as Array)[2] as Number);
        }
    }

    private function read(k as String) {
        try {
            return Storage.getValue(k);
        } catch (e) {
            return null;
        }
    }

    // gruppo dei metadati di una chiave (hash dei byte, stabile tra le esecuzioni)
    private function bucketOf(key as String) as Number {
        var b = key.toUtf8Array();
        var h = 0;
        for (var i = 0; i < b.size(); i++) {
            h = (h * 31 + b[i]) % 65521;
        }
        return h % BUCKETS;
    }

    private function markDirty(key as String) as Void {
        _dirty[bucketOf(key)] = true;
    }

    private function ck(key as String, n as Number) as String {
        return "c|" + key + "|" + n;
    }

    function hashOf(key as String) as String or Null {
        var m = _meta[key];
        return m == null ? null : ((m as Array)[0] as String);
    }

    function totalOf(key as String) as Number {
        var m = _meta[key];
        return m == null ? 0 : ((m as Array)[1] as Number);
    }

    function isComplete(key as String, hash as String) as Boolean {
        var m = _meta[key] as Array or Null;
        if (m == null) {
            return false;
        }
        if (hash.length() > 0 && !(m[0] as String).equals(hash)) {
            return false;
        }
        return (m[4] as Number) >= (m[1] as Number) && (m[1] as Number) > 0;
    }

    // Ritorna il pezzo n se presente e con l'hash atteso ("" = qualsiasi).
    function get(key as String, n as Number, hash as String) as String or Null {
        var m = _meta[key] as Array or Null;
        if (m == null) {
            return null;
        }
        if (hash.length() > 0 && !(m[0] as String).equals(hash)) {
            return null;
        }
        var v = null;
        try {
            v = Storage.getValue(ck(key, n));
        } catch (e) {
            v = null;
        }
        if (v instanceof Lang.String) {
            touch(key);
            return v as String;
        }
        return null;
    }

    // Tutti i pezzi concatenati (con sep), o null se manca qualcosa.
    function getAll(key as String, hash as String, sep as String) as String or Null {
        if (!isComplete(key, hash)) {
            return null;
        }
        var total = totalOf(key);
        var out = "";
        for (var i = 0; i < total; i++) {
            var c = get(key, i, hash);
            if (c == null) {
                return null;
            }
            out = (i == 0) ? c : out + sep + c;
        }
        return out;
    }

    function touch(key as String) as Void {
        var m = _meta[key] as Array or Null;
        if (m != null) {
            _stamp += 1;
            m[3] = _stamp;
            markDirty(key);
        }
    }

    // Salva un pezzo. Ritorna false se non c'è spazio nemmeno dopo aver liberato la cache.
    function put(key as String, n as Number, total as Number, hash as String, data as String) as Boolean {
        var m = _meta[key] as Array or Null;
        if (m != null && !(m[0] as String).equals(hash)) {
            remove(key);
            m = null;
        }
        if (m == null) {
            m = [hash, total, 0, 0, 0];
            _meta[key] = m;
            markDirty(key);
        }
        var k = ck(key, n);
        if (Storage.getValue(k) != null) {
            touch(key);
            return true;
        }
        var bytes = data.length() + 16;
        makeRoom(bytes, key);
        var ok = false;
        for (var attempt = 0; attempt < 4 && !ok; attempt++) {
            try {
                Storage.setValue(k, data);
                ok = true;
            } catch (e) {
                // spazio esaurito: libera la risorsa usata meno di recente e riprova
                System.println("Storage pieno: " + e.getErrorMessage());
                if (!evictOne(key)) {
                    break;
                }
            }
        }
        if (!ok) {
            return false;
        }
        m[1] = total;
        m[2] = (m[2] as Number) + bytes;
        m[4] = (m[4] as Number) + 1;
        _used += bytes;
        touch(key);
        save();
        return true;
    }

    function used() as Number {
        return _used;
    }

    // oltre il 90% del budget: il prefetch si ferma
    function nearlyFull() as Boolean {
        return _used > BUDGET / 10 * 9;
    }

    private function makeRoom(bytes as Number, keep as String) as Void {
        while (_used + bytes > BUDGET) {
            if (!evictOne(keep)) {
                return;
            }
        }
    }

    // Elimina la risorsa meno usata (escluse quelle bloccate e `keep`).
    function evictOne(keep as String) as Boolean {
        var keys = _meta.keys();
        var victim = null;
        var best = 0x7FFFFFFF;
        for (var i = 0; i < keys.size(); i++) {
            var k = keys[i] as String;
            if (k.equals(keep) || pinned.indexOf(k) >= 0) {
                continue;
            }
            var st = (_meta[k] as Array)[3] as Number;
            if (st < best) {
                best = st;
                victim = k;
            }
        }
        if (victim == null) {
            return false;
        }
        remove(victim as String);
        return true;
    }

    function remove(key as String) as Void {
        var m = _meta[key] as Array or Null;
        if (m == null) {
            return;
        }
        var total = m[1] as Number;
        for (var i = 0; i < total; i++) {
            Storage.deleteValue(ck(key, i));
        }
        _used -= (m[2] as Number);
        _meta.remove(key);
        markDirty(key);
        save();
    }

    // Dopo un nuovo indice: elimina le sezioni il cui hash non è più valido.
    function dropStale(valid as Dictionary) as Void {
        var keys = _meta.keys();
        for (var i = 0; i < keys.size(); i++) {
            var k = keys[i] as String;
            if (k.length() > 2 && k.substring(0, 2).equals("s:")) {
                var h = valid[k];
                if (h == null || !(h as String).equals(hashOf(k))) {
                    remove(k);
                }
            }
        }
    }

    // Dopo un download completo: elimina le immagini che nessuna pagina usa più
    // (versioni precedenti degli appunti; le chiavi sono hash del contenuto).
    function dropImagesExcept(keep as Dictionary) as Void {
        var keys = _meta.keys();
        for (var i = 0; i < keys.size(); i++) {
            var k = keys[i] as String;
            if (k.length() > 2 && k.substring(0, 2).equals("i:") && keep[k] == null) {
                remove(k);
            }
        }
    }

    function clearAll() as Void {
        Storage.clearValues();
        _meta = {} as Dictionary;
        _dirty = {} as Dictionary;
        _stamp = 0;
        _used = 0;
    }

    // Salva i gruppi di metadati modificati.
    function save() as Void {
        var bs = _dirty.keys();
        _dirty = {} as Dictionary;
        if (bs.size() == 0) {
            return;
        }
        var parts = {} as Dictionary;
        for (var i = 0; i < bs.size(); i++) {
            parts[bs[i]] = {} as Dictionary;
        }
        var keys = _meta.keys();
        for (var i = 0; i < keys.size(); i++) {
            var p = parts[bucketOf(keys[i] as String)];
            if (p != null) {
                (p as Dictionary)[keys[i]] = _meta[keys[i]];
            }
        }
        for (var i = 0; i < bs.size(); i++) {
            try {
                Storage.setValue("m" + bs[i], parts[bs[i]]);
            } catch (e) {
                // spazio esaurito: il gruppo resta da salvare, ci si riprova al prossimo salvataggio
                System.println("Impossibile salvare i metadati della cache");
                _dirty[bs[i]] = true;
            }
        }
        try {
            Storage.setValue("stamp", _stamp);
        } catch (e) {
        }
    }

    function getValue(k as String) {
        return Storage.getValue(k);
    }

    function setValue(k as String, v) as Void {
        try {
            Storage.setValue(k, v);
        } catch (e) {
            System.println("Storage: " + k + " non salvato");
        }
    }

    function count() as Number {
        return _meta.size();
    }
}
