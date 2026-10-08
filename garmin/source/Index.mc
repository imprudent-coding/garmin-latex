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
            }
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
