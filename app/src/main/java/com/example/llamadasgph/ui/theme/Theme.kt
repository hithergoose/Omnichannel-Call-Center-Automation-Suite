package com.example.llamadasgph.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.graphics.Color

val Charcoal = Color(0xFF011536) // GPH_BLUE
val GoldPrimary = Color(0xFF2B64D3) // GPH_ACCENT
val GoldSecondary = Color(0xFF1D4A99) // Hover accent (modified GoldSecondary)
val SurfaceDark = Color(0xFF0B2144) // slightly lighter than GPH_BLUE for surfaces
val TextHigh = Color(0xFFFFFFFF)
val TextMed = Color(0xFFDDDDDD)
val SuccessGreen = Color(0xFF4CAF50)
val ErrorRed = Color(0xFFF44336)

private val DarkColorScheme = darkColorScheme(
    primary = GoldPrimary,
    secondary = GoldSecondary,
    tertiary = SuccessGreen,
    background = Charcoal,
    surface = SurfaceDark,
    onPrimary = Color.White,
    onSecondary = Color.White,
    onBackground = TextHigh,
    onSurface = TextHigh
)

@Composable
fun LlamadasGPHTheme(
    darkTheme: Boolean = true, // Force dark for premium feel
    content: @Composable () -> Unit
) {
    MaterialTheme(
        colorScheme = DarkColorScheme,
        typography = Typography,
        content = content
    )
}