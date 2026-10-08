package io.github.imprudentcoding.garminlatex.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Amber = Color(0xFFFFB54A)
private val Mint = Color(0xFF2E9E78)

@Composable
fun NotesTheme(content: @Composable () -> Unit) {
    val scheme = if (isSystemInDarkTheme()) {
        darkColorScheme(primary = Amber, secondary = Color(0xFF6FE3B4))
    } else {
        lightColorScheme(primary = Color(0xFF9A5B00), secondary = Mint)
    }
    MaterialTheme(colorScheme = scheme, content = content)
}
