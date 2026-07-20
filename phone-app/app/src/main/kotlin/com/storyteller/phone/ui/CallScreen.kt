package com.storyteller.phone.ui

import android.app.Activity
import android.view.WindowManager
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material3.Icon
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.storyteller.phone.data.ApiClient
import com.storyteller.phone.data.CHARACTERS
import com.storyteller.phone.voice.AgentState
import com.storyteller.phone.voice.LiveKitManager
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

    val characterDef = CHARACTERS.find { it.id == character }
    val color = characterDef?.color ?: Color.Gray
    val backgroundTop = lerp(color, Color.Black, 0.55f)
    val backgroundBottom = lerp(color, Color.Black, 0.9f)

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

    // Keep the screen from auto-locking for the duration of the call — same
    // reason a real video-call app does this: a locked/dimmed screen pauses
    // the activity, which drops the mic and the LiveKit connection.
    DisposableEffect(Unit) {
        val activity = context as? Activity
        activity?.window?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        onDispose {
            activity?.window?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            manager.disconnect()
            manager.release()
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Brush.verticalGradient(listOf(backgroundTop, backgroundBottom))),
    ) {
        // TEMPORARY debug label — remove once the state-detection bug is
        // found. Not the final design (see comment history: no status text
        // by default, matching the web app's textless session view).
        Text(
            "DEBUG: ${agentState.name}",
            color = Color.Yellow,
            style = MaterialTheme.typography.titleLarge,
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(top = 40.dp, start = 16.dp)
                .background(Color.Black.copy(alpha = 0.6f))
                .padding(8.dp),
        )

        characterDef?.let {
            MascotCharacter(
                characterDef = it,
                agentState = agentState,
                modifier = Modifier
                    .align(Alignment.Center)
                    .size(280.dp),
            )
        }

        errorText?.let {
            Text(
                it,
                color = Color.White,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 40.dp, start = 32.dp, end = 32.dp)
                    .background(MaterialTheme.colorScheme.error, MaterialTheme.shapes.medium)
                    .padding(horizontal = 16.dp, vertical = 8.dp),
            )
        }

        Box(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .padding(bottom = 48.dp)
                .fillMaxWidth(),
        ) {
            androidx.compose.foundation.layout.Row(
                modifier = Modifier.align(Alignment.Center),
                horizontalArrangement = Arrangement.spacedBy(32.dp),
            ) {
                CallButton(
                    onClick = { manager.toggleMicrophone() },
                    background = Color.White.copy(alpha = 0.15f),
                    iconTint = Color.White,
                ) {
                    Icon(
                        if (micEnabled) Icons.Filled.Mic else Icons.Filled.MicOff,
                        contentDescription = "Toggle microphone",
                    )
                }
                CallButton(
                    onClick = {
                        manager.disconnect()
                        onEndCall()
                    },
                    background = Color(0xFFE8483C),
                    iconTint = Color.White,
                ) {
                    Icon(Icons.Filled.Close, contentDescription = "End call")
                }
            }
        }
    }
}

@Composable
private fun CallButton(
    onClick: () -> Unit,
    background: Color,
    iconTint: Color,
    content: @Composable () -> Unit,
) {
    Box(
        modifier = Modifier
            .size(64.dp)
            .clip(CircleShape)
            .background(background)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        CompositionLocalProvider(LocalContentColor provides iconTint) {
            content()
        }
    }
}
