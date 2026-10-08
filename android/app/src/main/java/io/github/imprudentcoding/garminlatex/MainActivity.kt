package io.github.imprudentcoding.garminlatex

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.ContextCompat
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import io.github.imprudentcoding.garminlatex.ui.HomeScreen
import io.github.imprudentcoding.garminlatex.ui.NotesTheme
import io.github.imprudentcoding.garminlatex.ui.PreviewScreen
import io.github.imprudentcoding.garminlatex.ui.ReaderScreen
import io.github.imprudentcoding.garminlatex.ui.SettingsScreen
import io.github.imprudentcoding.garminlatex.watch.WatchService

class MainActivity : ComponentActivity() {
    private val askNotifications = registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val app = application as NotesApplication
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            // serve per la notifica del servizio e per "nuovi appunti disponibili"
            askNotifications.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        if (app.settings.keepAlive) WatchService.start(this) else app.watch.start()
        setContent {
            NotesTheme {
                val nav = rememberNavController()
                NavHost(nav, startDestination = "home") {
                    composable("home") {
                        HomeScreen(app, onPreview = { nav.navigate("preview") }, onSettings = { nav.navigate("settings") })
                    }
                    composable("preview") {
                        PreviewScreen(app, onOpen = { id -> nav.navigate("reader/$id") }, onBack = { nav.popBackStack() })
                    }
                    composable("reader/{id}") { e ->
                        ReaderScreen(app, e.arguments?.getString("id") ?: "", onBack = { nav.popBackStack() })
                    }
                    composable("settings") {
                        SettingsScreen(app, onBack = { nav.popBackStack() })
                    }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        (application as NotesApplication).watch.refreshDevices()
    }
}
