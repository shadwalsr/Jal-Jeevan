package com.jaljeev.voice

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStream

class AudioRecorder(private val context: Context) {

    companion object {
        const val SAMPLE_RATE = 16000
        const val MAX_DURATION_MS = 29_000L
        const val MIN_DURATION_MS = 500L
        const val WAV_HEADER_SIZE = 44
    }

    private var audioRecord: AudioRecord? = null
    private var outputFile: File? = null
    private var startTimeMs = 0L

    // Returns the recorded WAV file path, or throws SarvamError
    @SuppressLint("MissingPermission")
    suspend fun recordUntilStopped(
        onAmplitude: (Int) -> Unit,   // for waveform visualizer (0–32767)
        stopSignal: Flow<Unit>,       // emits when PTT button released
    ): File = withContext(Dispatchers.IO) {

        val bufferSize = AudioRecord.getMinBufferSize(
            SAMPLE_RATE,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        ).coerceAtLeast(1024)

        try {
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                SAMPLE_RATE,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize * 4
            )
        } catch (e: Exception) {
            throw SarvamError.RecordingFailed("Microphone initialization error: ${e.message}")
        }

        if (audioRecord?.state != AudioRecord.STATE_INITIALIZED) {
            throw SarvamError.RecordingFailed("Microphone unavailable")
        }

        val cacheFile = File(
            context.cacheDir,
            "jaljeev_voice_${System.currentTimeMillis()}.wav"
        )
        outputFile = cacheFile

        val allPcmData = ByteArrayOutputStream()
        startTimeMs = System.currentTimeMillis()
        try {
            audioRecord?.startRecording()
        } catch (e: Exception) {
            throw SarvamError.RecordingFailed("Microphone recording could not start: ${e.message}")
        }

        val buffer = ShortArray(bufferSize)
        var stopped = false

        // Launch stop-signal listener
        val stopJob = launch {
            stopSignal.first()
            stopped = true
        }

        // Auto-stop after MAX_DURATION_MS
        val autoStopJob = launch {
            delay(MAX_DURATION_MS)
            stopped = true
        }

        while (!stopped) {
            val read = audioRecord?.read(buffer, 0, buffer.size) ?: 0
            if (read > 0) {
                // Amplitude for visualizer
                var maxVal = 0
                for (i in 0 until read) {
                    val abs = Math.abs(buffer[i].toInt())
                    if (abs > maxVal) maxVal = abs
                }
                onAmplitude(maxVal)

                // Convert shorts to bytes (little-endian PCM)
                val bytes = ByteArray(read * 2)
                for (i in 0 until read) {
                    bytes[i * 2]     = (buffer[i].toInt() and 0xFF).toByte()
                    bytes[i * 2 + 1] = (buffer[i].toInt() shr 8 and 0xFF).toByte()
                }
                allPcmData.write(bytes)
            }
        }

        stopJob.cancel()
        autoStopJob.cancel()
        try {
            audioRecord?.stop()
        } catch (_: Exception) {}
        audioRecord?.release()
        audioRecord = null

        val durationMs = System.currentTimeMillis() - startTimeMs
        if (durationMs < MIN_DURATION_MS) {
            cacheFile.delete()
            throw SarvamError.AudioTooShort()
        }

        // Write WAV file with proper header
        FileOutputStream(cacheFile).use { fos ->
            val pcmBytes = allPcmData.toByteArray()
            writeWavHeader(fos, pcmBytes.size.toLong())
            fos.write(pcmBytes)
        }

        return@withContext cacheFile
    }

    fun cleanup() {
        outputFile?.delete()
        outputFile = null
        try {
            audioRecord?.release()
        } catch (_: Exception) {}
        audioRecord = null
    }

    fun writeWavHeader(
        out: OutputStream,
        pcmDataLen: Long,
        sampleRate: Int = SAMPLE_RATE,
        channels: Int = 1,
        bitsPerSample: Int = 16
    ) {
        val totalDataLen  = pcmDataLen + 36
        val byteRate      = (sampleRate * channels * bitsPerSample / 8).toLong()
        val blockAlign    = (channels * bitsPerSample / 8)

        out.write("RIFF".toByteArray())
        out.write(intToByteArray(totalDataLen.toInt()))
        out.write("WAVE".toByteArray())
        out.write("fmt ".toByteArray())
        out.write(intToByteArray(16))
        out.write(shortToByteArray(1))                 // PCM format
        out.write(shortToByteArray(channels.toShort())) // channels
        out.write(intToByteArray(sampleRate))
        out.write(intToByteArray(byteRate.toInt()))
        out.write(shortToByteArray(blockAlign.toShort()))
        out.write(shortToByteArray(bitsPerSample.toShort())) // bits per sample
        out.write("data".toByteArray())
        out.write(intToByteArray(pcmDataLen.toInt()))
    }

    private fun intToByteArray(value: Int) = ByteArray(4).also {
        it[0] = (value        and 0xFF).toByte()
        it[1] = (value shr 8  and 0xFF).toByte()
        it[2] = (value shr 16 and 0xFF).toByte()
        it[3] = (value shr 24 and 0xFF).toByte()
    }

    private fun shortToByteArray(value: Short) = ByteArray(2).also {
        it[0] = (value.toInt()        and 0xFF).toByte()
        it[1] = (value.toInt() shr 8  and 0xFF).toByte()
    }
}
