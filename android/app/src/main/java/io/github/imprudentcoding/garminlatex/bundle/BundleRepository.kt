package io.github.imprudentcoding.garminlatex.bundle

import android.content.Context
import android.util.Log
import io.github.imprudentcoding.garminlatex.BuildConfig
import io.github.imprudentcoding.garminlatex.Settings
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import java.io.File
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

data class BundleState(
    val bundle: Bundle? = null,
    val checking: Boolean = false,
    val progress: String? = null,
    val lastCheck: Long = 0,
    val release: String? = null,
    val error: String? = null,
)

sealed interface UpdateResult {
    data class Updated(val version: String) : UpdateResult
    data object UpToDate : UpdateResult
    data object NoRelease : UpdateResult
    data class Failed(val message: String) : UpdateResult
}

/** Asset trovato nelle Release. */
data class ReleaseAsset(val tag: String, val name: String, val url: String, val marker: String, val size: Long)

/**
 * Scarica il bundle dalla Release GitHub più recente con tag "notes-*" e asset
 * notes-bundle.zip, lo verifica (schema e hash) e lo sostituisce in modo atomico.
 */
class BundleRepository(private val context: Context, private val settings: Settings) {
    private val dir = File(context.filesDir, "bundle").apply { mkdirs() }
    private val current = File(dir, "notes-bundle.zip")
    private val mutex = Mutex()
    private val _state = MutableStateFlow(BundleState(lastCheck = settings.lastCheck, release = settings.lastRelease))
    val state: StateFlow<BundleState> = _state

    /** Listener chiamati quando cambia il bundle (es. per avvisare l'orologio). */
    var onNewBundle: ((Bundle) -> Unit)? = null

    fun bundle(): Bundle? = _state.value.bundle

    suspend fun loadCached() = withContext(Dispatchers.IO) {
        if (_state.value.bundle != null || !current.exists()) return@withContext
        try {
            val b = Bundle.open(current, BuildConfig.BUNDLE_SCHEMA, verify = false)
            _state.update { it.copy(bundle = b, error = null) }
        } catch (e: Exception) {
            Log.w(TAG, "bundle in cache illeggibile", e)
            _state.update { it.copy(error = "Bundle in cache non valido: ${e.message}") }
        }
    }

    suspend fun checkForUpdates(force: Boolean = false): UpdateResult = mutex.withLock {
        withContext(Dispatchers.IO) {
            _state.update { it.copy(checking = true, error = null, progress = "Controllo delle Release…") }
            val result = try {
                doCheck(force)
            } catch (e: Exception) {
                Log.w(TAG, "aggiornamento fallito", e)
                UpdateResult.Failed(e.message ?: e.javaClass.simpleName)
            }
            settings.lastCheck = System.currentTimeMillis()
            _state.update {
                it.copy(
                    checking = false, progress = null, lastCheck = settings.lastCheck,
                    release = settings.lastRelease,
                    error = (result as? UpdateResult.Failed)?.message
                        ?: if (result is UpdateResult.NoRelease) "Nessuna Release \"notes-*\" con notes-bundle.zip" else null,
                )
            }
            result
        }
    }

    private fun doCheck(force: Boolean): UpdateResult {
        val asset = findLatestAsset(settings.repo) ?: return UpdateResult.NoRelease
        if (!force && asset.marker == settings.lastAsset && current.exists()) {
            return UpdateResult.UpToDate
        }
        _state.update { it.copy(progress = "Download di ${asset.tag} (${asset.size / 1024} KB)…") }
        val tmp = File(dir, "download.tmp")
        download(asset.url, tmp)
        _state.update { it.copy(progress = "Verifica…") }
        val fresh = try {
            Bundle.open(tmp, BuildConfig.BUNDLE_SCHEMA, verify = true)
        } catch (e: Exception) {
            tmp.delete()
            throw IOException("bundle scaricato non valido: ${e.message}")
        }
        val old = _state.value.bundle
        if (old != null && old.manifest.contentHash == fresh.manifest.contentHash && current.exists()) {
            fresh.close()
            tmp.delete()
            settings.lastAsset = asset.marker
            settings.lastRelease = asset.tag
            return UpdateResult.UpToDate
        }
        fresh.close()
        old?.close()
        if (!tmp.renameTo(current)) {
            tmp.copyTo(current, overwrite = true)
            tmp.delete()
        }
        val b = Bundle.open(current, BuildConfig.BUNDLE_SCHEMA, verify = false)
        settings.lastAsset = asset.marker
        settings.lastRelease = asset.tag
        _state.update { it.copy(bundle = b) }
        onNewBundle?.invoke(b)
        return UpdateResult.Updated(b.manifest.contentVersion)
    }

    private fun findLatestAsset(repo: String): ReleaseAsset? {
        val conn = (URL("https://api.github.com/repos/$repo/releases?per_page=30").openConnection() as HttpURLConnection)
        conn.setRequestProperty("Accept", "application/vnd.github+json")
        conn.setRequestProperty("User-Agent", "garmin-latex-notes-android")
        conn.connectTimeout = 15000
        conn.readTimeout = 30000
        try {
            when (conn.responseCode) {
                200 -> {}
                404 -> throw IOException("repository $repo non trovato (o privato)")
                403 -> throw IOException("limite di richieste GitHub raggiunto: riprova più tardi")
                else -> throw IOException("GitHub ha risposto ${conn.responseCode}")
            }
            val arr = JSONArray(conn.inputStream.use { it.readBytes().toString(Charsets.UTF_8) })
            return parseReleases(arr)
        } finally {
            conn.disconnect()
        }
    }

    private fun download(url: String, out: File) {
        var u = URL(url)
        repeat(5) {
            val conn = u.openConnection() as HttpURLConnection
            conn.instanceFollowRedirects = false
            conn.setRequestProperty("User-Agent", "garmin-latex-notes-android")
            conn.setRequestProperty("Accept", "application/octet-stream")
            conn.connectTimeout = 15000
            conn.readTimeout = 60000
            try {
                val code = conn.responseCode
                if (code in 300..399) {
                    u = URL(u, conn.getHeaderField("Location"))
                    return@repeat
                }
                if (code != 200) throw IOException("download fallito: HTTP $code")
                conn.inputStream.use { input -> out.outputStream().use { input.copyTo(it) } }
                return
            } finally {
                conn.disconnect()
            }
        }
        throw IOException("troppi redirect")
    }

    companion object {
        private const val TAG = "BundleRepository"
        const val ASSET_NAME = "notes-bundle.zip"
        const val TAG_PREFIX = "notes-"

        /** Prima Release (le API le ordinano dalla più recente) con tag notes-* e l'asset del bundle. */
        fun parseReleases(arr: JSONArray): ReleaseAsset? {
            for (i in 0 until arr.length()) {
                val r = arr.getJSONObject(i)
                if (r.optBoolean("draft") || r.optBoolean("prerelease")) continue
                val tag = r.optString("tag_name")
                if (!tag.startsWith(TAG_PREFIX)) continue
                val assets = r.optJSONArray("assets") ?: continue
                for (j in 0 until assets.length()) {
                    val a = assets.getJSONObject(j)
                    if (a.optString("name") == ASSET_NAME) {
                        return ReleaseAsset(
                            tag, ASSET_NAME, a.getString("browser_download_url"),
                            "${a.optLong("id")}@${a.optString("updated_at")}", a.optLong("size"),
                        )
                    }
                }
            }
            return null
        }
    }
}
