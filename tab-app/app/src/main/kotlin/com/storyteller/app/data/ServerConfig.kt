package com.storyteller.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

private val Context.dataStore by preferencesDataStore(name = "server_config")
private val SERVER_URL_KEY = stringPreferencesKey("server_url")

/**
 * The backend's base URL (e.g. "https://192.168.1.203:8091"), set once on
 * first launch. There's no service discovery here — a home LAN deployment
 * doesn't have a stable DNS name, so this is a manual field the parent fills
 * in, same as bookmarking the URL in a browser would be.
 */
class ServerConfig(private val context: Context) {
    val baseUrlFlow: Flow<String?> =
        context.dataStore.data.map { it[SERVER_URL_KEY] }

    suspend fun setBaseUrl(url: String) {
        val normalized = url.trim().trimEnd('/')
        context.dataStore.edit { it[SERVER_URL_KEY] = normalized }
    }
}
