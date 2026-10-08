package io.github.imprudentcoding.garminlatex.watch

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import com.garmin.android.connectiq.ConnectIQ
import com.garmin.android.connectiq.IQApp
import com.garmin.android.connectiq.IQDevice
import io.github.imprudentcoding.garminlatex.BuildConfig
import io.github.imprudentcoding.garminlatex.Settings
import io.github.imprudentcoding.garminlatex.bundle.BundleRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

enum class SdkStatus { STOPPED, STARTING, READY, GCM_NOT_INSTALLED, GCM_UPGRADE_NEEDED, ERROR }

enum class AppStatus { UNKNOWN, INSTALLED, NOT_INSTALLED, NOT_SUPPORTED }

data class WatchDevice(
    val id: Long,
    val name: String,
    val status: String,  // CONNECTED, NOT_CONNECTED, NOT_PAIRED, UNKNOWN
    val app: AppStatus = AppStatus.UNKNOWN,
    val appVersion: Int = 0,
    val cache: ProtocolHandler.WatchProgress? = null,
)

data class WatchState(
    val sdk: SdkStatus = SdkStatus.STOPPED,
    val devices: List<WatchDevice> = emptyList(),
    val lastRequest: Long = 0,
    val chunksSent: Int = 0,
    val failures: Int = 0,
    /** Velocità misurata delle risposte con dati (media mobile), byte/s; 0 = non ancora misurata. */
    val bytesPerSecond: Int = 0,
    /** Durata dell'ultimo invio con dati, ms. */
    val lastSendMs: Long = 0,
    val duplicates: Int = 0,
    val log: List<String> = emptyList(),
    val error: String? = null,
    val simulator: Boolean = false,
)

/**
 * Collegamento con l'app sull'orologio tramite il Connect IQ Mobile SDK.
 * Tutte le comunicazioni passano dall'app Garmin Connect, che deve essere
 * installata e associata all'orologio.
 */
