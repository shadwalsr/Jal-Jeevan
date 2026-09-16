package com.jaljeev.marine.data.remote

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import com.jaljeev.marine.BuildConfig
import kotlinx.serialization.json.Json
import okhttp3.Interceptor
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Response
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import java.util.concurrent.TimeUnit

/**
 * One Retrofit instance for the whole app, with a base URL that can change at
 * runtime.
 *
 * Retrofit fixes its base URL at build time, but this app deliberately lets
 * the user retarget the backend from the Settings screen (emulator alias,
 * laptop LAN IP, tunnel) without a rebuild. [BaseUrlInterceptor] therefore
 * rewrites scheme/host/port on every outgoing request from a volatile field,
 * and Retrofit's own base URL is only a placeholder that must parse.
 */
object ApiClient {

    /**
     * Long by design. The backend's own ceilings are 115 s for /chat (two LLM
     * calls plus the slowest marine agent) and 90 s for /optimize-route's A*
     * search - see backend/app/api/chat.py and marine.py. A shorter client
     * timeout here would kill requests the server was going to answer
     * correctly, and would look exactly like a hang. Individual fast calls
     * (quick-check) impose their own tighter deadline with coroutine
     * withTimeout in MarineRepository instead.
     */
    private const val READ_TIMEOUT_SECONDS = 130L
    private const val CONNECT_TIMEOUT_SECONDS = 15L

    val json: Json = Json {
        ignoreUnknownKeys = true // backend may add fields; an unknown key must never crash the app
        explicitNulls = false
        coerceInputValues = false
    }

    private val baseUrlInterceptor = BaseUrlInterceptor(BuildConfig.DEFAULT_API_BASE)

    /** Called by SettingsRepository whenever the stored base URL changes. */
    fun setBaseUrl(url: String) = baseUrlInterceptor.set(url)

    fun currentBaseUrl(): String = baseUrlInterceptor.current()

    private val okHttp: OkHttpClient = OkHttpClient.Builder()
        .addInterceptor(baseUrlInterceptor)
        .addInterceptor(
            HttpLoggingInterceptor().apply {
                level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BASIC
                else HttpLoggingInterceptor.Level.NONE
            }
        )
        .connectTimeout(CONNECT_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .readTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .writeTimeout(READ_TIMEOUT_SECONDS, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    val api: JalJeevApi = Retrofit.Builder()
        .baseUrl("http://localhost/") // placeholder, always overwritten by the interceptor
        .client(okHttp)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()
        .create(JalJeevApi::class.java)
}

private class BaseUrlInterceptor(initial: String) : Interceptor {

    @Volatile
    private var base: String = initial

    fun set(url: String) {
        base = url.trim().removeSuffix("/")
    }

    fun current(): String = base

    override fun intercept(chain: Interceptor.Chain): Response {
        val target = base.toHttpUrlOrNull()
            ?: throw java.io.IOException(
                "Backend URL \"$base\" is not a valid URL. Fix it in Settings " +
                    "(for example http://192.168.1.5:8000)."
            )
        val request = chain.request()
        val rewritten = request.url.newBuilder()
            .scheme(target.scheme)
            .host(target.host)
            .port(target.port)
            .build()
        return chain.proceed(request.newBuilder().url(rewritten).build())
    }
}
