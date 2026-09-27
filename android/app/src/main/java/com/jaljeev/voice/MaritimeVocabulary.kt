package com.jaljeev.voice

object MaritimeVocabulary {

    val INDIAN_PORTS = listOf(
        "Paradip", "Haldia", "Kolkata", "Dhamra", "Gopalpur",
        "Visakhapatnam", "Kakinada", "Gangavaram", "Krishnapatnam",
        "Chennai", "Ennore", "Tuticorin", "Kochi", "Mangaluru",
        "New Mangalore", "Mundra", "Kandla", "Pipavav", "Dahej",
        "Hazira", "Mumbai", "JNPT", "Nhava Sheva", "Mormugao",
        "Goa Port", "Karaikal", "Nagapattinam", "Cuddalore"
    )

    val VESSEL_TERMS = listOf(
        "trawler", "gillnet", "purse seine", "dhow", "catamaran",
        "mechanized boat", "country boat", "fishing vessel",
        "draft", "freeboard", "squat", "UKC", "ballast"
    )

    val MARINE_SAFETY_TERMS = listOf(
        "significant wave height", "swell", "wave period",
        "cyclone", "depression", "trough", "storm surge",
        "Potential Fishing Zone", "PFZ", "EEZ",
        "Marine Protected Area", "no-go zone",
        "mean sea level", "tidal variation", "EOT20"
    )

    val ISRO_SPECIFIC = listOf(
        "INCOIS", "MOSDAC", "ISRO", "EOS-06", "OCM-3",
        "chlorophyll", "sea surface temperature", "SST",
        "JalJeev", "SIH", "IBTrACS", "GEBCO"
    )

    // Returns top 50 keyterms prioritized by maritime relevance
    fun getKeyterms(): List<String> =
        (INDIAN_PORTS + VESSEL_TERMS + MARINE_SAFETY_TERMS + ISRO_SPECIFIC)
            .take(50)

    // Post-processing: fix known Sarvam mishearings for Indian maritime terms
    val CORRECTIONS = mapOf(
        "para deep" to "Paradip",
        "para dip" to "Paradip",
        "paradip port" to "Paradip",
        "cochin" to "Kochi",
        "vizag" to "Visakhapatnam",
        "vishakha" to "Visakhapatnam",
        "fishing zone" to "Potential Fishing Zone",
        "jnpt" to "JNPT",
        "haldia port" to "Haldia",
        "nhava sheva" to "Nhava Sheva",
        "kakinada" to "Kakinada",
    )

    fun applyCorrections(transcript: String): String {
        var result = transcript
        CORRECTIONS.forEach { (wrong, correct) ->
            result = result.replace(wrong, correct, ignoreCase = true)
        }
        return result
    }
}
