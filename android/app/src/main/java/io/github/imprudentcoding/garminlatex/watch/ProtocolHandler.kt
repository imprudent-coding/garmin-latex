package io.github.imprudentcoding.garminlatex.watch

import io.github.imprudentcoding.garminlatex.bundle.Bundle

/**
 * Risposte alle richieste dell'orologio (shared/PROTOCOL.md). Nessuna
 * dipendenza dal Connect IQ SDK: è testata con unit test JVM.
 */
class ProtocolHandler(private val schema: Int, private val bundle: () -> Source?) {

    /**
     * Byte massimi di dati in una risposta con più pezzi (`get` con `c` > 1).
     * Garmin non documenta un limite: se l'invio fallisce con
     * FAILURE_MESSAGE_TOO_LARGE, WatchLink lo dimezza (fino a un pezzo solo).
     */
    @Volatile
    var batchBytes: Int = DEFAULT_BATCH_BYTES

    /** Ciò che serve del bundle (interfaccia per i test). */
    interface Source {
        val schema: Int
        val contentVersion: String
        val indexKey: String
        val indexHash: String
        val indexChunks: Int
        fun resource(key: String): Pair<String, List<String>>? // hash, pezzi
    }

    class BundleSource(private val b: Bundle) : Source {
        override val schema get() = b.manifest.schema
        override val contentVersion get() = b.manifest.contentVersion
        override val indexKey get() = b.manifest.indexKey
        override val indexHash get() = b.manifest.indexHash
        override val indexChunks get() = b.manifest.indexChunks
        override fun resource(key: String) = b.resource(key)?.let { it.hash to it.chunks }
    }

    data class Reply(val message: Map<String, Any>, val chunkSent: Boolean, val description: String, val chunks: Int = 1)

    fun handle(raw: Any?): Reply? {
        val msg = raw as? Map<*, *> ?: return null
        val op = msg["op"]?.toString() ?: return null
        val req = toInt(msg["req"])
        return when (op) {
            "hello" -> hello(msg, req)
            "get" -> get(msg, req)
            else -> null
        }
    }

    private fun hello(msg: Map<*, *>, req: Int): Reply {
        val src = bundle()
        val watchSchema = toInt(msg["schema"])
        if (src == null) {
            return Reply(mapOf("op" to "hello", "ok" to false, "err" to "nobundle", "req" to req), false,
                "hello: nessun bundle sul telefono")
        }
        if (watchSchema != schema || src.schema != schema) {
            return Reply(mapOf("op" to "hello", "ok" to false, "err" to "schema", "schema" to schema, "req" to req), false,
                "hello: schema incompatibile (orologio $watchSchema, telefono $schema, bundle ${src.schema})")
        }
        return Reply(
            mapOf(
                "op" to "hello", "ok" to true, "schema" to schema, "ver" to src.contentVersion,
                "ih" to src.indexHash, "ic" to src.indexChunks, "req" to req,
            ),
            false, "hello: versione ${src.contentVersion}",
        )
    }

    private fun get(msg: Map<*, *>, req: Int): Reply {
        val key = msg["k"]?.toString() ?: ""
        val n = toInt(msg["n"])
        val expected = msg["h"]?.toString() ?: ""
        val src = bundle()
        val res = src?.resource(key)
        if (res == null) {
            return Reply(mapOf("op" to "err", "k" to key, "n" to n, "req" to req, "err" to "notfound"), false,
                "get $key/$n: non trovato")
        }
        val (hash, chunks) = res
        if (expected.isNotEmpty() && expected != hash) {
            return Reply(mapOf("op" to "err", "k" to key, "n" to n, "req" to req, "err" to "stale"), false,
                "get $key/$n: hash vecchio ($expected ≠ $hash)")
        }
        if (n < 0 || n >= chunks.size) {
            return Reply(mapOf("op" to "err", "k" to key, "n" to n, "req" to req, "err" to "notfound"), false,
                "get $key/$n: pezzo inesistente")
        }
        val count = toInt(msg["c"])
        if (count > 1) {
            // più pezzi consecutivi in un solo messaggio, entro batchBytes (almeno uno)
            val out = ArrayList<String>()
            var bytes = 0
            var i = n
            while (i < chunks.size && out.size < count) {
                val b = chunks[i].toByteArray(Charsets.UTF_8).size
                if (out.isNotEmpty() && bytes + b > batchBytes) break
                out.add(chunks[i])
                bytes += b
                i++
            }
            return Reply(
                mapOf("op" to "chunks", "k" to key, "n" to n, "of" to chunks.size, "h" to hash, "d" to out, "req" to req),
                true, "chunks $key ${n + 1}-${n + out.size}/${chunks.size}", chunks = out.size,
            )
        }
        return Reply(
            mapOf("op" to "chunk", "k" to key, "n" to n, "of" to chunks.size, "h" to hash, "d" to chunks[n], "req" to req),
            true, "chunk $key ${n + 1}/${chunks.size}",
        )
    }

    /** Stato della cache sull'orologio (messaggio `progress`, senza risposta). */
    data class WatchProgress(
        val version: String,
        val sections: Int,
        val sectionsTotal: Int,
        val images: Int,
        val imagesTotal: Int,
        val finished: Boolean,
    )

    companion object {
        const val DEFAULT_BATCH_BYTES = 7200
        const val MIN_BATCH_BYTES = 1800

        /** Legge un messaggio `progress` dell'orologio; null se è un altro messaggio. */
        fun progress(raw: Any?): WatchProgress? {
            val msg = raw as? Map<*, *> ?: return null
            if (msg["op"]?.toString() != "progress") return null
            return WatchProgress(
                version = msg["ver"]?.toString() ?: "",
                sections = toInt(msg["sec"]), sectionsTotal = toInt(msg["secs"]),
                images = toInt(msg["img"]), imagesTotal = toInt(msg["imgs"]),
                finished = msg["fin"] == true || msg["fin"]?.toString() == "true",
            )
        }

        fun toInt(v: Any?): Int = when (v) {
            is Number -> v.toInt()
            is String -> v.toIntOrNull() ?: 0
            else -> 0
        }
    }
}
