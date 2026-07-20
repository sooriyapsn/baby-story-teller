package com.storyteller.app.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.storyteller.app.data.ApiClient
import kotlinx.coroutines.launch

@Composable
fun ParentScreen(baseUrl: String, onClose: () -> Unit) {
    var pin by remember { mutableStateOf<String?>(null) }

    Column(modifier = Modifier.fillMaxSize().padding(32.dp)) {
        TextButton(onClick = onClose) { Text("Close") }
        if (pin == null) {
            PinGate(baseUrl = baseUrl, onUnlocked = { pin = it })
        } else {
            SettingsForm(baseUrl = baseUrl, pin = pin!!)
        }
    }
}

@Composable
private fun PinGate(baseUrl: String, onUnlocked: (String) -> Unit) {
    var pinInput by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var checking by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    Column(
        modifier = Modifier.fillMaxSize(),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text("Enter the parent PIN", style = MaterialTheme.typography.titleLarge)
        OutlinedTextField(
            value = pinInput,
            onValueChange = { pinInput = it; error = null },
            modifier = Modifier.width(200.dp).padding(top = 16.dp),
            isError = error != null,
        )
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        Button(
            onClick = {
                checking = true
                scope.launch {
                    val ok = try {
                        ApiClient(baseUrl).verifyPin(pinInput)
                    } catch (_: Exception) {
                        false
                    }
                    checking = false
                    if (ok) onUnlocked(pinInput) else error = "Incorrect PIN"
                }
            },
            enabled = !checking && pinInput.isNotBlank(),
            modifier = Modifier.padding(top = 16.dp),
        ) {
            Text(if (checking) "Checking…" else "Unlock")
        }
    }
}

@Composable
private fun SettingsForm(baseUrl: String, pin: String) {
    val context = LocalContext.current
    val api = remember { ApiClient(baseUrl) }
    val scope = rememberCoroutineScope()

    var loaded by remember { mutableStateOf(false) }
    var timeLimitText by remember { mutableStateOf("30") }
    var storyTitle by remember { mutableStateOf("") }
    var storyText by remember { mutableStateOf("") }
    var status by remember { mutableStateOf<String?>(null) }

    androidx.compose.runtime.LaunchedEffect(Unit) {
        try {
            val settings = api.getParentSettings(pin)
            timeLimitText = settings.timeLimitMinutes.toString()
            storyTitle = settings.storyTitle
            storyText = settings.storyText
        } catch (_: Exception) {
            // Fall back to defaults shown above; save will still work.
        } finally {
            loaded = true
        }
    }

    val pdfPicker = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        scope.launch {
            try {
                val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                    ?: return@launch
                val settings = api.uploadPdf(pin, "story.pdf", bytes)
                storyTitle = settings.storyTitle
                storyText = settings.storyText
                status = "PDF uploaded: ${settings.storyTitle}"
            } catch (e: Exception) {
                status = "Couldn't read that PDF: ${e.message}"
            }
        }
    }

    if (!loaded) {
        Text("Loading…")
        return
    }

    Column(modifier = Modifier.fillMaxWidth().padding(top = 16.dp)) {
        Text("Play time limit (minutes)", style = MaterialTheme.typography.titleSmall)
        OutlinedTextField(
            value = timeLimitText,
            onValueChange = { timeLimitText = it.filter { c -> c.isDigit() } },
            modifier = Modifier.width(120.dp),
        )

        Text("Story / lesson title", style = MaterialTheme.typography.titleSmall, modifier = Modifier.padding(top = 16.dp))
        OutlinedTextField(
            value = storyTitle,
            onValueChange = { storyTitle = it },
            modifier = Modifier.fillMaxWidth(),
        )

        Text(
            "Story text (paste it in, or upload a PDF below)",
            style = MaterialTheme.typography.titleSmall,
            modifier = Modifier.padding(top = 16.dp),
        )
        OutlinedTextField(
            value = storyText,
            onValueChange = { storyText = it },
            modifier = Modifier.fillMaxWidth().height(160.dp),
        )

        OutlinedButton(
            onClick = { pdfPicker.launch("application/pdf") },
            modifier = Modifier.padding(top = 16.dp),
        ) {
            Text("Upload PDF")
        }

        status?.let { Text(it, modifier = Modifier.padding(top = 8.dp)) }

        Button(
            onClick = {
                scope.launch {
                    try {
                        api.saveParentSettings(
                            pin = pin,
                            timeLimitMinutes = timeLimitText.toIntOrNull() ?: 30,
                            storyTitle = storyTitle,
                            storyText = storyText,
                        )
                        status = "Saved."
                    } catch (e: Exception) {
                        status = "Couldn't save: ${e.message}"
                    }
                }
            },
            modifier = Modifier.padding(top = 24.dp),
        ) {
            Text("Save settings")
        }
    }
}
