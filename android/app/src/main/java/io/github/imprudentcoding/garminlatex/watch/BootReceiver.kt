package io.github.imprudentcoding.garminlatex.watch

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import io.github.imprudentcoding.garminlatex.Settings

/** Riavvia il servizio dopo un riavvio del telefono (se l'utente lo vuole). */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action == Intent.ACTION_BOOT_COMPLETED && Settings(context).keepAlive) {
            try {
                WatchService.start(context)
            } catch (e: Exception) {
                // Android può vietare l'avvio di servizi in primo piano da qui: si riparte all'apertura dell'app
            }
        }
    }
}
