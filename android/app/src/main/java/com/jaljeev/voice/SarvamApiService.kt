package com.jaljeev.voice

import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.RequestBody
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Header
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import java.util.concurrent.TimeUnit

interface SarvamApiService {
    @Multipart
    @POST("speech-to-text")
    suspend fun transcribe(
        @Header("api-subscription-key") apiKey: String,
        @Part file: MultipartBody.Part,
        @Part("model") model: RequestBody,
        @Part("language_code") languageCode: RequestBody,
        @Part("mode") mode: RequestBody,
        @Part("with_timestamps") withTimestamps: RequestBody,
        @Part("keyterms") keyterms: RequestBody,
        @Part("input_audio_codec") inputAudioCodec: RequestBody,
    ): Response<SarvamResponse>
}

object SarvamApiClient {
    private const val BASE_URL = "https://api.sarvam.ai/"

    fun create(baseUrl: String = BASE_URL): SarvamApiService {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BODY
        }

        val okHttpClient = OkHttpClient.Builder()
            .addInterceptor(logging)
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(35, TimeUnit.SECONDS)
            .writeTimeout(35, TimeUnit.SECONDS)
            .build()

        return Retrofit.Builder()
            .baseUrl(baseUrl)
            .client(okHttpClient)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(SarvamApiService::class.java)
    }
}
