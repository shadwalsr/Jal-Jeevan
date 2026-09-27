package com.jaljeev.voice

enum class IndianLanguage(
    val displayName: String,           // shown in UI
    val nativeScript: String,          // shown in native script for low-literacy users
    val bcp47Code: String,             // sent to Sarvam API
    val region: String,                // coastal region tag for auto-select
) {
    ODIA(        "Odia",       "ଓଡ଼ିଆ",      "od-IN",  "east_coast"),
    BENGALI(     "Bengali",    "বাংলা",        "bn-IN",  "bengal"),
    HINDI(       "Hindi",      "हिंदी",         "hi-IN",  "default"),
    MARATHI(     "Marathi",    "मराठी",         "mr-IN",  "west_coast"),
    GUJARATI(    "Gujarati",   "ગુજરાતી",       "gu-IN",  "gujarat"),
    TAMIL(       "Tamil",      "தமிழ்",         "ta-IN",  "south_east"),
    TELUGU(      "Telugu",     "తెలుగు",        "te-IN",  "andhra"),
    KANNADA(     "Kannada",    "ಕನ್ನಡ",        "kn-IN",  "karnataka"),
    MALAYALAM(   "Malayalam",  "മലയാളം",        "ml-IN",  "kerala"),
    PUNJABI(     "Punjabi",    "ਪੰਜਾਬੀ",        "pa-IN",  "punjab"),
    ASSAMESE(    "Assamese",   "অসমীয়া",       "as-IN",  "northeast"),
    URDU(        "Urdu",       "اردو",          "ur-IN",  "urdu_belt"),
    NEPALI(      "Nepali",     "नेपाली",         "ne-IN",  "northeast"),
    KONKANI(     "Konkani",    "कोंकणी",         "kok-IN", "goa"),
    KASHMIRI(    "Kashmiri",   "کٲشُر",         "ks-IN",  "kashmir"),
    SINDHI(      "Sindhi",     "سنڌي",          "sd-IN",  "sindh"),
    SANSKRIT(    "Sanskrit",   "संस्कृत",        "sa-IN",  "classical"),
    SANTALI(     "Santali",    "ᱥᱟᱱᱛᱟᱲᱤ",     "sat-IN", "jharkhand"),
    MANIPURI(    "Manipuri",   "মেইতেই লোন্",    "mni-IN", "northeast"),
    BODO(        "Bodo",       "बड़ो",           "brx-IN", "northeast"),
    MAITHILI(    "Maithili",   "मैथिली",         "mai-IN", "bihar"),
    DOGRI(       "Dogri",      "डोगरी",          "doi-IN", "jammu"),
    AUTO_DETECT( "Auto",       "Auto",           "unknown","auto"),
    ENGLISH(     "English",    "English",        "en-IN",  "english");

    companion object {
        // Given a GPS coastal region hint, return the most likely language
        fun fromRegion(region: String): IndianLanguage =
            entries.firstOrNull { it.region == region } ?: AUTO_DETECT

        // For the language selector dropdown — ordered by coastal relevance
        fun coastalPriority(): List<IndianLanguage> = listOf(
            AUTO_DETECT, ODIA, BENGALI, MARATHI, GUJARATI, MALAYALAM,
            TAMIL, TELUGU, KANNADA, HINDI, PUNJABI, ASSAMESE,
            URDU, KONKANI, ENGLISH
        ) + entries.filter { it !in listOf(
            AUTO_DETECT, ODIA, BENGALI, MARATHI, GUJARATI, MALAYALAM,
            TAMIL, TELUGU, KANNADA, HINDI, PUNJABI, ASSAMESE,
            URDU, KONKANI, ENGLISH
        )}
    }
}
