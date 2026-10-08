package io.github.imprudentcoding.garminlatex

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import io.github.imprudentcoding.garminlatex.bundle.BundleRepository
import io.github.imprudentcoding.garminlatex.watch.WatchLink
import io.github.imprudentcoding.garminlatex.work.UpdateWorker
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/** Oggetti condivisi dall'interfaccia, dal servizio e dal worker. */
class NotesApplication : Application() {
    lateinit var settings: Settings
    lateinit var repo: BundleRepository
    lateinit var watch: WatchLink
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    override fun onCreate() {
        super.onCreate()
        settings = Settings(this)
        repo = BundleRepository(this, settings)
        watch = WatchLink(this, repo, settings)
        repo.onNewBundle = { b -> scope.launch { watch.notifyUpdate(b.manifest.contentVersion) } }
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_SERVICE, getString(R.string.channel_service), NotificationManager.IMPORTANCE_MIN)
        )
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_UPDATES, getString(R.string.channel_updates), NotificationManager.IMPORTANCE_DEFAULT)
        )
        scope.launch { repo.loadCached() }
        UpdateWorker.schedule(this, settings.autoUpdateHours)
    }

    companion object {
        const val CHANNEL_SERVICE = "service"
        const val CHANNEL_UPDATES = "updates"
    }
}
