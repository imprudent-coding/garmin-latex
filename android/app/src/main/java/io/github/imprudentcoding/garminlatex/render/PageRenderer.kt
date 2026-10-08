package io.github.imprudentcoding.garminlatex.render

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.Rect
import android.util.Base64
import io.github.imprudentcoding.garminlatex.bundle.Bundle

/**
 * Disegna le pagine come l'orologio (shared/FORMAT.md), con gli stessi font bitmap.
 * Implementazione di riferimento: pipeline/gwnotes/preview.py.
 */
class PageRenderer(context: Context) {
    private class Glyph(val x: Int, val y: Int, val w: Int, val h: Int, val xo: Int, val yo: Int, val adv: Int)

    private class Font(val base: Int, val atlas: Bitmap, val glyphs: Map<Int, Glyph>) {
        fun width(s: String): Int = s.codePoints().toArray().sumOf { glyphs[it]?.adv ?: 0 }
    }

    private val fonts: Map<String, Font> = listOf("body", "bold", "small").associateWith { loadFont(context, it) }
    private val images = object : LinkedHashMap<String, Bitmap>(8, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, Bitmap>?) = size > 12
    }
    private val glyphPaint = Paint().apply { isFilterBitmap = false }
    private val paint = Paint().apply { isAntiAlias = false }

    private fun loadFont(context: Context, name: String): Font {
        val fnt = context.assets.open("$name.fnt").bufferedReader().readText()
        val common = Regex("""^common .*$""", RegexOption.MULTILINE).find(fnt)!!.value
        val base = Regex("""base=(\d+)""").find(common)!!.groupValues[1].toInt()
        val file = Regex("""page id=0 file="([^"]+)"""").find(fnt)!!.groupValues[1]
        val gray = context.assets.open(file).use { BitmapFactory.decodeStream(it) }
        // atlante in scala di grigi -> maschera alpha (il colore lo dà il Paint)
        val px = IntArray(gray.width * gray.height)
        gray.getPixels(px, 0, gray.width, 0, 0, gray.width, gray.height)
        for (i in px.indices) px[i] = Color.argb(Color.red(px[i]), 255, 255, 255)
        val atlas = Bitmap.createBitmap(px, gray.width, gray.height, Bitmap.Config.ARGB_8888)
        val glyphs = HashMap<Int, Glyph>()
        for (m in Regex("""^char (.*)$""", RegexOption.MULTILINE).findAll(fnt)) {
            val d = Regex("""(\w+)=(-?\d+)""").findAll(m.groupValues[1]).associate { it.groupValues[1] to it.groupValues[2].toInt() }
            glyphs[d.getValue("id")] = Glyph(d.getValue("x"), d.getValue("y"), d.getValue("width"), d.getValue("height"),
                d.getValue("xoffset"), d.getValue("yoffset"), d.getValue("xadvance"))
        }
        return Font(base, atlas, glyphs)
    }

    private fun drawString(c: Canvas, f: Font, x0: Int, top: Int, s: String, color: Int): Int {
        var x = x0
        glyphPaint.colorFilter = android.graphics.PorterDuffColorFilter(color, android.graphics.PorterDuff.Mode.MULTIPLY)
        for (cp in s.codePoints()) {
            val g = f.glyphs[cp] ?: continue
            if (g.w > 0 && g.h > 0) {
                c.drawBitmap(f.atlas, Rect(g.x, g.y, g.x + g.w, g.y + g.h),
                    Rect(x + g.xo, top + g.yo, x + g.xo + g.w, top + g.yo + g.h), glyphPaint)
            }
            x += g.adv
        }
        return x
    }

    // ------------------------------------------------------------- testo ricco
    private data class Open(val kind: Int, val param: Int, val x: Int)

    fun drawText(c: Canvas, x0: Int, baseline: Int, text: String) {
        val stack = ArrayList<Open>()
        var x = x0
        val run = StringBuilder()
        fun font(): Font {
            if (stack.any { it.kind == 3 || it.kind == 4 || it.kind == 17 }) return fonts.getValue("small")
            if (stack.any { it.kind == 1 }) return fonts.getValue("bold")
            return fonts.getValue("body")
        }
        fun offset(n: Int = stack.size) = stack.take(n).sumOf { if (it.kind == 3) -it.param else if (it.kind == 4) it.param else 0 }
        fun color(n: Int = stack.size) = PALETTE[stack.take(n).lastOrNull { it.kind == 2 }?.param ?: 0] ?: PALETTE.getValue(0)
        fun flush() {
            if (run.isEmpty()) return
            val f = font()
            x = drawString(c, f, x, baseline - offset() - f.base, run.toString(), color())
            run.clear()
        }
        val cps = text.codePoints().toArray()
        var i = 0
        while (i < cps.size) {
            val cp = cps[i]
            if (cp in 0xE000 until 0xE100) {
                flush()
                val code = cp - 0xE000
                if (code == 15) {
                    if (stack.isNotEmpty()) {
                        val o = stack.removeAt(stack.size - 1)
                        decor(c, o.kind, o.param, o.x, x, baseline - offset(), color())
                    }
                    i += 1
                } else {
                    val p = if (i + 1 < cps.size) cps[i + 1] - 0x100 else 0
                    if (code == 16) x += p else stack.add(Open(code, p, x))
                    i += 2
                }
                continue
            }
            run.appendCodePoint(cp)
            i++
        }
        flush()
    }

    private fun decor(c: Canvas, kind: Int, p: Int, sx: Int, ex: Int, base: Int, col: Int) {
        paint.color = col
        paint.strokeWidth = 2f
        paint.style = Paint.Style.FILL
        val mid = (sx + ex) / 2f
        when (kind) {
            5 -> c.drawRect(sx.toFloat(), (base + p).toFloat(), ex.toFloat(), (base + p + 2).toFloat(), paint)
            6 -> {
                c.drawRect(sx.toFloat(), (base + p).toFloat(), ex.toFloat(), (base + p + 2).toFloat(), paint)
                c.drawRect(sx.toFloat(), (base + p + 4).toFloat(), ex.toFloat(), (base + p + 6).toFloat(), paint)
            }
            7 -> {
                val y = (base - p).toFloat()
                c.drawLine(mid - 5, y + 4, mid, y, paint)
                c.drawLine(mid, y, mid + 5, y + 4, paint)
            }
            8 -> c.drawRect(mid - 1, (base - p - 2).toFloat(), mid + 2, (base - p + 1).toFloat(), paint)
            9 -> {
                c.drawRect(mid - 4, (base - p - 2).toFloat(), mid - 1, (base - p + 1).toFloat(), paint)
                c.drawRect(mid + 2, (base - p - 2).toFloat(), mid + 5, (base - p + 1).toFloat(), paint)
            }
            10 -> {
                val y = (base - p).toFloat()
                val path = Path().apply { moveTo(mid - 6, y + 1); lineTo(mid - 3, y - 2); lineTo(mid + 3, y + 1); lineTo(mid + 6, y - 2) }
                paint.style = Paint.Style.STROKE
                c.drawPath(path, paint)
            }
            11 -> c.drawRect(sx.toFloat(), (base - p - 1).toFloat(), ex.toFloat(), (base - p + 1).toFloat(), paint)
            12, 13 -> {
                val y = (if (kind == 12) base - p else base + p).toFloat()
                c.drawRect(sx.toFloat(), y - 1, ex.toFloat(), y + 1, paint)
                c.drawLine(ex - 5f, y - 4, ex - 1f, y, paint)
                c.drawLine(ex - 1f, y, ex - 5f, y + 3, paint)
            }
        }
    }

    // ------------------------------------------------------------- immagini
    private fun image(bundle: Bundle, key: String): Bitmap? {
        images[key]?.let { return it }
        val res = bundle.resource(key) ?: return null
        val s = res.chunks.joinToString("")
        val bar = s.indexOf('|')
        val head = s.substring(0, bar).split(",").map { it.toInt() }
        val w = head[0]
        val h = head[1]
        val packed = Base64.decode(s.substring(bar + 1), Base64.DEFAULT)
        // schema 2: quarto campo = byte RLE dopo la decompressione LZ
        val rle = if (head.size >= 4) Lz.decompress(packed, head[3]) else packed
        val px = IntArray(w * h)
        var i = 0
        for (b in rle) {
            val v = (b.toInt() shr 6) and 3
            val len = (b.toInt() and 63) + 1
            val col = LEVELS[v]
            for (k in 0 until len) if (i < px.size) px[i++] = col
        }
        val bmp = Bitmap.createBitmap(px, w, h, Bitmap.Config.ARGB_8888)
        images[key] = bmp
        return bmp
    }

    // ------------------------------------------------------------- pagina
    fun render(bundle: Bundle, page: String, pageNo: Int, total: Int): Bitmap {
        val out = Bitmap.createBitmap(390, 390, Bitmap.Config.ARGB_8888)
        val c = Canvas(out)
        c.drawColor(Color.BLACK)
        val clip = Path().apply { addCircle(195f, 195f, 195f, Path.Direction.CW) }
        c.clipPath(clip)
        for (line in page.split("\n")) {
            if (line.length < 2) continue
            val body = line.substring(1)
            when (line[0]) {
                'T' -> {
                    val f = body.split(",", limit = 3)
                    if (f.size == 3) drawText(c, f[0].toInt(), f[1].toInt(), f[2])
                }
                'I' -> {
                    val f = body.split(",", limit = 7)
                    val x = f[0].toInt(); val y = f[1].toInt(); val w = f[2].toInt(); val h = f[3].toInt(); val sy = f[4].toInt()
                    val bmp = image(bundle, f[5])
                    if (bmp != null) c.drawBitmap(bmp, Rect(0, sy, w, sy + h), Rect(x, y, x + w, y + h), null)
                }
                'R' -> {
                    val f = body.split(",").map { it.toInt() }
                    paint.color = PALETTE[f[4]] ?: Color.WHITE
                    paint.style = Paint.Style.FILL
                    c.drawRect(f[0].toFloat(), f[1].toFloat(), (f[0] + f[2]).toFloat(), (f[1] + f[3]).toFloat(), paint)
                }
            }
        }
        val label = "$pageNo/$total"
        val small = fonts.getValue("small")
        drawString(c, small, 195 - small.width(label) / 2, 362, label, PALETTE.getValue(2))
        return out
    }

    companion object {
        val PALETTE = mapOf(
            0 to Color.rgb(255, 255, 255), 1 to Color.rgb(255, 181, 74), 2 to Color.rgb(154, 154, 154),
            3 to Color.rgb(127, 212, 255), 4 to Color.rgb(111, 227, 180), 5 to Color.rgb(127, 212, 255),
            6 to Color.rgb(255, 107, 107),
        )
        val LEVELS = intArrayOf(Color.BLACK, Color.rgb(85, 85, 85), Color.rgb(170, 170, 170), Color.WHITE)

        /** Pagine di una sezione: pezzi concatenati e divisi alle righe "P". */
        fun pages(chunks: List<String>): List<String> {
            val all = chunks.joinToString("\n")
            return all.removePrefix("P\n").split("\nP\n")
        }
    }
}
