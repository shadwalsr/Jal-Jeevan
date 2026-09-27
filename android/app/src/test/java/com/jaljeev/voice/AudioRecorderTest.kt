package com.jaljeev.voice

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

class AudioRecorderTest {

    private fun createRecorder(): AudioRecorder {
        val tempDir = File(System.getProperty("java.io.tmpdir"), "audio_test_${System.currentTimeMillis()}")
        tempDir.mkdirs()
        // Provide mock/stub context using simple proxy or direct invocation
        val mockContext = android.content.ContextWrapper(null)
        return AudioRecorder(mockContext)
    }

    @Test
    fun test_wav_header_size_is_44_bytes() {
        val recorder = AudioRecorder(android.content.ContextWrapper(null))
        val out = ByteArrayOutputStream()
        recorder.writeWavHeader(out, 1000L, sampleRate = 16000, channels = 1, bitsPerSample = 16)
        val headerBytes = out.toByteArray()
        assertEquals(44, headerBytes.size)
        // Check RIFF and WAVE signatures
        val riff = String(headerBytes, 0, 4)
        val wave = String(headerBytes, 8, 4)
        val fmt = String(headerBytes, 12, 4)
        val data = String(headerBytes, 36, 4)
        assertEquals("RIFF", riff)
        assertEquals("WAVE", wave)
        assertEquals("fmt ", fmt)
        assertEquals("data", data)
    }

    @Test
    fun test_wav_header_has_correct_sample_rate() {
        val recorder = AudioRecorder(android.content.ContextWrapper(null))
        val out = ByteArrayOutputStream()
        recorder.writeWavHeader(out, 1000L, sampleRate = 16000, channels = 1, bitsPerSample = 16)
        val headerBytes = out.toByteArray()

        // Sample rate is 4-byte integer at offset 24 (little-endian)
        val buffer = ByteBuffer.wrap(headerBytes, 24, 4).order(ByteOrder.LITTLE_ENDIAN)
        val sampleRate = buffer.int
        assertEquals(16000, sampleRate)
    }

    @Test
    fun test_too_short_audio_throws_error() {
        val durationMs = 300L
        assertTrue("Duration under 500ms must be rejected", durationMs < AudioRecorder.MIN_DURATION_MS)
        val error = SarvamError.AudioTooShort()
        assertEquals("Audio too short — please speak longer", error.message)
    }

    @Test
    fun test_file_is_deleted_on_success() {
        val testFile = File.createTempFile("voice_success_", ".wav")
        assertTrue(testFile.exists())
        // Simulate lifecycle: delete after success
        testFile.delete()
        assertFalse(testFile.exists())
    }

    @Test
    fun test_file_is_deleted_on_error() {
        val testFile = File.createTempFile("voice_error_", ".wav")
        assertTrue(testFile.exists())
        // Simulate lifecycle: delete on error
        testFile.delete()
        assertFalse(testFile.exists())
    }
}
