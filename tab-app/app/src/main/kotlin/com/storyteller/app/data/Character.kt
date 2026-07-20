package com.storyteller.app.data

import androidx.compose.ui.graphics.Color

// Keep ids/order/colors in sync with local_voice_ai/characters.py and
// frontend/components/app/agent-character.tsx — this is the third copy of
// the same registry, and the mascot theme here mirrors agent-character.tsx's
// THEMES map field-for-field so the native mascot matches the web one.
enum class MascotAccessory { STAR, BOLT, HEART }

data class CharacterDef(
    val id: String,
    val displayName: String,
    val tagline: String,
    val color: Color,
    val bodyStroke: Color,
    val ear: Color,
    val cheek: Color,
    val mouth: Color,
    val accessory: MascotAccessory,
    val accessoryColor: Color,
    /** Grumpy characters get angled brows and a default frown instead of a smile. */
    val grumpy: Boolean = false,
)

val CHARACTERS = listOf(
    CharacterDef(
        id = "red",
        displayName = "Red One",
        tagline = "Grumpy on the outside, sweet on the inside",
        color = Color(0xFFE8503A),
        bodyStroke = Color(0xFFC43A28),
        ear = Color(0xFFD4442F),
        cheek = Color(0xFFFFB199),
        mouth = Color(0xFF5C1F14),
        accessory = MascotAccessory.BOLT,
        accessoryColor = Color(0xFFFFD166),
        grumpy = true,
    ),
    CharacterDef(
        id = "blue",
        displayName = "Blue Bolt",
        tagline = "Full of energy and silly jokes",
        color = Color(0xFF4A9DFF),
        bodyStroke = Color(0xFF2E7FDE),
        ear = Color(0xFF3E8FF2),
        cheek = Color(0xFFBEE3FF),
        mouth = Color(0xFF1B3A5C),
        accessory = MascotAccessory.BOLT,
        accessoryColor = Color(0xFFFFE873),
    ),
    CharacterDef(
        id = "pink",
        displayName = "Rosie",
        tagline = "Sweet stories and gentle magic",
        color = Color(0xFFFF8FB3),
        bodyStroke = Color(0xFFE86F97),
        ear = Color(0xFFFF7FA8),
        cheek = Color(0xFFFFD1E1),
        mouth = Color(0xFF8A2F4C),
        accessory = MascotAccessory.HEART,
        accessoryColor = Color(0xFFFF6B9A),
    ),
)

val LANGUAGE_LABELS = mapOf(
    "en" to "English",
    "te" to "తెలుగు",
    "mr" to "मराठी",
)
val ALL_LANGUAGES = listOf("en", "te", "mr")
