package com.jaljeev.voice

import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.File

class SarvamRepositoryTest {

    private lateinit var mockWebServer: MockWebServer
    private lateinit var apiService: SarvamApiService
    private lateinit var repository: SarvamRepository
    private lateinit var dummyAudioFile: File
    private val testApiKey = "test_api_key_12345"

    @Before
    fun setup() {
        mockWebServer = MockWebServer()
        mockWebServer.start()

        val baseUrl = mockWebServer.url("/").toString()
        apiService = SarvamApiClient.create(baseUrl)
        repository = SarvamRepository(apiService, apiKey = testApiKey)

        dummyAudioFile = File.createTempFile("test_audio_", ".wav")
        dummyAudioFile.writeBytes(ByteArray(100))
    }

    @After
    fun teardown() {
        dummyAudioFile.delete()
        mockWebServer.shutdown()
    }

    @Test
    fun test_success_response_returns_transcript() = runBlocking {
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"transcript": "नमस्ते, समुद्र कैसा है?"}""")
        )

        val result = repository.transcribeVoice(dummyAudioFile, IndianLanguage.HINDI)
        assertTrue(result.isSuccess)
        assertEquals("नमस्ते, समुद्र कैसा है?", result.getOrNull())
    }

    @Test
    fun test_429_retries_once_then_fails() = runBlocking {
        // Enqueue two 429 responses
        mockWebServer.enqueue(MockResponse().setResponseCode(429).setBody("Rate limit exceeded"))
        mockWebServer.enqueue(MockResponse().setResponseCode(429).setBody("Rate limit exceeded"))

        val result = repository.transcribeVoice(dummyAudioFile, IndianLanguage.ODIA)
        assertTrue(result.isFailure)
        assertEquals(2, mockWebServer.requestCount)
        assertTrue(result.exceptionOrNull()?.message?.contains("Service busy") == true)
    }

    @Test
    fun test_500_returns_server_error() = runBlocking {
        mockWebServer.enqueue(
            MockResponse().setResponseCode(500).setBody("Internal Server Error")
        )

        val result = repository.transcribeVoice(dummyAudioFile, IndianLanguage.TAMIL)
        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull()?.message?.contains("Sarvam server error") == true)
    }

    @Test
    fun test_empty_transcript_returns_failure() = runBlocking {
        mockWebServer.enqueue(
            MockResponse().setResponseCode(200).setBody("""{"transcript": "   "}""")
        )

        val result = repository.transcribeVoice(dummyAudioFile, IndianLanguage.BENGALI)
        assertTrue(result.isFailure)
        assertTrue(result.exceptionOrNull()?.message?.contains("Empty transcript") == true)
    }

    @Test
    fun test_maritime_corrections_applied_to_transcript() = runBlocking {
        mockWebServer.enqueue(
            MockResponse()
                .setResponseCode(200)
                .setBody("""{"transcript": "going to vizag port near para deep"}""")
        )

        val result = repository.transcribeVoice(dummyAudioFile, IndianLanguage.TELUGU)
        assertTrue(result.isSuccess)
        assertEquals("going to Visakhapatnam port near Paradip", result.getOrNull())
    }

    @Test
    fun test_api_key_sent_in_correct_header() = runBlocking {
        mockWebServer.enqueue(
            MockResponse().setResponseCode(200).setBody("""{"transcript": "hello"}""")
        )

        repository.transcribeVoice(dummyAudioFile, IndianLanguage.ENGLISH)
        val recordedRequest = mockWebServer.takeRequest()

        val headerValue = recordedRequest.getHeader("api-subscription-key")
        assertEquals(testApiKey, headerValue)
    }
}
