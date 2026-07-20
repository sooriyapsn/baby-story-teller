package com.storyteller.app

import android.Manifest
import android.content.pm.PackageManager
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import com.storyteller.app.data.ServerConfig
import com.storyteller.app.ui.CallScreen
import com.storyteller.app.ui.ParentScreen
import com.storyteller.app.ui.ServerSetupScreen
import com.storyteller.app.ui.WelcomeScreen
import com.storyteller.app.ui.theme.StoryTellerTheme

sealed interface Screen {
    data object ServerSetup : Screen
    data object Welcome : Screen
    data class Call(val character: String, val language: String) : Screen
    data object Parent : Screen
}

class MainActivity : ComponentActivity() {
    private var micPermissionGranted by mutableStateOf(false)

    private val requestMicPermission = registerForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> micPermissionGranted = granted }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        micPermissionGranted = ContextCompat.checkSelfPermission(
            this, Manifest.permission.RECORD_AUDIO
        ) == PackageManager.PERMISSION_GRANTED
        if (!micPermissionGranted) {
            requestMicPermission.launch(Manifest.permission.RECORD_AUDIO)
        }

        val serverConfig = ServerConfig(applicationContext)

        setContent {
            StoryTellerTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    if (!micPermissionGranted) {
                        Text("Story Teller needs microphone access to work — please grant it and reopen the app.")
                    } else {
                        AppNav(serverConfig)
                    }
                }
            }
        }
    }
}

@Composable
private fun AppNav(serverConfig: ServerConfig) {
    var screen by remember { mutableStateOf<Screen>(Screen.ServerSetup) }
    var baseUrl by remember { mutableStateOf<String?>(null) }

    when (val current = screen) {
        is Screen.ServerSetup -> ServerSetupScreen(
            serverConfig = serverConfig,
            onReady = { url ->
                baseUrl = url
                screen = Screen.Welcome
            },
        )
        is Screen.Welcome -> baseUrl?.let { url ->
            WelcomeScreen(
                baseUrl = url,
                onSelectCharacter = { character, language ->
                    screen = Screen.Call(character, language)
                },
                onOpenParent = { screen = Screen.Parent },
                onChangeServer = { screen = Screen.ServerSetup },
            )
        }
        is Screen.Call -> baseUrl?.let { url ->
            CallScreen(
                baseUrl = url,
                character = current.character,
                language = current.language,
                onEndCall = { screen = Screen.Welcome },
            )
        }
        is Screen.Parent -> baseUrl?.let { url ->
            ParentScreen(
                baseUrl = url,
                onClose = { screen = Screen.Welcome },
            )
        }
    }
}
