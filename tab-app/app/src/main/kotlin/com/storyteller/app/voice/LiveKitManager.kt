package com.storyteller.app.voice

import android.content.Context
import io.livekit.android.LiveKit
import io.livekit.android.events.RoomEvent
import io.livekit.android.events.collect
import io.livekit.android.room.Room
import io.livekit.android.room.participant.LocalParticipant
import io.livekit.android.room.participant.Participant
import io.livekit.android.room.types.AgentSdkState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

enum class AgentState { CONNECTING, LISTENING, THINKING, AGENT_SPEAKING, DISCONNECTED }

/**
 * Wraps a LiveKit Room connection for one voice call. This is the whole
 * reason for going native: LiveKit's Android SDK drives WebRTC's native
 * Android audio module directly (hardware AEC/NS/AGC when the device
 * supports it, proper audio-focus/Bluetooth-routing integration), instead
 * of whatever a mobile browser's WebView happens to negotiate.
 *
 * Agent state is read straight from the agent participant's `lk.agent.state`
 * attribute (exposed here as `Participant.agentAttributes.lkAgentState`) —
 * the same protocol the web app's `useVoiceAssistant()` hook reads. This
 * used to be inferred from `RoomEvent.ActiveSpeakersChanged` instead, which
 * only reflects whether audio is currently above a level threshold: it
 * can't distinguish "thinking" from "listening" at all, and it's flaky
 * about "speaking" too (state can lag or stick if a sentence has a quiet
 * beat), which is why the mascot's mouth used to look stuck mid-call.
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

        // Pick up the agent's state as soon as it's already present (it may
        // have joined and published attributes before our listener below
        // was wired up).
        room.remoteParticipants.values.forEach(::applyAgentAttributes)

        scope.launch {
            room.events.collect { event ->
                when (event) {
                    is RoomEvent.ParticipantConnected -> applyAgentAttributes(event.participant)
                    is RoomEvent.ParticipantAttributesChanged -> applyAgentAttributes(event.participant)
                    is RoomEvent.Disconnected -> {
                        _state.value = AgentState.DISCONNECTED
                    }
                    else -> Unit
                }
            }
        }
    }

    private fun applyAgentAttributes(participant: Participant) {
        if (participant is LocalParticipant) return
        _state.value = when (participant.agentAttributes.lkAgentState) {
            AgentSdkState.Thinking -> AgentState.THINKING
            AgentSdkState.Speaking -> AgentState.AGENT_SPEAKING
            AgentSdkState.Listening, AgentSdkState.Idle, AgentSdkState.Initializing -> AgentState.LISTENING
            AgentSdkState.Unknown, null -> _state.value
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
