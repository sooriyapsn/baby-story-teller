package com.storyteller.app.voice

import android.content.Context
import io.livekit.android.LiveKit
import io.livekit.android.events.RoomEvent
import io.livekit.android.events.collect
import io.livekit.android.room.Room
import io.livekit.android.room.participant.LocalParticipant
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

enum class AgentState { CONNECTING, LISTENING, AGENT_SPEAKING, DISCONNECTED }

/**
 * Wraps a LiveKit Room connection for one voice call. This is the whole
 * reason for going native: LiveKit's Android SDK drives WebRTC's native
 * Android audio module directly (hardware AEC/NS/AGC when the device
 * supports it, proper audio-focus/Bluetooth-routing integration), instead
 * of whatever a mobile browser's WebView happens to negotiate.
 *
 * Agent state here is a simplified proxy: "is the agent's audio track
 * currently speaking" vs "not" — not the richer listening/thinking/speaking
 * split the web UI gets via LiveKit's voice-assistant attribute protocol.
 * Good enough for a first native pass; a true 1:1 port would need to read
 * the same participant attributes the web SDK's useVoiceAssistant hook does.
 */
class LiveKitManager(context: Context) {
    private val room: Room = LiveKit.create(context.applicationContext)
    private val scope = CoroutineScope(Dispatchers.Main)

    private val _state = MutableStateFlow(AgentState.DISCONNECTED)
    val state: StateFlow<AgentState> = _state.asStateFlow()

    private val _micEnabled = MutableStateFlow(true)
    val micEnabled: StateFlow<Boolean> = _micEnabled.asStateFlow()

    suspend fun connect(url: String, token: String) {
        _state.value = AgentState.CONNECTING
        room.connect(url, token)
        room.localParticipant.setMicrophoneEnabled(true)
        _micEnabled.value = true
        _state.value = AgentState.LISTENING

        scope.launch {
            room.events.collect { event ->
                when (event) {
                    is RoomEvent.ActiveSpeakersChanged -> {
                        val agentSpeaking = event.speakers.any { it !is LocalParticipant }
                        _state.value = if (agentSpeaking) AgentState.AGENT_SPEAKING else AgentState.LISTENING
                    }
                    is RoomEvent.Disconnected -> {
                        _state.value = AgentState.DISCONNECTED
                    }
                    else -> Unit
                }
            }
        }
    }

    fun toggleMicrophone() {
        val next = !_micEnabled.value
        scope.launch {
            room.localParticipant.setMicrophoneEnabled(next)
            _micEnabled.value = next
        }
    }

    fun disconnect() {
        room.disconnect()
        _state.value = AgentState.DISCONNECTED
    }

    fun release() {
        room.release()
    }
}
