package com.storyteller.phone.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.Card
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.storyteller.phone.data.ALL_LANGUAGES
import com.storyteller.phone.data.ApiClient
import com.storyteller.phone.data.CHARACTERS
import com.storyteller.phone.data.LANGUAGE_LABELS
import com.storyteller.phone.voice.AgentState

@Composable
fun WelcomeScreen(
    baseUrl: String,
    onSelectCharacter: (character: String, language: String) -> Unit,
    onOpenParent: () -> Unit,
    onChangeServer: () -> Unit,
) {
    var availableLanguages by remember { mutableStateOf(listOf("en")) }
    var language by remember { mutableStateOf("en") }
    var languageMenuOpen by remember { mutableStateOf(false) }

    LaunchedEffect(baseUrl) {
        try {
            availableLanguages = ApiClient(baseUrl).status().languages
        } catch (_: Exception) {
            // Fails open to English-only; the picker below still works.
        }
    }

    Box(modifier = Modifier.fillMaxSize().padding(24.dp)) {
        Row(
            modifier = Modifier.align(Alignment.TopEnd),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Box {
                OutlinedButton(onClick = { languageMenuOpen = true }) {
                    Text(LANGUAGE_LABELS[language] ?: language)
                }
                DropdownMenu(expanded = languageMenuOpen, onDismissRequest = { languageMenuOpen = false }) {
                    ALL_LANGUAGES.forEach { code ->
                        val available = availableLanguages.contains(code)
                        DropdownMenuItem(
                            text = { Text(LANGUAGE_LABELS[code] + if (!available) " (soon)" else "") },
                            enabled = available,
                            onClick = { language = code; languageMenuOpen = false },
                        )
                    }
                }
            }
            IconButton(onClick = onOpenParent) {
                Icon(Icons.Filled.Lock, contentDescription = "Parent settings")
            }
        }

        Column(
            modifier = Modifier.fillMaxSize().padding(top = 48.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text("Who do you want to play with?", style = MaterialTheme.typography.headlineMedium)
            Text(
                "Tap your favorite friend to start!",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 8.dp, bottom = 24.dp),
            )
            // A phone in portrait is rarely wide enough for 3 cards side by
            // side (tab-app's tablet layout) — a scrollable vertical list of
            // full-width rows fits any phone size instead.
            LazyColumn(
                modifier = Modifier.weight(1f).widthIn(max = 480.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 16.dp),
            ) {
                items(CHARACTERS) { c ->
                    Card(
                        onClick = { onSelectCharacter(c.id, language) },
                        shape = RoundedCornerShape(20.dp),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Row(
                            modifier = Modifier.padding(16.dp).fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(16.dp),
                        ) {
                            MascotCharacter(
                                characterDef = c,
                                agentState = AgentState.LISTENING,
                                modifier = Modifier.size(64.dp),
                            )
                            Column {
                                Text(c.displayName, style = MaterialTheme.typography.titleMedium)
                                Text(c.tagline, style = MaterialTheme.typography.bodySmall)
                            }
                        }
                    }
                }
            }
            OutlinedButton(onClick = onChangeServer, modifier = Modifier.padding(vertical = 16.dp)) {
                Text("Change server")
            }
        }
    }
}
