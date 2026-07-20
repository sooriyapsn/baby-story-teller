package com.storyteller.app.ui

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.storyteller.app.data.ApiClient
import com.storyteller.app.data.CHARACTERS
import com.storyteller.app.voice.AgentState
import com.storyteller.app.voice.LiveKitManager
import kotlinx.coroutines.delay

@Composable
fun CallScreen(
    baseUrl: String,
    character: String,
    language: String,
    onEndCall: () -> Unit,
) {
    val context = LocalContext.current
    val manager = remember { LiveKitManager(context) }
    val agentState by manager.state.collectAsState()
    val micEnabled by manager.micEnabled.collectAsState()
    var errorText by remember { mutableStateOf<String?>(null) }

    val color = CHARACTERS.find { it.id == character }?.color ?: Color.Gray

    LaunchedEffect(character, language) {
        try {
            val details = ApiClient(baseUrl).connectionDetails(character, language)
            manager.connect(details.serverUrl, details.participantToken)
        } catch (e: Exception) {
            errorText = "Couldn't start the call: ${e.message}"
        }
    }

    // Parent-set play time limit: end the call gently instead of leaving it
    // open indefinitely, mirroring the web app's behavior (session-view.tsx).
    LaunchedEffect(Unit) {
        val minutes = try {
            ApiClient(baseUrl).status().timeLimitMinutes
        } catch (_: Exception) {
            null
        }
        if (minutes != null && minutes > 0) {
            delay(minutes * 60_000L)
            manager.disconnect()
            onEndCall()
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            manager.disconnect()
            manager.release()
        }
    }

    val transition = rememberInfiniteTransition(label = "pulse")
    val pulse by transition.animateFloat(
        initialValue = 1f,
        targetValue = if (agentState == AgentState.AGENT_SPEAKING) 1.15f else 1f,
        animationSpec = infiniteRepeatable(tween(600), RepeatMode.Reverse),
        label = "pulse",
    )

    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Box(
            modifier = Modifier
                .size((200 * pulse).dp)
                .background(color, CircleShape)
        )
        Text(
            when (agentState) {
                AgentState.CONNECTING -> "Connecting…"
                AgentState.LISTENING -> "Listening — ask a question"
                AgentState.AGENT_SPEAKING -> "Speaking…"
                AgentState.DISCONNECTED -> "Disconnected"
            },
            style = MaterialTheme.typography.titleMedium,
            modifier = Modifier.padding(top = 24.dp),
        )
        errorText?.let {
            Text(it, color = MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 8.dp))
        }

        Row(
            modifier = Modifier.padding(top = 48.dp),
            horizontalArrangement = Arrangement.spacedBy(24.dp),
        ) {
            FloatingActionButton(onClick = { manager.toggleMicrophone() }) {
                Icon(
                    if (micEnabled) Icons.Filled.Mic else Icons.Filled.MicOff,
                    contentDescription = "Toggle microphone",
                )
            }
            FloatingActionButton(
                onClick = {
                    manager.disconnect()
                    onEndCall()
                },
                containerColor = MaterialTheme.colorScheme.errorContainer,
            ) {
                Icon(Icons.Filled.Call, contentDescription = "End call")
            }
        }
    }
}
