package com.jaljeev.voice

sealed class SarvamError(override val message: String) : Exception(message) {
    class InvalidRequest(msg: String)     : SarvamError(msg)
    class AuthenticationError(msg: String): SarvamError(msg)
    class UnprocessableAudio(msg: String) : SarvamError(msg)
    class RateLimitExceeded(msg: String)  : SarvamError(msg)
    class ServerError(msg: String)        : SarvamError(msg)
    class ServiceOverloaded(msg: String)  : SarvamError(msg)
    class NetworkError(msg: String)       : SarvamError(msg)
    class AudioTooShort                   : SarvamError("Audio too short — please speak longer")
    class RecordingFailed(msg: String)    : SarvamError(msg)

    companion object {
        fun fromHttpCode(code: Int, body: String): SarvamError = when (code) {
            400  -> InvalidRequest(body)
            403  -> AuthenticationError("API key issue — contact support")
            422  -> UnprocessableAudio("Could not process audio")
            429  -> RateLimitExceeded("Service busy — retrying...")
            500  -> ServerError("Sarvam server error — using offline mode")
            503  -> ServiceOverloaded("Service overloaded — using offline mode")
            else -> ServerError("Unexpected error $code")
        }
    }
}
