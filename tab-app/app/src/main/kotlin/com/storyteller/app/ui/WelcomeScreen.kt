package com.storyteller.app.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
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
import com.storyteller.app.data.ALL_LANGUAGES
import com.storyteller.app.data.ApiClient
import com.storyteller.app.data.CHARACTERS
import com.storyteller.app.data.LANGUAGE_LABELS

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
            modifier = Modifier.fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text("Who do you want to play with?", style = MaterialTheme.typography.headlineMedium)
            Text(
                "Tap your favorite friend to start!",
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.padding(top = 8.dp, bottom = 32.dp),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                CHARACTERS.forEach { c ->
                    Card(
                        onClick = { onSelectCharacter(c.id, language) },
                        shape = RoundedCornerShape(24.dp),
                        modifier = Modifier.width(160.dp),
                    ) {
                        Column(
                            modifier = Modifier.padding(16.dp),
                            horizontalAlignment = Alignment.CenterHorizontally,
                        ) {
                            Box(
                                modifier = Modifier
                                    .size(80.dp)
                                    .background(c.color, CircleShape)
                            )
                            Text(
                                c.displayName,
                                style = MaterialTheme.typography.titleMedium,
                                modifier = Modifier.padding(top = 12.dp),
                            )
                            Text(
                                c.tagline,
                                style = MaterialTheme.typography.bodySmall,
                                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                            )
                        }
                    }
                }
            }
            OutlinedButton(onClick = onChangeServer, modifier = Modifier.padding(top = 32.dp)) {
                Text("Change server")
            }
        }
    }
}
