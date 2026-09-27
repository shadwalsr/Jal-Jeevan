package com.jaljeev.voice

import com.google.gson.annotations.SerializedName

data class SarvamResponse(
    @SerializedName("request_id")           val requestId: String? = null,
    @SerializedName("transcript")           val transcript: String,
    @SerializedName("language_code")        val languageCode: String? = null,
    @SerializedName("language_probability") val languageProbability: Double? = null,
    @SerializedName("timestamps")           val timestamps: SarvamTimestamps? = null,
)

data class SarvamTimestamps(
    @SerializedName("words")              val words: List<String> = emptyList(),
    @SerializedName("start_time_seconds") val startTimes: List<Double> = emptyList(),
    @SerializedName("end_time_seconds")   val endTimes: List<Double> = emptyList(),
)
