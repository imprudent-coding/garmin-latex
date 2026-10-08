import Toybox.Graphics;
import Toybox.Lang;
import Toybox.System;

// Colori: devono coincidere con shared/FORMAT.md (palette del testo ricco).
module Palette {
    const COLORS = [0xFFFFFF, 0xFFB54A, 0x9A9A9A, 0x7FD4FF, 0x6FE3B4, 0x7FD4FF, 0xFF6B6B] as Array<Number>;
    // livelli di grigio delle immagini (0 = sfondo nero)
    const LEVELS = [0x000000, 0x555555, 0xAAAAAA, 0xFFFFFF] as Array<Number>;

    function color(i as Number) as Number {
        if (i >= 0 && i < COLORS.size()) {
            return COLORS[i];
        }
        return 0xFFFFFF;
    }
}

module Util {
    // Divide s a ogni occorrenza di sep.
    function split(s as String, sep as String) as Array<String> {
        return splitN(s, sep, 0);
    }

    // Come split ma al massimo n parti (n = 0: nessun limite); l'ultima contiene il resto.
    function splitN(s as String, sep as String, n as Number) as Array<String> {
        var out = [] as Array<String>;
        var rest = s;
        var sl = sep.length();
        while (true) {
            if (n > 0 && out.size() == n - 1) {
                out.add(rest);
                break;
            }
            var i = rest.find(sep);
            if (i == null) {
                out.add(rest);
                break;
            }
            out.add(rest.substring(0, i) as String);
            rest = rest.substring(i + sl, rest.length()) as String;
        }
        return out;
    }

    function toNum(s) as Number {
        if (s == null) {
            return 0;
        }
        if (s instanceof Lang.Number) {
            return s as Number;
        }
        var n = (s as String).toNumber();
        return n == null ? 0 : n;
    }

    function numbers(s as String) as Array<Number> {
        var out = [] as Array<Number>;
        if (s.length() == 0) {
            return out;
        }
        var parts = split(s, ";");
        for (var i = 0; i < parts.size(); i++) {
            out.add(toNum(parts[i]));
        }
        return out;
    }
}

// Registro dell'uso di memoria nei punti critici (console del simulatore).
module Mem {
    function log(tag as String) as Void {
        var s = System.getSystemStats();
        System.println("[mem] " + tag + ": usata " + s.usedMemory + " / " + s.totalMemory
            + " (libera " + s.freeMemory + ")");
    }

    function label() as String {
        var s = System.getSystemStats();
        return (s.usedMemory / 1024) + "/" + (s.totalMemory / 1024) + " KB";
    }
}
