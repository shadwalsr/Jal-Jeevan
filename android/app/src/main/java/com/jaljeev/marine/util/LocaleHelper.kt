package com.jaljeev.marine.util

import android.content.Context
import android.content.res.Configuration
import android.os.Build
import android.os.LocaleList
import androidx.appcompat.app.AppCompatDelegate
import androidx.core.os.LocaleListCompat
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.util.Locale

data class AppLanguage(
    val code: String,
    val displayName: String,
    val nativeName: String,
    val region: String,
    val sarvamCode: String,
)

object LocaleHelper {
    private const val PREFS_NAME = "jaljeev_locale_prefs"
    private const val KEY_LANGUAGE = "selected_language"

    val SUPPORTED_LANGUAGES = listOf(
        AppLanguage("en", "English", "English", "Universal", "en-IN"),
        AppLanguage("hi", "Hindi", "हिन्दी", "National", "hi-IN"),
        AppLanguage("ta", "Tamil", "தமிழ்", "Tamil Nadu / Coromandel", "ta-IN"),
        AppLanguage("te", "Telugu", "తెలుగు", "Andhra Pradesh / Yanam", "te-IN"),
        AppLanguage("ml", "Malayalam", "മലയാളം", "Kerala / Malabar", "ml-IN"),
        AppLanguage("bn", "Bengali", "বাংলা", "West Bengal / Sundarbans", "bn-IN"),
        AppLanguage("gu", "Gujarati", "ગુજરાતી", "Gujarat / Kathiawar", "gu-IN"),
        AppLanguage("mr", "Marathi", "मराठी", "Maharashtra / Konkan", "mr-IN"),
        AppLanguage("or", "Odia", "ଓଡ଼ିଆ", "Odisha / Utkal Coast", "od-IN"),
        AppLanguage("kn", "Kannada", "ಕನ್ನಡ", "Karnataka / Karavali", "kn-IN"),
    )

    private val _currentLanguageFlow = MutableStateFlow(SUPPORTED_LANGUAGES[0])
    val currentLanguageFlow: StateFlow<AppLanguage> = _currentLanguageFlow.asStateFlow()

    fun init(context: Context) {
        val code = getPersistedLanguage(context)
        val lang = SUPPORTED_LANGUAGES.find { it.code == code } ?: SUPPORTED_LANGUAGES[0]
        _currentLanguageFlow.value = lang
    }

    fun getPersistedLanguage(context: Context): String {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        return prefs.getString(KEY_LANGUAGE, "en") ?: "en"
    }

    fun setLanguage(context: Context, langCode: String) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        prefs.edit().putString(KEY_LANGUAGE, langCode).apply()

        val matched = SUPPORTED_LANGUAGES.find { it.code == langCode } ?: SUPPORTED_LANGUAGES[0]
        _currentLanguageFlow.value = matched

        // Apply to AndroidX AppCompatDelegate (supported on all modern Android versions)
        val localeList = LocaleListCompat.forLanguageTags(langCode)
        AppCompatDelegate.setApplicationLocales(localeList)
    }

    fun wrap(context: Context): Context {
        val langCode = getPersistedLanguage(context)
        val locale = Locale(langCode)
        Locale.setDefault(locale)

        val config = Configuration(context.resources.configuration)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            config.setLocales(LocaleList(locale))
        } else {
            @Suppress("DEPRECATION")
            config.locale = locale
        }

        return context.createConfigurationContext(config)
    }
}
