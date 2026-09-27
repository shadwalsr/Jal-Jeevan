package com.jaljeev.voice

import com.google.gson.Gson
import com.jaljeev.marine.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.Response
import java.io.File

class SarvamRepository(
    private val apiService: SarvamApiService,
    private val apiKey: String = BuildConfig.SARVAM_API_KEY,
) {
    private val gson = Gson()

    /**
     * Sends recorded audio to Sarvam API (saaras:v4).
     * Retry logic: on 429 → wait 2s → retry once.
     * On failure or 5xx → falls back to backend /api/speech/transcribe proxy.
     */
    suspend fun transcribeVoice(
        audioFile: File,
        language: IndianLanguage,
    ): Result<String> = withContext(Dispatchers.IO) {

        val filePart = MultipartBody.Part.createFormData(
            name     = "file",
            filename = audioFile.name,
            body     = audioFile.asRequestBody("audio/wav".toMediaType())
        )

        val keytermsList = MaritimeVocabulary.getKeyterms()
        val keytermsJson = gson.toJson(keytermsList)

        suspend fun attemptTranscribe(): Response<SarvamResponse> =
            apiService.transcribe(
                apiKey          = apiKey,
                file            = filePart,
                model           = "saaras:v4".toRequestBody(),
                languageCode    = language.bcp47Code.toRequestBody(),
                mode            = "transcribe".toRequestBody(),
                withTimestamps  = "false".toRequestBody(),
                keyterms        = keytermsJson.toRequestBody(),
                inputAudioCodec = "wav".toRequestBody(),
            )

        try {
            var response = attemptTranscribe()

            // Retry once on 429
            if (response.code() == 429) {
                delay(2000)
                response = attemptTranscribe()
            }

            if (response.isSuccessful) {
                val body = response.body()
                if (body?.transcript.isNullOrBlank()) {
                    return@withContext Result.failure(Exception("Empty transcript returned"))
                }
                val corrected = MaritimeVocabulary.applyCorrections(body!!.transcript)
                return@withContext Result.success(corrected)
            }

            // If direct call returned an error, try backend proxy fallback before giving up
            val fallbackResult = attemptBackendProxyTranscribe(audioFile, language)
            if (fallbackResult.isSuccess) {
                return@withContext fallbackResult
            }

            val err = SarvamError.fromHttpCode(
                response.code(),
                response.errorBody()?.string() ?: ""
            )
            Result.failure(Exception(err.message))
        } catch (e: Exception) {
            // Direct call exception (network error, timeout, etc.) -> try backend proxy
            val fallbackResult = attemptBackendProxyTranscribe(audioFile, language)
            if (fallbackResult.isSuccess) {
                return@withContext fallbackResult
            }
            Result.failure(Exception(SarvamError.NetworkError(e.message ?: "Network error").message))
        }
    }

    private suspend fun attemptBackendProxyTranscribe(
        audioFile: File,
        language: IndianLanguage,
    ): Result<String> = withContext(Dispatchers.IO) {
        try {
            val baseUrl = com.jaljeev.marine.data.remote.ApiClient.currentBaseUrl().trimEnd('/')
            val url = "$baseUrl/api/speech/transcribe"
            val requestBody = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("model", "saaras:v4")
                .addFormDataPart("language_code", language.bcp47Code)
                .addFormDataPart("mode", "transcribe")
                .addFormDataPart(
                    "file",
                    audioFile.name,
                    audioFile.asRequestBody("audio/wav".toMediaType())
                )
                .build()

            val request = okhttp3.Request.Builder()
                .url(url)
                .post(requestBody)
                .build()

            val client = okhttp3.OkHttpClient.Builder()
                .connectTimeout(15, java.util.concurrent.TimeUnit.SECONDS)
                .readTimeout(35, java.util.concurrent.TimeUnit.SECONDS)
                .build()

            client.newCall(request).execute().use { response ->
                if (response.isSuccessful) {
                    val bodyString = response.body?.string() ?: ""
                    val json = gson.fromJson(bodyString, SarvamResponse::class.java)
                    if (!json?.transcript.isNullOrBlank()) {
                        val corrected = MaritimeVocabulary.applyCorrections(json.transcript)
                        return@withContext Result.success(corrected)
                    }
                }
            }
        } catch (_: Exception) {}
        return@withContext Result.failure(Exception("Transcription failed via backend proxy"))
    }
}