class WatchLink(
    private val context: Context,
    private val repo: BundleRepository,
    private val settings: Settings,
) {
    private val main = Handler(Looper.getMainLooper())
    private var ciq: ConnectIQ? = null
    private val app = IQApp(BuildConfig.WATCH_APP_ID)
    private val handler = ProtocolHandler(BuildConfig.BUNDLE_SCHEMA) {
        repo.bundle()?.let { ProtocolHandler.BundleSource(it) }
    }
    private val known = mutableMapOf<Long, IQDevice>()
    // risposte in corso di invio (dispositivo|req|chiave|n): un nuovo tentativo
    // dell'orologio mentre il telefono sta ancora inviando non va risposto di nuovo
    private val sending: MutableSet<String> = java.util.Collections.synchronizedSet(mutableSetOf())
    private val _state = MutableStateFlow(WatchState())
    val state: StateFlow<WatchState> = _state

    // ------------------------------------------------------------- avvio
    fun start() {
        if (_state.value.sdk == SdkStatus.STARTING || _state.value.sdk == SdkStatus.READY) return
        val sim = settings.simulator
        _state.update { it.copy(sdk = SdkStatus.STARTING, error = null, simulator = sim) }
        val type = if (sim) ConnectIQ.IQConnectType.TETHERED else ConnectIQ.IQConnectType.WIRELESS
        val instance = ConnectIQ.getInstance(context.applicationContext, type)
        ciq = instance
        try {
            instance.initialize(context.applicationContext, false, object : ConnectIQ.ConnectIQListener {
                override fun onSdkReady() {
                    log("SDK Connect IQ pronto" + if (sim) " (simulatore via ADB)" else "")
                    _state.update { it.copy(sdk = SdkStatus.READY) }
                    refreshDevices()
                }

                override fun onInitializeError(status: ConnectIQ.IQSdkErrorStatus) {
                    val s = when (status) {
                        ConnectIQ.IQSdkErrorStatus.GCM_NOT_INSTALLED -> SdkStatus.GCM_NOT_INSTALLED
                        ConnectIQ.IQSdkErrorStatus.GCM_UPGRADE_NEEDED -> SdkStatus.GCM_UPGRADE_NEEDED
                        else -> SdkStatus.ERROR
                    }
                    log("SDK non inizializzato: $status")
                    _state.update { it.copy(sdk = s, error = status.name) }
                }

                override fun onSdkShutDown() {
                    _state.update { it.copy(sdk = SdkStatus.STOPPED) }
                }
            })
        } catch (e: Exception) {
            log("Errore di inizializzazione: ${e.message}")
            _state.update { it.copy(sdk = SdkStatus.ERROR, error = e.message) }
        }
    }

    fun stop() {
        try {
            ciq?.unregisterAllForEvents()
            ciq?.shutdown(context.applicationContext)
        } catch (e: Exception) {
            Log.w(TAG, "shutdown", e)
        }
        known.clear()
        _state.update { it.copy(sdk = SdkStatus.STOPPED, devices = emptyList()) }
    }

    fun restart() {
        stop()
        main.postDelayed({ start() }, 500)
    }

    // ------------------------------------------------------------- dispositivi
    fun refreshDevices() {
        val c = ciq ?: return
        if (_state.value.sdk != SdkStatus.READY) return
        val devices = try {
            c.knownDevices ?: emptyList()
        } catch (e: Exception) {
            log("Impossibile leggere i dispositivi: ${e.message}")
            emptyList()
        }
        for (d in devices) {
            known[d.deviceIdentifier] = d
            upsert(d, statusOf(d))
            try {
                c.registerForDeviceEvents(d) { dev, st ->
                    upsert(dev, st.name)
                    if (st == IQDevice.IQDeviceStatus.CONNECTED) queryApp(dev)
                }
                c.registerForAppEvents(d, app) { dev, _, messages, status -> onMessages(dev, messages, status) }
            } catch (e: Exception) {
                log("Registrazione eventi fallita per ${d.friendlyName}: ${e.message}")
            }
            queryApp(d)
        }
        if (devices.isEmpty()) log("Nessun orologio associato a Garmin Connect")
    }

    private fun statusOf(d: IQDevice): String = try {
        ciq?.getDeviceStatus(d)?.name ?: "UNKNOWN"
    } catch (e: Exception) {
        "UNKNOWN"
    }

    private fun queryApp(d: IQDevice) {
        try {
            ciq?.getApplicationInfo(BuildConfig.WATCH_APP_ID, d, object : ConnectIQ.IQApplicationInfoListener {
                override fun onApplicationInfoReceived(info: IQApp) {
                    val st = when (info.status) {
                        IQApp.IQAppStatus.INSTALLED -> AppStatus.INSTALLED
                        IQApp.IQAppStatus.NOT_SUPPORTED -> AppStatus.NOT_SUPPORTED
                        IQApp.IQAppStatus.NOT_INSTALLED -> AppStatus.NOT_INSTALLED
                        else -> AppStatus.UNKNOWN
                    }
                    updateDevice(d.deviceIdentifier) { it.copy(app = st, appVersion = info.version()) }
                }

                override fun onApplicationNotInstalled(applicationId: String) {
                    updateDevice(d.deviceIdentifier) { it.copy(app = AppStatus.NOT_INSTALLED) }
                }
            })
        } catch (e: Exception) {
            Log.w(TAG, "getApplicationInfo", e)
        }
    }

    private fun upsert(d: IQDevice, status: String) {
        _state.update { s ->
            val others = s.devices.filter { it.id != d.deviceIdentifier }
            val prev = s.devices.firstOrNull { it.id == d.deviceIdentifier }
            val name = d.friendlyName?.takeIf { it.isNotBlank() } ?: "Orologio ${d.deviceIdentifier}"
            s.copy(devices = (others + (prev?.copy(status = status, name = name)
                ?: WatchDevice(d.deviceIdentifier, name, status))).sortedBy { it.name })
        }
    }

    private fun updateDevice(id: Long, f: (WatchDevice) -> WatchDevice) {
        _state.update { s -> s.copy(devices = s.devices.map { if (it.id == id) f(it) else it }) }
    }

    /** Chiede all'orologio di aprire l'app (compare una richiesta di conferma sul polso). */
    fun openWatchApp(id: Long) {
        val d = known[id] ?: return
        try {
            ciq?.openApplication(d, app) { _, _, status -> log("Apertura app sull'orologio: $status") }
        } catch (e: Exception) {
            log("Impossibile aprire l'app: ${e.message}")
        }
    }

    // ------------------------------------------------------------- messaggi
    private fun onMessages(d: IQDevice, messages: List<Any?>?, status: ConnectIQ.IQMessageStatus) {
        if (status != ConnectIQ.IQMessageStatus.SUCCESS) {
            log("Messaggio dall'orologio non ricevuto: $status")
            return
        }
        _state.update { it.copy(lastRequest = System.currentTimeMillis()) }
        for (m in messages.orEmpty()) {
            val id = (m as? Map<*, *>)?.takeIf { it["op"] == "get" }?.let {
                "${d.deviceIdentifier}|${it["req"]}|${it["k"]}|${it["n"]}"
            }
            if (id != null && !sending.add(id)) {
                _state.update { it.copy(duplicates = it.duplicates + 1) }
                continue
            }
            ProtocolHandler.progress(m)?.let { p ->
                updateDevice(d.deviceIdentifier) { it.copy(cache = p) }
                if (p.finished) log("Tutti gli appunti sono sull'orologio (${p.version})")
                continue
            }
            val reply = try {
                handler.handle(m)
            } catch (e: Exception) {
                Log.e(TAG, "richiesta non gestita", e)
                null
            }
            if (reply == null) {
                id?.let { sending.remove(it) }
                continue
            }
            if (!reply.chunkSent) log(reply.description)
            val started = System.currentTimeMillis()
            send(d, reply.message, attempt = 0) { ok ->
                id?.let { sending.remove(it) }
                if (ok && reply.chunkSent) {
                    val ms = (System.currentTimeMillis() - started).coerceAtLeast(1)
                    val bytes = payloadBytes(reply.message)
                    _state.update {
                        val rate = (bytes * 1000L / ms).toInt()
                        it.copy(
                            chunksSent = it.chunksSent + reply.chunks,
                            lastSendMs = ms,
                            bytesPerSecond = if (it.bytesPerSecond == 0) rate else (it.bytesPerSecond * 3 + rate) / 4,
                        )
                    }
                }
            }
        }
    }

    private fun payloadBytes(msg: Map<String, Any>): Int = when (val d = msg["d"]) {
        is String -> d.toByteArray(Charsets.UTF_8).size
        is List<*> -> d.sumOf { (it as? String)?.toByteArray(Charsets.UTF_8)?.size ?: 0 }
        else -> 0
    }

    /** Invio con nuovi tentativi (0,5 s, 1 s, 2 s). */
    private fun send(d: IQDevice, msg: Map<String, Any>, attempt: Int, done: (Boolean) -> Unit) {
        val c = ciq ?: return done(false)
        try {
            c.sendMessage(d, app, msg) { _, _, st ->
                when {
                    st == ConnectIQ.IQMessageStatus.SUCCESS -> done(true)
                    st == ConnectIQ.IQMessageStatus.FAILURE_MESSAGE_TOO_LARGE && msg["op"] == "chunks" &&
                        handler.batchBytes > ProtocolHandler.MIN_BATCH_BYTES -> {
                        // risposte con più pezzi troppo grandi: dimezza; l'orologio ripete la richiesta
                        handler.batchBytes = maxOf(ProtocolHandler.MIN_BATCH_BYTES, handler.batchBytes / 2)
                        log("Messaggio troppo grande: ora al massimo ${handler.batchBytes} byte per risposta")
                        done(false)
                    }
                    st == ConnectIQ.IQMessageStatus.FAILURE_MESSAGE_TOO_LARGE -> {
                        log("Messaggio troppo grande per l'orologio: riduci chunk_bytes in pipeline/rules.yaml")
                        _state.update { it.copy(failures = it.failures + 1) }
                        done(false)
                    }
                    attempt < 3 -> main.postDelayed({ send(d, msg, attempt + 1, done) }, 500L shl attempt)
                    else -> {
                        log("Invio fallito dopo 4 tentativi: $st")
                        _state.update { it.copy(failures = it.failures + 1) }
                        done(false)
                    }
                }
            }
        } catch (e: Exception) {
            log("Invio impossibile: ${e.message}")
            done(false)
        }
    }

    /** Nuovo bundle: avvisa gli orologi che hanno usato l'app negli ultimi minuti. */
    fun notifyUpdate(version: String) {
        if (System.currentTimeMillis() - _state.value.lastRequest > 5 * 60_000) return
        for (d in known.values) {
            send(d, mapOf("op" to "update", "ver" to version), 0) { ok -> if (ok) log("Orologio avvisato del nuovo bundle") }
        }
    }

    private fun log(s: String) {
        Log.i(TAG, s)
        val t = SimpleDateFormat("HH:mm:ss", Locale.ITALY).format(Date())
        _state.update { it.copy(log = (listOf("$t  $s") + it.log).take(40)) }
    }

    companion object {
        private const val TAG = "WatchLink"
    }
}
