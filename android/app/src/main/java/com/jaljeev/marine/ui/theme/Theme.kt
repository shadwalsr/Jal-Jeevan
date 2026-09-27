package com.jaljeev.marine.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// Paper nautical chart palette matching frontend/src/app.css:
// 1. Color is reserved ENTIRELY for risk and exclusions. The interface is black, white and grey.
// 2. Monospace & tabular measurements.
// 3. Hairline borders, no shadows, no colored bubble cards.
val Paper = Color(0xFFFFFFFF)
val Ink = Color(0xFF111111)
val Ink2 = Color(0xFF5A5A5A)
val Field = Color(0xFFF6F6F4)
val Rule = Color(0x1F111111)        // rgba(17, 17, 17, 0.12)
val RuleHeavy = Color(0x47111111)   // rgba(17, 17, 17, 0.28)

// Risk scale hues
val RiskLow = Color(0xFF3ECFA8)
val RiskModerate = Color(0xFFD9C94F)
val RiskHigh = Color(0xFFE3A53D)
val RiskExtreme = Color(0xFFE3675A)
val Exclusion = Color(0xFFC2185B)
val PortBlue = Color(0xFF4F8FE0)

// Text-safe darkenings of the same hues — used for type on white ground
val RiskLowInk = Color(0xFF0E7C63)
val RiskModerateInk = Color(0xFF6B6410)
val RiskHighInk = Color(0xFF8A5A05)
val RiskExtremeInk = Color(0xFFA8342A)
val ExclusionInk = Color(0xFFA3145E)

private val JalJeevColors = lightColorScheme(
    primary = Ink,
    onPrimary = Paper,
    primaryContainer = Field,
    onPrimaryContainer = Ink,
    secondary = PortBlue,
    onSecondary = Paper,
    secondaryContainer = Field,
    onSecondaryContainer = Ink,
    tertiary = RiskHighInk,
    onTertiary = Paper,
    tertiaryContainer = Color(0xFFFFF8EE),
    onTertiaryContainer = RiskHighInk,
    background = Paper,
    onBackground = Ink,
    surface = Paper,
    onSurface = Ink,
    surfaceVariant = Field,
    onSurfaceVariant = Ink2,
    outline = Rule,
    outlineVariant = RuleHeavy,
    error = Exclusion,
    onError = Paper,
    errorContainer = Color(0xFFFDF2F4),
    onErrorContainer = ExclusionInk,
)

private val JalJeevTypography = Typography(
    titleLarge = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.SemiBold, lineHeight = 26.sp, letterSpacing = (-0.2).sp),
    titleMedium = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.SemiBold, lineHeight = 22.sp),
    bodyLarge = TextStyle(fontSize = 15.sp, lineHeight = 22.sp),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 20.sp),
    labelLarge = TextStyle(fontSize = 13.sp, fontWeight = FontWeight.Medium),
    labelMedium = TextStyle(fontSize = 12.sp, fontWeight = FontWeight.Normal, letterSpacing = 0.2.sp),
    labelSmall = TextStyle(fontSize = 11.sp, fontWeight = FontWeight.Normal, fontFamily = androidx.compose.ui.text.font.FontFamily.Monospace),
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
