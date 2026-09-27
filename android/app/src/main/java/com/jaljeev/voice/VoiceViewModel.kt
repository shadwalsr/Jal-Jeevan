package com.jaljeev.voice

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.io.File

sealed class VoiceUiState {
    object Idle          : VoiceUiState()
    object Listening     : VoiceUiState()   // recording in progress
    object Processing    : VoiceUiState()   // API call in flight
    data class PartialResult(val text: String) : VoiceUiState()  // reserved for future streaming
    data class Success(
        val transcript: String,
        val detectedLanguage: String?,
    ) : VoiceUiState()
    data class Error(
        val error: SarvamError,
        val canRetry: Boolean = true,
    ) : VoiceUiState()
}

class VoiceViewModel(
    private val repository: SarvamRepository,
    private val audioRecorder: AudioRecorder,
) : ViewModel() {

    private val _uiState = MutableStateFlow<VoiceUiState>(VoiceUiState.Idle)
    val uiState: StateFlow<VoiceUiState> = _uiState.asStateFlow()

    private val _amplitude = MutableStateFlow(0)
    val amplitude: StateFlow<Int> = _amplitude.asStateFlow()

    private val _selectedLanguage = MutableStateFlow(IndianLanguage.AUTO_DETECT)
    val selectedLanguage: StateFlow<IndianLanguage> = _selectedLanguage.asStateFlow()

    private val _elapsedMs = MutableStateFlow(0L)
    val elapsedMs: StateFlow<Long> = _elapsedMs.asStateFlow()

    private val stopRecordingChannel = MutableSharedFlow<Unit>(extraBufferCapacity = 1)
    private var recordingJob: Job? = null
    private var timerJob: Job? = null
    private var lastAudioFile: File? = null

    fun setLanguage(language: IndianLanguage) {
        _selectedLanguage.value = language
    }

    fun startRecording() {
        if (_uiState.value != VoiceUiState.Idle) return
        _uiState.value = VoiceUiState.Listening
        _elapsedMs.value = 0L

        // Timer for elapsed display
        timerJob = viewModelScope.launch {
            val startMs = System.currentTimeMillis()
            while (true) {
                _elapsedMs.value = System.currentTimeMillis() - startMs
                delay(100)
            }
        }

        recordingJob = viewModelScope.launch {
            try {
                val file = audioRecorder.recordUntilStopped(
                    onAmplitude = { _amplitude.value = it },
                    stopSignal  = stopRecordingChannel,
                )
                lastAudioFile = file
                timerJob?.cancel()
                _uiState.value = VoiceUiState.Processing
                sendToApi(file)
            } catch (e: SarvamError.AudioTooShort) {
                timerJob?.cancel()
                _uiState.value = VoiceUiState.Error(SarvamError.AudioTooShort(), canRetry = true)
            } catch (e: Exception) {
                timerJob?.cancel()
                _uiState.value = VoiceUiState.Error(
                    SarvamError.RecordingFailed(e.message ?: ""), canRetry = true
                )
            }
        }
    }

    fun stopRecording() {
        stopRecordingChannel.tryEmit(Unit)
        timerJob?.cancel()
    }

    private suspend fun sendToApi(file: File) {
        val result = repository.transcribeVoice(
            audioFile = file,
            language  = _selectedLanguage.value,
        )
        file.delete()  // always delete audio file after use
        lastAudioFile = null

        result.fold(
            onSuccess = { transcript ->
                _uiState.value = VoiceUiState.Success(
                    transcript       = transcript,
                    detectedLanguage = _selectedLanguage.value.displayName,
                )
            },
            onFailure = { e ->
                val error = if (e is SarvamError) e else SarvamError.ServerError(e.message ?: "Unknown error")
                _uiState.value = VoiceUiState.Error(
                    error,
                    canRetry = true
                )
            }
        )
    }

    fun resetToIdle() {
        _uiState.value = VoiceUiState.Idle
        _amplitude.value = 0
        _elapsedMs.value = 0L
    }

    override fun onCleared() {
        super.onCleared()
        audioRecorder.cleanup()
        timerJob?.cancel()
        recordingJob?.cancel()
    }

    companion object {
        fun factory(
            repository: SarvamRepository,
            audioRecorder: AudioRecorder,
        ): ViewModelProvider.Factory = object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                return VoiceViewModel(repository, audioRecorder) as T
            }
        }
    }
}
