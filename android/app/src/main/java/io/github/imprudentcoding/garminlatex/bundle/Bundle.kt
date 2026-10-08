package io.github.imprudentcoding.garminlatex.bundle

import org.json.JSONObject
import java.io.Closeable
import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipFile

/** Formato: shared/FORMAT.md */
data class ResourceInfo(val key: String, val hash: String, val chunks: Int, val bytes: Int, val file: String)

data class TocSection(val id: String, val title: String, val pages: Int, val key: String, val hash: String)

data class TocChapter(val title: String, val sections: List<TocSection>)

data class Manifest(
    val schema: Int,
    val contentVersion: String,
    val contentHash: String,
    val generatedAt: String,
    val sourceCommit: String,
    val title: String,
    val fontId: String,
    val chunkBytes: Int,
    val indexKey: String,
    val indexHash: String,
    val indexChunks: Int,
    val toc: List<TocChapter>,
    val resources: Map<String, ResourceInfo>,
) {
    companion object {
        fun parse(text: String): Manifest {
            val o = JSONObject(text)
            val idx = o.getJSONObject("index")
            val res = o.getJSONObject("resources")
            val resources = buildMap {
                for (k in res.keys()) {
                    val r = res.getJSONObject(k)
                    put(k, ResourceInfo(k, r.getString("hash"), r.getInt("chunks"), r.optInt("bytes"), r.getString("file")))
                }
            }
            val tocArr = o.getJSONArray("toc")
            val toc = (0 until tocArr.length()).map { i ->
                val c = tocArr.getJSONObject(i)
                val secs = c.getJSONArray("sections")
                TocChapter(c.getString("title"), (0 until secs.length()).map { j ->
                    val s = secs.getJSONObject(j)
                    TocSection(s.getString("id"), s.getString("title"), s.getInt("pages"), s.getString("key"),
                        s.getString("hash"))
                })
            }
            return Manifest(
                schema = o.getInt("schema"),
                contentVersion = o.getString("contentVersion"),
                contentHash = o.optString("contentHash"),
                generatedAt = o.optString("generatedAt"),
                sourceCommit = o.optString("sourceCommit"),
                title = o.optString("title"),
                fontId = o.optString("fontId"),
                chunkBytes = o.optInt("chunkBytes", 1800),
                indexKey = idx.getString("key"),
                indexHash = idx.getString("hash"),
                indexChunks = idx.getInt("chunks"),
                toc = toc,
                resources = resources,
            )
        }
    }
}

/** Risorsa decodificata: pezzi così come vanno inviati all'orologio. */
data class Resource(val key: String, val hash: String, val chunks: List<String>)

class BundleException(message: String) : Exception(message)

/** Bundle aperto su disco; legge le risorse dallo zip quando servono. */
class Bundle private constructor(val file: File, val manifest: Manifest) : Closeable {
    private val zip = ZipFile(file)
    private val cache = object : LinkedHashMap<String, Resource>(16, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Resource>?) = size > 24
    }

    @Synchronized
    fun resource(key: String): Resource? {
        cache[key]?.let { return it }
        val info = manifest.resources[key] ?: return null
        val entry = zip.getEntry(info.file) ?: return null
        val text = zip.getInputStream(entry).use { it.readBytes().toString(Charsets.UTF_8) }
        val o = JSONObject(text)
        val arr = o.getJSONArray("chunks")
        val res = Resource(key, o.getString("hash"), (0 until arr.length()).map { arr.getString(it) })
        cache[key] = res
        return res
    }

    override fun close() = zip.close()

    companion object {
        /** Apre e verifica il bundle: schema supportato e hash di tutte le risorse. */
        fun open(file: File, maxSchema: Int, verify: Boolean = true): Bundle {
            val manifest = ZipFile(file).use { z ->
                val e = z.getEntry("manifest.json") ?: throw BundleException("manifest.json mancante")
                Manifest.parse(z.getInputStream(e).use { it.readBytes().toString(Charsets.UTF_8) })
            }
            if (manifest.schema > maxSchema) {
                throw BundleException("schema ${manifest.schema} non supportato (max $maxSchema): aggiorna l'app")
            }
            val b = Bundle(file, manifest)
            if (verify) {
                for ((key, info) in manifest.resources) {
                    val r = b.resource(key) ?: run { b.close(); throw BundleException("risorsa mancante: $key") }
                    if (r.chunks.size != info.chunks || shortHash(r.chunks.joinToString("\u0000")) != info.hash) {
                        b.close()
                        throw BundleException("hash non valido per $key")
                    }
                }
                b.cache.clear()
            }
            return b
        }

        /** Come bundle.short_hash della pipeline: sha256 esadecimale, primi n caratteri. */
        fun shortHash(s: String, n: Int = 10): String {
            val d = MessageDigest.getInstance("SHA-256").digest(s.toByteArray(Charsets.UTF_8))
            return d.joinToString("") { "%02x".format(it) }.substring(0, n)
        }
    }
}
