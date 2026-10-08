package io.github.imprudentcoding.garminlatex.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.imprudentcoding.garminlatex.NotesApplication
import io.github.imprudentcoding.garminlatex.R
import io.github.imprudentcoding.garminlatex.render.PageRenderer

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PreviewScreen(app: NotesApplication, onOpen: (String) -> Unit, onBack: () -> Unit) {
    val st by app.repo.state.collectAsStateWithLifecycle()
    val m = st.bundle?.manifest
    Scaffold(topBar = {
        TopAppBar(title = { Text(m?.title ?: stringResource(R.string.preview)) }, navigationIcon = {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, null) }
        })
    }) { pad ->
        if (m == null) {
            Text(stringResource(R.string.no_bundle), Modifier.padding(pad).padding(16.dp))
            return@Scaffold
        }
        LazyColumn(Modifier.padding(pad).fillMaxSize()) {
            for (ch in m.toc) {
                item {
                    Text(ch.title, style = MaterialTheme.typography.titleMedium,
                        modifier = Modifier.padding(start = 16.dp, end = 16.dp, top = 16.dp, bottom = 4.dp))
                }
                items(ch.sections) { s ->
                    Column(Modifier.fillMaxWidth().clickable { onOpen(s.id) }.padding(horizontal = 24.dp, vertical = 10.dp)) {
                        Text(s.title)
                        Text(stringResource(R.string.pages, s.pages), style = MaterialTheme.typography.bodySmall)
                    }
                    HorizontalDivider()
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReaderScreen(app: NotesApplication, sectionId: String, onBack: () -> Unit) {
    val st by app.repo.state.collectAsStateWithLifecycle()
    val bundle = st.bundle
    val ctx = LocalContext.current
    val renderer = remember { PageRenderer(ctx.applicationContext) }
    val section = bundle?.manifest?.toc?.flatMap { it.sections }?.firstOrNull { it.id == sectionId }
    val pages = remember(bundle, sectionId) {
        section?.let { s -> bundle.resource(s.key)?.let { PageRenderer.pages(it.chunks) } } ?: emptyList()
    }
    var page by rememberSaveable(sectionId) { mutableIntStateOf(0) }
    Scaffold(topBar = {
        TopAppBar(title = { Text(section?.title ?: "") }, navigationIcon = {
            IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, null) }
        })
    }) { pad ->
        Column(Modifier.padding(pad).fillMaxSize().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)) {
            if (bundle == null || pages.isEmpty()) {
                Text(stringResource(R.string.no_bundle))
                return@Column
            }
            val bmp = remember(bundle, sectionId, page) { renderer.render(bundle, pages[page], page + 1, pages.size) }
            Box(Modifier.fillMaxWidth().aspectRatio(1f).clip(CircleShape).pointerInput(page, pages.size) {
                detectTapGestures { off ->
                    page = if (off.y < size.height / 2) (page - 1).coerceAtLeast(0) else (page + 1).coerceAtMost(pages.size - 1)
                }
            }) {
                Image(bmp.asImageBitmap(), null, Modifier.fillMaxSize(), filterQuality = FilterQuality.None)
            }
            Text(stringResource(R.string.preview_hint), style = MaterialTheme.typography.bodySmall)
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                OutlinedButton(enabled = page > 0, onClick = { page-- }) { Text("‹") }
                Text("${page + 1} / ${pages.size}", Modifier.align(Alignment.CenterVertically))
                OutlinedButton(enabled = page < pages.size - 1, onClick = { page++ }) { Text("›") }
            }
        }
    }
}
