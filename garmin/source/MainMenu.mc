import Toybox.Lang;
import Toybox.WatchUi;

function showMainMenu() as Void {
    var m = new WatchUi.Menu2({:title => WatchUi.loadResource(Rez.Strings.MenuTitle) as String});
    m.addItem(new WatchUi.MenuItem(WatchUi.loadResource(Rez.Strings.MenuResume) as String, null, :resume, null));
    m.addItem(new WatchUi.MenuItem(WatchUi.loadResource(Rez.Strings.MenuIndex) as String, null, :index, null));
    m.addItem(new WatchUi.MenuItem(WatchUi.loadResource(Rez.Strings.MenuAuto) as String, autoLabel(getApp().autoSeconds()),
        :auto, null));
    m.addItem(new WatchUi.ToggleMenuItem(WatchUi.loadResource(Rez.Strings.MenuClockKey) as String,
        WatchUi.loadResource(Rez.Strings.MenuClockKeySub) as String, :clockKey, getApp().clockButton(), null));
    var winfo = getApp().store.getValue("winfo");
    m.addItem(new WatchUi.MenuItem(WatchUi.loadResource(Rez.Strings.MenuSync) as String,
        getApp().status + ((winfo instanceof Lang.String) ? " · " + winfo : ""), :sync, null));
    m.addItem(new WatchUi.MenuItem(WatchUi.loadResource(Rez.Strings.MenuClear) as String,
        getApp().store.count().toString() + " risorse, " + (getApp().store.used() / 1024) + " KB", :clear, null));
    var sr = speedResult();
    m.addItem(new WatchUi.MenuItem(WatchUi.loadResource(Rez.Strings.MenuSpeed) as String,
        sr != null ? sr : WatchUi.loadResource(Rez.Strings.MenuSpeedSub) as String, :speed, null));
    m.addItem(new WatchUi.ToggleMenuItem(WatchUi.loadResource(Rez.Strings.MenuMemory) as String, null, :memory,
        getApp().showMemory, null));
    WatchUi.pushView(m, new MainMenuDelegate(), WatchUi.SLIDE_UP);
}

// valori dello scorrimento automatico, in secondi per pagina (0 = spento)
const AUTO_STEPS = [0, 5, 10, 15, 20, 30, 45, 60];

function autoLabel(secs as Number) as String {
    return secs == 0 ? (WatchUi.loadResource(Rez.Strings.Off) as String) : secs.toString() + " s";
}

class MainMenuDelegate extends WatchUi.Menu2InputDelegate {
    private var _speedItem as WatchUi.MenuItem or Null = null;

    function onSpeedDone() as Void {
        var app = getApp();
        if (_speedItem != null) {
            var r = speedResult();
            (_speedItem as WatchUi.MenuItem).setSubLabel(r != null ? r : "");
        }
        // riprende il download in sottofondo sospeso per la prova
        app.startSync();
        WatchUi.requestUpdate();
    }

    function initialize() {
        Menu2InputDelegate.initialize();
    }

    function onSelect(item as WatchUi.MenuItem) as Void {
        var app = getApp();
        var id = item.getId();
        if (id == :auto) {
            // ogni tocco passa al valore successivo; il menu resta aperto
            var cur = app.autoSeconds();
            var i = AUTO_STEPS.indexOf(cur);
            var next = AUTO_STEPS[(i + 1) % AUTO_STEPS.size()] as Number;
            app.store.setValue("auto", next);
            item.setSubLabel(autoLabel(next));
            WatchUi.requestUpdate();
            return;
        }
        if (id == :speed) {
            // il menu resta aperto: il risultato compare sotto la voce
            if (!app.speed.running) {
                _speedItem = item;
                item.setSubLabel(WatchUi.loadResource(Rez.Strings.MenuSpeedRunning) as String);
                app.prefetch.stop();   // niente altro traffico durante la prova
                app.speed.run(method(:onSpeedDone));
                WatchUi.requestUpdate();
            }
            return;
        }
        if (id == :clockKey) {
            app.store.setValue("clockKey", (item as WatchUi.ToggleMenuItem).isEnabled());
            return;
        }
        if (id == :memory) {
            app.showMemory = !app.showMemory;
            Mem.log("richiesta dall'utente");
            WatchUi.popView(WatchUi.SLIDE_DOWN);
            return;
        }
        WatchUi.popView(WatchUi.SLIDE_DOWN);
        if (id == :sync) {
            app.images.retryFailed();
            app.startSync();
        } else if (id == :clear) {
            app.prefetch.stop();
            app.store.clearAll();
            app.images.clear();
            app.index = null;
            app.startSync();
        } else if (id == :index) {
            // torna alla lista dei capitoli
            var v = new QuestionListView();
            WatchUi.switchToView(v, new QuestionListDelegate(v), WatchUi.SLIDE_RIGHT);
        } else if (id == :resume) {
            var pos = app.lastPosition();
            if (pos != null && app.index != null) {
                var sec = (app.index as Index).findSection(pos[0] as String);
                if (sec != null) {
                    openReader(sec as Section, pos[1] as Number);
                }
            }
        }
        WatchUi.requestUpdate();
    }
}
