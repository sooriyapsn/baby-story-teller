package com.storyteller.phone.data

import androidx.compose.ui.graphics.Color

// Keep ids/order in sync with local_voice_ai/characters.py and
// frontend/lib/characters.ts — this is the third copy of the same registry.
data class CharacterDef(
    val id: String,
    val displayName: String,
    val tagline: String,
    val color: Color,
)

val CHARACTERS = listOf(
    CharacterDef(
        id = "red",
        displayName = "Red One",
        tagline = "Grumpy on the outside, sweet on the inside",
        color = Color(0xFFE8604C),
    ),
    CharacterDef(
        id = "blue",
        displayName = "Blue Bolt",
        tagline = "Full of energy and silly jokes",
        color = Color(0xFF4A90E8),
    ),
    CharacterDef(
        id = "pink",
        displayName = "Rosie",
        tagline = "Sweet stories and gentle magic",
        color = Color(0xFFE85C9E),
    ),
)

val LANGUAGE_LABELS = mapOf(
    "en" to "English",
    "te" to "తెలుగు",
    "mr" to "मराठी",
)
val ALL_LANGUAGES = listOf("en", "te", "mr")
