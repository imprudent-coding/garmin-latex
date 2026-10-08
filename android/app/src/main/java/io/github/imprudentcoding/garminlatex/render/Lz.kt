package io.github.imprudentcoding.garminlatex.render

/**
 * Decompressione LZ dei dati RLE delle immagini (shared/FORMAT.md, schema 2).
 * Implementazione di riferimento: pipeline/gwnotes/lz.py.
 */
object Lz {
    private const val MIN_MATCH = 4

    fun decompress(c: ByteArray, size: Int): ByteArray {
        val out = ByteArray(size)
        var i = 0
        var o = 0
        fun u(k: Int) = c[k].toInt() and 0xFF
        while (i < c.size) {
            val tok = u(i++)
            var ll = tok shr 4
            if (ll == 15) {
                do { val b = u(i++); ll += b } while (b == 255)
            }
            System.arraycopy(c, i, out, o, ll)
            i += ll
            o += ll
            if (i >= c.size) break
            val off = u(i) or (u(i + 1) shl 8)
            i += 2
            var ml = tok and 15
            if (ml == 15) {
                do { val b = u(i++); ml += b } while (b == 255)
            }
            ml += MIN_MATCH
            require(off in 1..o) { "LZ: offset non valido" }
            for (k in 0 until ml) {
                out[o] = out[o - off]
                o++
            }
        }
        require(o == size) { "LZ: attesi $size byte, trovati $o" }
        return out
    }
}
