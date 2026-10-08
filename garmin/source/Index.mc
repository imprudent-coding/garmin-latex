import Toybox.Lang;

// Indice degli appunti (formato: shared/FORMAT.md, sezione "Indice").
class Section {
    var id as String;
    var hash as String;
    var pages as Number;
    var starts as Array<Number>;   // prima pagina di ogni pezzo
    var widths as Array<Number>;
    var lines as Array<String>;
    var chapter as Number;
    // elenco compatto (righe "Q" dell'indice): tipo, id della domanda, riga larga e stretta
    var kind as String = "section";
    var qid as String = "";
    var cLines as Array<String> or Null = null;
    var cWidths as Array<Number> or Null = null;
    // file web (riga "F") con la sezione e le sue immagini; vuoto = solo telefono
    var packs as Array<String> = [] as Array<String>;

    function initialize(f as Array<String>, chapter as Number) {
        id = f[1];
        hash = f[2];
        pages = Util.toNum(f[3]);
        starts = Util.numbers(f[4]);
        widths = Util.numbers(f[5]);
        lines = Util.split(f[6], Index.titleBreak());
        self.chapter = chapter;
    }

    function key() as String {
        return "s:" + id;
    }

    // indice del pezzo che contiene la pagina p
    function chunkFor(p as Number) as Number {
        var n = 0;
        for (var i = 0; i < starts.size(); i++) {
            if (starts[i] <= p) {
                n = i;
            }
        }
        return n;
    }
}

class Chapter {
    var widths as Array<Number>;
    var lines as Array<String>;
    var sections as Array<Section> = [] as Array<Section>;
    // intestazione compatta del gruppo nell'elenco (riga "H"), null se il gruppo ha una sola sezione
    var hLine as String or Null = null;
    var hWidth as Number = 0;

    function initialize(f as Array<String>) {
        widths = Util.numbers(f[2]);
        lines = Util.split(f[3], Index.titleBreak());
    }
}

class Index {
    // separatore delle righe dei titoli (U+E01E)
    static function titleBreak() as String {
        return (0xE01E).toChar().toString();
    }

    var schema as Number = 0;
    var version as String = "";
    var fontId as String = "";
    var title as String = "";
    // indirizzo dei file web (riga "W"), null se gli appunti non sono sul web
    var webBase as String or Null = null;
    var chapters as Array<Chapter> = [] as Array<Chapter>;

    function initialize(text as String) {
        var rows = Util.split(text, "\n");
        var current = null;
        for (var i = 0; i < rows.size(); i++) {
            var row = rows[i];
            if (row.length() < 2) {
                continue;
            }
            var t = row.substring(0, 1);
            if (t.equals("V")) {
                var f = Util.splitN(row, "|", 5);
                schema = Util.toNum(f[1]);
                version = f[2];
                fontId = f[3];
                title = f[4];
            } else if (t.equals("C")) {
                current = new Chapter(Util.splitN(row, "|", 4));
                chapters.add(current);
            } else if (t.equals("S") && current != null) {
                (current as Chapter).sections.add(new Section(Util.splitN(row, "|", 7), chapters.size() - 1));
            } else if (t.equals("W")) {
                var f = Util.splitN(row, "|", 2);
                if (f.size() == 2 && f[1].length() > 8) {
                    webBase = f[1];
                }
            } else if (t.equals("F") && current != null) {
                var secs = (current as Chapter).sections;
                var f = Util.splitN(row, "|", 3);
                if (f.size() == 3 && secs.size() > 0 && secs[secs.size() - 1].id.equals(f[1])) {
                    secs[secs.size() - 1].packs = Util.split(f[2], ";");
                }
            } else if (t.equals("H") && current != null) {
                var f = Util.splitN(row, "|", 3);
                (current as Chapter).hWidth = Util.toNum(f[1]);
                (current as Chapter).hLine = f[2];
            } else if (t.equals("Q") && current != null) {
                var secs = (current as Chapter).sections;
                var f = Util.splitN(row, "|", 6);
                if (secs.size() > 0 && secs[secs.size() - 1].id.equals(f[1])) {
                    var sec = secs[secs.size() - 1];
                    sec.kind = f[2];
                    sec.qid = f[3];
                    sec.cWidths = Util.numbers(f[4]);
                    sec.cLines = Util.split(f[5], Index.titleBreak());
                }
            }
            // righe di tipo sconosciuto: ignorate (compatibilità con indici più recenti)
        }
    }

    function findSection(id as String) as Section or Null {
        for (var c = 0; c < chapters.size(); c++) {
            var secs = chapters[c].sections;
            for (var s = 0; s < secs.size(); s++) {
                if (secs[s].id.equals(id)) {
                    return secs[s];
                }
            }
        }
        return null;
    }
}
