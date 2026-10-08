package io.github.imprudentcoding.garminlatex.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import io.github.imprudentcoding.garminlatex.BuildConfig
import io.github.imprudentcoding.garminlatex.NotesApplication
import io.github.imprudentcoding.garminlatex.R
import io.github.imprudentcoding.garminlatex.watch.WatchService
import io.github.imprudentcoding.garminlatex.work.UpdateWorker

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(app: NotesApplication, onBack: () -> Unit) {
    val s = app.settings
    val ctx = LocalContext.current
    var repo by remember { mutableStateOf(s.repo) }
    var hours by remember { mutableIntStateOf(s.autoUpdateHours) }
    var sim by remember { mutableStateOf(s.simulator) }
    var keep by remember { mutableStateOf(s.keepAlive) }
    Scaffold(topBar = {
        TopAppBar(title = { Text(stringResource(R.string.settings)) }, navigationIcon = {
            IconButton(onClick = { s.repo = repo; onBack() }) { Icon(Icons.AutoMirrored.Filled.ArrowBack, null) }
        })
    }) { pad ->
        Column(Modifier.padding(pad).padding(16.dp).verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)) {
            OutlinedTextField(repo, { repo = it; s.repo = it }, Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.repo_label)) }, singleLine = true,
                supportingText = { Text(stringResource(R.string.repo_help)) })

            Text(stringResource(R.string.auto_update), style = MaterialTheme.typography.titleSmall)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                for (h in listOf(0, 1, 6, 24)) {
                    FilterChip(selected = hours == h, onClick = {
                        hours = h
                        s.autoUpdateHours = h
                        UpdateWorker.schedule(ctx, h)
                    }, label = { Text(if (h == 0) stringResource(R.string.off) else "${h} h") })
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.keep_alive))
                    Text(stringResource(R.string.keep_alive_help), style = MaterialTheme.typography.bodySmall)
                }
                Switch(keep, {
                    keep = it
                    s.keepAlive = it
                    if (it) WatchService.start(ctx) else WatchService.stop(ctx)
                })
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(stringResource(R.string.simulator))
                    Text(stringResource(R.string.simulator_help), style = MaterialTheme.typography.bodySmall)
                }
                Switch(sim, {
                    sim = it
                    s.simulator = it
                    app.watch.restart()
                })
            }

            Text(stringResource(R.string.about, BuildConfig.VERSION_NAME, BuildConfig.WATCH_APP_ID),
                style = MaterialTheme.typography.bodySmall)
        }
    }
}
