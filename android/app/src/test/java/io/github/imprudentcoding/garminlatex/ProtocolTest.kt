package io.github.imprudentcoding.garminlatex

import io.github.imprudentcoding.garminlatex.bundle.Bundle
import io.github.imprudentcoding.garminlatex.bundle.BundleException
import io.github.imprudentcoding.garminlatex.bundle.BundleRepository
import io.github.imprudentcoding.garminlatex.watch.ProtocolHandler
import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.io.File
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream

class ProtocolTest {
    private class FakeSource : ProtocolHandler.Source {
        override val schema = 1
        override val contentVersion = "20261008.120000-abc"
        override val indexKey = "idx"
        override val indexHash = "h-idx"
        override val indexChunks = 2
        val res = mapOf("idx" to ("h-idx" to listOf("V|1|x", "C|1|10|T")), "s:a" to ("h-a" to listOf("P\nT1,2,x")))
        override fun resource(key: String) = res[key]
    }

    private val handler = ProtocolHandler(1) { FakeSource() }

    @Test
    fun helloReturnsVersionAndIndex() {
        val r = handler.handle(hashMapOf<Any, Any>("op" to "hello", "schema" to 1, "ver" to "", "req" to 7L))!!
        assertEquals(true, r.message["ok"])
        assertEquals("20261008.120000-abc", r.message["ver"])
        assertEquals(2, r.message["ic"])
        assertEquals(7, r.message["req"])
    }

    @Test
    fun helloWithoutBundle() {
        val r = ProtocolHandler(1) { null }.handle(mapOf("op" to "hello", "schema" to 1))!!
        assertEquals(false, r.message["ok"])
        assertEquals("nobundle", r.message["err"])
    }

    @Test
    fun helloSchemaMismatch() {
        val r = handler.handle(mapOf("op" to "hello", "schema" to 2))!!
        assertEquals("schema", r.message["err"])
    }

    @Test
    fun getChunk() {
        val r = handler.handle(mapOf("op" to "get", "k" to "idx", "n" to 1, "h" to "h-idx", "req" to 3))!!
        assertEquals("chunk", r.message["op"])
        assertEquals("C|1|10|T", r.message["d"])
        assertEquals(2, r.message["of"])
        assertTrue(r.chunkSent)
    }

    @Test
    fun staleAndMissing() {
        assertEquals("stale", handler.handle(mapOf("op" to "get", "k" to "s:a", "n" to 0, "h" to "old"))!!.message["err"])
        assertEquals("notfound", handler.handle(mapOf("op" to "get", "k" to "s:zz", "n" to 0, "h" to ""))!!.message["err"])
        assertEquals("notfound", handler.handle(mapOf("op" to "get", "k" to "s:a", "n" to 5, "h" to ""))!!.message["err"])
        assertNull(handler.handle("non un dizionario"))
    }

    // ------------------------------------------------------------- bundle

    private fun makeBundle(dir: File, schema: Int = 1, corrupt: Boolean = false): File {
        val chunks = listOf("P\nT10,20,ciao", "P\nT10,20,mondo")
        val hash = Bundle.shortHash(chunks.joinToString("\u0000"))
        val idxChunks = listOf("V|1|v1|f|Titolo\nC|1|50|Cap\nS|a|$hash|2|0|50|Sez")
        val idxHash = Bundle.shortHash(idxChunks.joinToString("\u0000"))
        val manifest = JSONObject()
            .put("schema", schema).put("contentVersion", "v1").put("contentHash", "c").put("title", "Titolo")
            .put("chunkBytes", 1800).put("fontId", "f")
            .put("index", JSONObject().put("key", "idx").put("hash", idxHash).put("chunks", 1))
            .put("toc", JSONArray().put(JSONObject().put("title", "Cap").put("sections", JSONArray().put(
                JSONObject().put("id", "a").put("title", "Sez").put("pages", 2).put("key", "s:a").put("hash", hash)))))
            .put("resources", JSONObject()
                .put("s:a", JSONObject().put("hash", hash).put("chunks", 2).put("bytes", 30).put("file", "res/s_a.json"))
                .put("idx", JSONObject().put("hash", idxHash).put("chunks", 1).put("bytes", 30).put("file", "res/idx.json")))
        val f = File(dir, "b.zip")
        ZipOutputStream(f.outputStream()).use { z ->
            fun put(name: String, s: String) {
                z.putNextEntry(ZipEntry(name)); z.write(s.toByteArray()); z.closeEntry()
            }
            put("manifest.json", manifest.toString())
            val sec = if (corrupt) listOf("P\nT10,20,ciao", "alterato") else chunks
            put("res/s_a.json", JSONObject().put("key", "s:a").put("hash", hash).put("chunks", JSONArray(sec)).toString())
            put("res/idx.json", JSONObject().put("key", "idx").put("hash", idxHash).put("chunks", JSONArray(idxChunks)).toString())
        }
        return f
    }

    @Test
    fun bundleOpensAndVerifies() {
        val dir = createTempDir()
        Bundle.open(makeBundle(dir), 1).use { b ->
            assertEquals("v1", b.manifest.contentVersion)
            assertEquals(2, b.resource("s:a")!!.chunks.size)
            assertEquals("Sez", b.manifest.toc[0].sections[0].title)
        }
    }

    @Test
    fun corruptBundleIsRejected() {
        val dir = createTempDir()
        try {
            Bundle.open(makeBundle(dir, corrupt = true), 1)
            fail("atteso errore di hash")
        } catch (e: BundleException) {
            assertTrue(e.message!!.contains("hash"))
        }
    }

    @Test
    fun newerSchemaIsRejected() {
        val dir = createTempDir()
        try {
            Bundle.open(makeBundle(dir, schema = 2), 1)
            fail("atteso errore di schema")
        } catch (e: BundleException) {
            assertTrue(e.message!!.contains("schema"))
        }
    }

    @Test
    fun shortHashMatchesPipeline() {
        // python3 -c "import hashlib;print(hashlib.sha256('a\x00b'.encode()).hexdigest()[:10])"
        assertEquals("59b271ae1b", Bundle.shortHash("a\u0000b"))
    }

    // ------------------------------------------------------------- release

    @Test
    fun picksLatestNotesRelease() {
        val arr = JSONArray()
            .put(JSONObject().put("tag_name", "android-v1.0.0").put("assets", JSONArray()
                .put(JSONObject().put("name", "app.apk").put("browser_download_url", "x"))))
            .put(JSONObject().put("tag_name", "notes-20261008").put("draft", false).put("assets", JSONArray()
                .put(JSONObject().put("name", "notes.pdf").put("browser_download_url", "p"))
                .put(JSONObject().put("name", "notes-bundle.zip").put("id", 5).put("updated_at", "t")
                    .put("browser_download_url", "https://example/b.zip").put("size", 10))))
            .put(JSONObject().put("tag_name", "notes-20261001").put("assets", JSONArray()
                .put(JSONObject().put("name", "notes-bundle.zip").put("browser_download_url", "old"))))
        val a = BundleRepository.parseReleases(arr)
        assertNotNull(a)
        assertEquals("notes-20261008", a!!.tag)
        assertEquals("https://example/b.zip", a.url)
        assertEquals("5@t", a.marker)
    }
}
