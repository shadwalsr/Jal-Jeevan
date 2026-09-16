package com.jaljeev.marine.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// Marine console palette. Deep navy ground, one blue for interaction, one
// teal for "safe" - the same teal the risk scale uses for LOW, so the app
// never says "good" in a colour the risk scale does not recognise.
val Navy900 = Color(0xFF0B1B2B)
val Navy800 = Color(0xFF12293D)
val Navy700 = Color(0xFF1A3550)
val Navy600 = Color(0xFF2C4A66)
val Blue400 = Color(0xFF4F8FE0)
val Teal400 = Color(0xFF3ECFA8)
val Amber400 = Color(0xFFE3A53D)
val Red400 = Color(0xFFE3675A)
val Ink100 = Color(0xFFE6EEF6)
val Ink300 = Color(0xFFA9BDD1)

/**
 * One dark scheme, on purpose - not a light/dark pair.
 *
 * The screen this app is read on is a phone in daylight glare or at night on
 * open water, and the risk colours (teal / yellow / amber / red) were picked
 * for contrast against this navy ground. Re-tuning them for a light surface
 * would mean two palettes to keep honest, and a MODERATE that looks different
 * depending on the phone's theme setting.
 */
private val JalJeevColors = darkColorScheme(
    primary = Blue400,
    onPrimary = Navy900,
    primaryContainer = Navy700,
    onPrimaryContainer = Ink100,
    secondary = Teal400,
    onSecondary = Navy900,
    secondaryContainer = Navy700,
    onSecondaryContainer = Ink100,
    tertiary = Amber400,
    onTertiary = Navy900,
    background = Navy900,
    onBackground = Ink100,
    surface = Navy800,
    onSurface = Ink100,
    surfaceVariant = Navy700,
    onSurfaceVariant = Ink300,
    outline = Navy600,
    outlineVariant = Navy700,
    error = Red400,
    onError = Navy900,
    errorContainer = Color(0xFF4A1E22),
    onErrorContainer = Color(0xFFFFDAD6),
)

private val JalJeevTypography = Typography(
    titleLarge = TextStyle(fontSize = 22.sp, fontWeight = FontWeight.SemiBold, lineHeight = 28.sp),
    titleMedium = TextStyle(fontSize = 17.sp, fontWeight = FontWeight.SemiBold, lineHeight = 24.sp),
    bodyLarge = TextStyle(fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 21.sp),
    labelLarge = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.Medium),
    labelMedium = TextStyle(fontSize = 12.sp, fontWeight = FontWeight.Medium, letterSpacing = 0.4.sp),
)

@Composable
fun JalJeevTheme(
    @Suppress("UNUSED_PARAMETER") darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = JalJeevColors,
        typography = JalJeevTypography,
        content = content,
    )
}
