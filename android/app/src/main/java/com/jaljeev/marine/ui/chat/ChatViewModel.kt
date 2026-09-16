package com.jaljeev.marine.ui.chat

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.jaljeev.marine.AppContainer
import com.jaljeev.marine.data.remote.EvidenceReceipt
import com.jaljeev.marine.domain.ApiOutcome
import com.jaljeev.marine.domain.GeoPoint
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

data class ChatMessage(
    val id: Long,
    val fromUser: Boolean,
    val text: String,
    val evidence: EvidenceReceipt? = null,
    val trace: List<String> = emptyList(),
    val isError: Boolean = false,
    val errorDetail: String? = null,
)

data class ChatUiState(
    val messages: List<ChatMessage> = emptyList(),
    val sending: Boolean = false,
    val sessionId: String? = null,
    val attachLocation: Boolean = true,
    val locationUnavailable: Boolean = false,
)

class ChatViewModel(private val container: AppContainer) : ViewModel() {

    private val _state = MutableStateFlow(ChatUiState())
    val state: StateFlow<ChatUiState> = _state.asStateFlow()

    private var nextId = 0L

    init {
        viewModelScope.launch {
            _state.value = _state.value.copy(
                attachLocation = container.settings.settings.value.attachLocationToChat
            )
        }
    }

    fun setAttachLocation(enabled: Boolean) {
        _state.value = _state.value.copy(attachLocation = enabled)
        viewModelScope.launch { container.settings.setAttachLocationToChat(enabled) }
    }

    /**
     * Starts a fresh backend session. Session id is what lets "and what about
     * tomorrow?" resolve a location the user named three messages ago
     * (memory_agent.py, 1 hour TTL server-side), so clearing it is an explicit
     * user action rather than something that happens on rotation.
     */
    fun newConversation() {
        _state.value = ChatUiState(attachLocation = _state.value.attachLocation)
    }

    fun send(message: String) {
        val text = message.trim()
        if (text.isEmpty() || _state.value.sending) return

        appendMessage(ChatMessage(id = nextId++, fromUser = true, text = text))
        _state.value = _state.value.copy(sending = true, locationUnavailable = false)

        viewModelScope.launch {
            var point: GeoPoint? = null
            if (_state.value.attachLocation) {
                point = container.locationProvider.current()
                if (point == null) {
                    // Say so rather than silently sending a location-less
                    // query the user believed carried their position.
                    _state.value = _state.value.copy(locationUnavailable = true)
                }
            }

            when (
                val outcome = container.repository.chat(
                    message = text,
                    sessionId = _state.value.sessionId,
                    clientLat = point?.lat,
                    clientLon = point?.lon,
                )
            ) {
                is ApiOutcome.Ok -> {
                    val response = outcome.value
                    appendMessage(
                        ChatMessage(
                            id = nextId++,
                            fromUser = false,
                            text = response.answer,
                            evidence = response.evidence.takeUnless { it.isEmpty },
                            trace = response.trace,
                        )
                    )
                    _state.value = _state.value.copy(sending = false, sessionId = response.sessionId)

                    // Keep the rest of the app pointed at whatever this answer
                    // is actually about, so Map and Route open on it.
                    val lat = response.evidence.locationLat
                    val lon = response.evidence.locationLon
                    if (lat != null && lon != null) {
                        container.session.selectPoint(GeoPoint(lat, lon))
                    }
                }

                is ApiOutcome.Err -> {
                    appendMessage(
                        ChatMessage(
                            id = nextId++,
                            fromUser = false,
                            text = outcome.message,
                            isError = true,
                            errorDetail = outcome.detail,
                        )
                    )
                    _state.value = _state.value.copy(sending = false)
                }
            }
        }
    }

    fun showOnMap(point: GeoPoint) = container.session.focusOnMap(point)

    private fun appendMessage(message: ChatMessage) {
        _state.value = _state.value.copy(messages = _state.value.messages + message)
    }

    companion object {
        fun factory(container: AppContainer): ViewModelProvider.Factory = viewModelFactory {
            initializer { ChatViewModel(container) }
        }
    }
}
