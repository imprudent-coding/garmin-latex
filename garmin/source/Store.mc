import Toybox.Application;
import Toybox.Application.Storage;
import Toybox.Lang;
import Toybox.System;

// Cache delle risorse in Application.Storage (vedi shared/PROTOCOL.md).
//
// Limiti documentati da Garmin: 8 KB per valore e 128 KB totali (guida
// "Persisting Data"); 32 KB per valore e totale variabile (API reference).
// Rispettiamo il più stretto: pezzi di ~1,8 KB e budget di 96 KB.
class Store {
    const BUDGET = 96 * 1024;
    const META = "meta";

    // chiave risorsa -> [hash, pezzi totali, byte salvati, ultimo uso, pezzi presenti]
    private var _meta as Dictionary;
    private var _stamp as Number = 0;
    // risorse da non eliminare (indice, sezione aperta)
    var pinned as Array<String> = ["idx"] as Array<String>;

    function initialize() {
        var m = null;
        try {
            m = Storage.getValue(META);
        } catch (e) {
            m = null;
        }
        _meta = (m instanceof Lang.Dictionary) ? (m as Dictionary) : ({} as Dictionary);
        var st = Storage.getValue("stamp");
        _stamp = (st instanceof Lang.Number) ? (st as Number) : 0;
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
        touch(key);
        save();
        return true;
    }

    function used() as Number {
        var keys = _meta.keys();
        var sum = 0;
        for (var i = 0; i < keys.size(); i++) {
            sum += ((_meta[keys[i]] as Array)[2] as Number);
        }
        return sum;
    }

    private function makeRoom(bytes as Number, keep as String) as Void {
        while (used() + bytes > BUDGET) {
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
        _meta.remove(key);
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

    function clearAll() as Void {
        Storage.clearValues();
        _meta = {} as Dictionary;
        _stamp = 0;
    }

    function save() as Void {
        try {
            Storage.setValue(META, _meta);
            Storage.setValue("stamp", _stamp);
        } catch (e) {
            // il dizionario dei metadati è troppo grande: libera spazio e riprova una volta
            if (evictOne("")) {
                try {
                    Storage.setValue(META, _meta);
                } catch (e2) {
                    System.println("Impossibile salvare i metadati della cache");
                }
            }
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
