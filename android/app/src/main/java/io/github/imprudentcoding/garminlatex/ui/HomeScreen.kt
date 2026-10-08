package io.github.imprudentcoding.garminlatex.ui

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.text.format.DateUtils
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import io.github.imprudentcoding.garminlatex.NotesApplication
import io.github.imprudentcoding.garminlatex.R
import io.github.imprudentcoding.garminlatex.watch.AppStatus
import io.github.imprudentcoding.garminlatex.watch.SdkStatus
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(app: NotesApplication, onPreview: () -> Unit, onSettings: () -> Unit) {
    val bundleState by app.repo.state.collectAsStateWithLifecycle()
    val watch by app.watch.state.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    val ctx = LocalContext.current

    Scaffold(topBar = {
        TopAppBar(title = { Text(stringResource(R.string.app_name)) }, actions = {
            IconButton(onClick = onSettings) { Icon(Icons.Filled.Settings, stringResource(R.string.settings)) }
        })
    }) { pad ->
        Column(
            Modifier.padding(pad).fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // ------------------------------------------------ appunti
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(stringResource(R.string.notes), style = MaterialTheme.typography.titleMedium)
                    val b = bundleState.bundle
                    if (b == null) {
                        Text(stringResource(R.string.no_bundle))
                    } else {
                        val m = b.manifest
                        Text(m.title, style = MaterialTheme.typography.bodyLarge)
                        Text(stringResource(R.string.bundle_info, m.toc.size, m.toc.sumOf { it.sections.size },
                            b.file.length() / 1024))
                        Text(stringResource(R.string.bundle_version, m.contentVersion), style = MaterialTheme.typography.bodySmall)
                        bundleState.release?.let { Text("Release: $it", style = MaterialTheme.typography.bodySmall) }
                    }
                    if (bundleState.lastCheck > 0) {
                        Text(stringResource(R.string.last_check,
                            DateUtils.getRelativeTimeSpanString(bundleState.lastCheck).toString()),
                            style = MaterialTheme.typography.bodySmall)
                    }
                    bundleState.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                        Button(enabled = !bundleState.checking, onClick = {
                            scope.launch { app.repo.checkForUpdates(force = false) }
                        }) { Text(stringResource(R.string.check_updates)) }
                        if (b != null) OutlinedButton(onClick = onPreview) { Text(stringResource(R.string.preview)) }
                        if (bundleState.checking) CircularProgressIndicator(Modifier.height(24.dp))
                    }
                    bundleState.progress?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                }
            }

            // ------------------------------------------------ orologio
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(stringResource(R.string.watch), style = MaterialTheme.typography.titleMedium)
                    when (watch.sdk) {
                        SdkStatus.GCM_NOT_INSTALLED -> {
                            Text(stringResource(R.string.gcm_missing), color = MaterialTheme.colorScheme.error)
                            Button(onClick = { openGarminConnectStore(ctx) }) { Text(stringResource(R.string.install_gcm)) }
                        }
                        SdkStatus.GCM_UPGRADE_NEEDED -> {
                            Text(stringResource(R.string.gcm_upgrade), color = MaterialTheme.colorScheme.error)
                            Button(onClick = { openGarminConnectStore(ctx) }) { Text(stringResource(R.string.update_gcm)) }
                        }
                        SdkStatus.ERROR -> Text(stringResource(R.string.sdk_error, watch.error ?: "?"),
                            color = MaterialTheme.colorScheme.error)
                        SdkStatus.STARTING -> Text(stringResource(R.string.sdk_starting))
                        SdkStatus.STOPPED -> Text(stringResource(R.string.sdk_stopped))
                        SdkStatus.READY -> {
                            if (watch.simulator) Text(stringResource(R.string.simulator_mode), style = MaterialTheme.typography.bodySmall)
                            if (watch.devices.isEmpty()) Text(stringResource(R.string.no_devices))
                            for (d in watch.devices) {
                                Text(d.name, style = MaterialTheme.typography.bodyLarge)
                                Text(when (d.status) {
                                    "CONNECTED" -> stringResource(R.string.dev_connected)
                                    "NOT_CONNECTED" -> stringResource(R.string.dev_not_connected)
                                    "NOT_PAIRED" -> stringResource(R.string.dev_not_paired)
                                    else -> d.status
                                })
                                Text(when (d.app) {
                                    AppStatus.INSTALLED -> stringResource(R.string.app_installed, d.appVersion)
                                    AppStatus.NOT_INSTALLED -> stringResource(R.string.app_not_installed)
                                    AppStatus.NOT_SUPPORTED -> stringResource(R.string.app_not_supported)
                                    AppStatus.UNKNOWN -> stringResource(R.string.app_unknown)
                                }, color = if (d.app == AppStatus.INSTALLED) MaterialTheme.colorScheme.primary
                                else MaterialTheme.colorScheme.error)
                                if (d.status == "CONNECTED" && d.app == AppStatus.INSTALLED) {
                                    OutlinedButton(onClick = { app.watch.openWatchApp(d.id) }) {
                                        Text(stringResource(R.string.open_on_watch))
                                    }
                                }
                            }
                        }
                    }
                    Text(stringResource(R.string.sync_stats, watch.chunksSent, watch.failures,
                        if (watch.lastRequest > 0) DateUtils.getRelativeTimeSpanString(watch.lastRequest).toString() else "–"),
                        style = MaterialTheme.typography.bodySmall)
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(onClick = { app.watch.refreshDevices() }) { Text(stringResource(R.string.refresh)) }
                        OutlinedButton(onClick = { app.watch.restart() }) { Text(stringResource(R.string.restart_link)) }
                    }
                }
            }

            // ------------------------------------------------ registro
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp)) {
                    Text(stringResource(R.string.log), style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(6.dp))
                    if (watch.log.isEmpty()) Text("–")
                    for (l in watch.log.take(15)) Text(l, fontFamily = FontFamily.Monospace, fontSize = 11.sp)
                }
            }
        }
    }
}

fun openGarminConnectStore(ctx: Context) {
    val pkg = "com.garmin.android.apps.connectmobile"
    try {
        ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$pkg")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (e: ActivityNotFoundException) {
        ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=$pkg"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}
