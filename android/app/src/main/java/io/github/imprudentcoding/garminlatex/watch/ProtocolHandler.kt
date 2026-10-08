package io.github.imprudentcoding.garminlatex.watch

import io.github.imprudentcoding.garminlatex.bundle.Bundle

/**
 * Risposte alle richieste dell'orologio (shared/PROTOCOL.md). Nessuna
 * dipendenza dal Connect IQ SDK: è testata con unit test JVM.
 */
class ProtocolHandler(private val schema: Int, private val bundle: () -> Source?) {

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

    data class Reply(val message: Map<String, Any>, val chunkSent: Boolean, val description: String)

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
        return Reply(
            mapOf("op" to "chunk", "k" to key, "n" to n, "of" to chunks.size, "h" to hash, "d" to chunks[n], "req" to req),
            true, "chunk $key ${n + 1}/${chunks.size}",
        )
    }

    companion object {
        fun toInt(v: Any?): Int = when (v) {
            is Number -> v.toInt()
            is String -> v.toIntOrNull() ?: 0
            else -> 0
        }
    }
}
