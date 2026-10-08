import Toybox.Lang;
import Toybox.WatchUi;

function showMainMenu() as Void {
    var m = new WatchUi.Menu2({:title => WatchUi.loadResource(Rez.Strings.MenuTitle) as String});
    m.addItem(new WatchUi.MenuItem(WatchUi.loadResource(Rez.Strings.MenuResume) as String, null, :resume, null));
    m.addItem(new WatchUi.MenuItem(WatchUi.loadResource(Rez.Strings.MenuIndex) as String, null, :index, null));
    m.addItem(new WatchUi.MenuItem(WatchUi.loadResource(Rez.Strings.MenuSync) as String, getApp().status, :sync, null));
    m.addItem(new WatchUi.MenuItem(WatchUi.loadResource(Rez.Strings.MenuClear) as String,
        getApp().store.count().toString() + " risorse", :clear, null));
    m.addItem(new WatchUi.ToggleMenuItem(WatchUi.loadResource(Rez.Strings.MenuMemory) as String, null, :memory,
        getApp().showMemory, null));
    WatchUi.pushView(m, new MainMenuDelegate(), WatchUi.SLIDE_UP);
}

class MainMenuDelegate extends WatchUi.Menu2InputDelegate {
    function initialize() {
        Menu2InputDelegate.initialize();
    }

    function onSelect(item as WatchUi.MenuItem) as Void {
        var app = getApp();
        var id = item.getId();
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
            app.store.clearAll();
            app.images.clear();
            app.index = null;
            app.startSync();
        } else if (id == :index) {
            // torna alla lista dei capitoli
            var v = new ChapterListView();
            WatchUi.switchToView(v, new ListDelegate(v), WatchUi.SLIDE_RIGHT);
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
