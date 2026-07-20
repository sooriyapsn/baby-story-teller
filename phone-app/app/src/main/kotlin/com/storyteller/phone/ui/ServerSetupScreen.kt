package com.storyteller.phone.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.storyteller.phone.data.ApiClient
import com.storyteller.phone.data.ServerConfig
import com.storyteller.phone.data.WakeClient
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * First-run (and "change server") screen: there's no service discovery on a
 * home LAN, so the parent enters the machine's address once — same thing
 * they'd bookmark in a browser. Pre-fills with whatever was saved last time.
 *
 * If a connection attempt actually fails and a wake secret is set, a "wake
 * up server" button appears — it's not shown proactively, since the wake
 * listener is optional infrastructure most setups won't have configured.
 */
@Composable
fun ServerSetupScreen(serverConfig: ServerConfig, onReady: (String) -> Unit) {
    var url by remember { mutableStateOf("https://192.168.1.100:8091") }
    var wakeSecret by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var checking by remember { mutableStateOf(false) }
    var waking by remember { mutableStateOf(false) }
    var wakeStatus by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        val current = serverConfig.current()
        if (current.baseUrl.isNotBlank()) url = current.baseUrl
        wakeSecret = current.wakeSecret
    }

    fun tryConnect() {
        checking = true
        error = null
        wakeStatus = null
        scope.launch {
            try {
                ApiClient(url.trim().trimEnd('/')).status()
                serverConfig.setBaseUrl(url)
                serverConfig.setWakeSecret(wakeSecret)
                onReady(url.trim().trimEnd('/'))
            } catch (e: Exception) {
                error = "Couldn't reach that address: ${e.message}"
            } finally {
                checking = false
            }
        }
    }

    fun wakeAndRetry() {
        waking = true
        wakeStatus = "Waking up the server… this can take a minute or two."
        scope.launch {
            val settings = serverConfig.current().copy(baseUrl = url, wakeSecret = wakeSecret)
            val wakeUrl = settings.wakeUrl
            if (wakeUrl == null) {
                wakeStatus = "Couldn't figure out the wake listener's address from that server URL."
                waking = false
                return@launch
            }
            val wakeClient = WakeClient(wakeUrl)
            if (!wakeClient.wake(wakeSecret)) {
                wakeStatus = "Couldn't reach the wake listener — is the laptop on and on the same Wi-Fi?"
                waking = false
                return@launch
            }
            serverConfig.setWakeSecret(wakeSecret)

            // Poll the real server until it comes up (model loading can take
            // a while on first boot) or we give up after ~3 minutes.
            repeat(36) {
                delay(5_000)
                try {
                    val status = ApiClient(url.trim().trimEnd('/')).status()
                    if (status.ready) {
                        wakeStatus = null
                        error = null
                        serverConfig.setBaseUrl(url)
                        waking = false
                        onReady(url.trim().trimEnd('/'))
                        return@launch
                    }
                    wakeStatus = "Server is starting up…"
                } catch (_: Exception) {
                    // Not up yet — keep polling.
                }
            }
            wakeStatus = "Still not reachable after a few minutes — check the laptop directly."
            waking = false
        }
    }

    Column(
        modifier = Modifier.fillMaxSize().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Connect to Story Teller", style = androidx.compose.material3.MaterialTheme.typography.headlineSmall)
        Text(
            "Enter the address shown when the server starts, e.g. https://192.168.1.50:8091",
            modifier = Modifier.padding(top = 8.dp, bottom = 24.dp),
        )
        OutlinedTextField(
            value = url,
            onValueChange = { url = it; error = null },
            label = { Text("Server address") },
            modifier = Modifier.fillMaxWidth(),
            isError = error != null,
        )
        OutlinedTextField(
            value = wakeSecret,
            onValueChange = { wakeSecret = it },
            label = { Text("Wake secret (optional)") },
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
        )
        error?.let { Text(it, color = androidx.compose.material3.MaterialTheme.colorScheme.error) }
        Button(
            onClick = { tryConnect() },
            enabled = !checking && url.isNotBlank(),
            modifier = Modifier.padding(top = 16.dp),
        ) {
            Text(if (checking) "Checking…" else "Continue")
        }

        if (error != null && wakeSecret.isNotBlank()) {
            OutlinedButton(
                onClick = { wakeAndRetry() },
                enabled = !waking,
                modifier = Modifier.padding(top = 12.dp),
            ) {
                Text(if (waking) "Waking…" else "Wake up server")
            }
        }
        wakeStatus?.let { Text(it, modifier = Modifier.padding(top = 8.dp)) }
    }
}
