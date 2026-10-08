package io.github.imprudentcoding.garminlatex

import android.content.Context
import androidx.core.content.edit

/** Preferenze dell'utente (SharedPreferences). */
class Settings(context: Context) {
    private val p = context.getSharedPreferences("settings", Context.MODE_PRIVATE)

    /** Repository GitHub da cui scaricare gli appunti ("owner/repo"). */
    var repo: String
        get() = p.getString("repo", null)?.takeIf { it.contains('/') } ?: BuildConfig.DEFAULT_REPO
        set(v) = p.edit { putString("repo", v.trim()) }

    /** Controllo automatico degli aggiornamenti, in ore (0 = disattivato). */
    var autoUpdateHours: Int
        get() = p.getInt("autoUpdateHours", 6)
        set(v) = p.edit { putInt("autoUpdateHours", v) }

    /** Collegamento al simulatore Connect IQ via ADB invece che all'orologio. */
    var simulator: Boolean
        get() = p.getBoolean("simulator", false)
        set(v) = p.edit { putBoolean("simulator", v) }

    /** Servizio in primo piano per rispondere all'orologio con l'app chiusa. */
    var keepAlive: Boolean
        get() = p.getBoolean("keepAlive", true)
        set(v) = p.edit { putBoolean("keepAlive", v) }

    /** Ultimo asset scaricato ("idAsset@updated_at"), per non riscaricarlo. */
    var lastAsset: String?
        get() = p.getString("lastAsset", null)
        set(v) = p.edit { putString("lastAsset", v) }

    var lastCheck: Long
        get() = p.getLong("lastCheck", 0)
        set(v) = p.edit { putLong("lastCheck", v) }

    var lastRelease: String?
        get() = p.getString("lastRelease", null)
        set(v) = p.edit { putString("lastRelease", v) }
}
