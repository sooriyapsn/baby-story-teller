package com.storyteller.app.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
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
import com.storyteller.app.data.ApiClient
import com.storyteller.app.data.ServerConfig
import kotlinx.coroutines.launch

/**
 * First-run (and "change server") screen: there's no service discovery on a
 * home LAN, so the parent enters the machine's address once — same thing
 * they'd bookmark in a browser. Pre-fills with whatever was saved last time.
 */
@Composable
fun ServerSetupScreen(serverConfig: ServerConfig, onReady: (String) -> Unit) {
    var url by remember { mutableStateOf("https://192.168.1.100:8091") }
    var error by remember { mutableStateOf<String?>(null) }
    var checking by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(Unit) {
        serverConfig.baseUrlFlow.collect { saved ->
            if (saved != null) url = saved
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
            modifier = Modifier.width(400.dp),
            isError = error != null,
        )
        error?.let { Text(it, color = androidx.compose.material3.MaterialTheme.colorScheme.error) }
        Button(
            onClick = {
                checking = true
                error = null
                scope.launch {
                    try {
                        ApiClient(url.trim().trimEnd('/')).status()
                        serverConfig.setBaseUrl(url)
                        onReady(url.trim().trimEnd('/'))
                    } catch (e: Exception) {
                        error = "Couldn't reach that address: ${e.message}"
                    } finally {
                        checking = false
                    }
                }
            },
            enabled = !checking && url.isNotBlank(),
            modifier = Modifier.padding(top = 16.dp),
        ) {
            Text(if (checking) "Checking…" else "Continue")
        }
    }
}
