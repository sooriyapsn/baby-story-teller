package com.storyteller.phone.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import java.net.URI

private val Context.dataStore by preferencesDataStore(name = "server_config")
private val SERVER_URL_KEY = stringPreferencesKey("server_url")
private val WAKE_SECRET_KEY = stringPreferencesKey("wake_secret")
private val WAKE_PORT_KEY = intPreferencesKey("wake_port")

data class ConnectionSettings(
    val baseUrl: String,
    val wakeSecret: String,
    val wakePort: Int,
) {
    /** The wake listener always speaks plain HTTP (see wake-listener/README.md
     * — it's a separate stdlib process outside Caddy/TLS), on the same host
     * as the main server regardless of what scheme/port baseUrl uses. */
    val wakeUrl: String?
        get() = runCatching { URI(baseUrl).host }.getOrNull()?.let { host -> "http://$host:$wakePort" }
}

/**
 * All connection info the app needs lives in this one DataStore-backed file
 * — server address, and the wake listener's port/secret — so there's a
 * single place to look when something needs updating, editable from either
 * the server-setup screen or the parent dashboard.
 *
 * There's no service discovery here — a home LAN deployment doesn't have a
 * stable DNS name, so the server address is a manual field the parent fills
 * in, same as bookmarking it in a browser would be.
 */
class ServerConfig(private val context: Context) {
    val baseUrlFlow: Flow<String?> = context.dataStore.data.map { it[SERVER_URL_KEY] }
    val wakeSecretFlow: Flow<String> = context.dataStore.data.map { it[WAKE_SECRET_KEY] ?: "" }
    val wakePortFlow: Flow<Int> = context.dataStore.data.map { it[WAKE_PORT_KEY] ?: 9191 }

    suspend fun current(): ConnectionSettings = ConnectionSettings(
        baseUrl = baseUrlFlow.first() ?: "",
        wakeSecret = wakeSecretFlow.first(),
        wakePort = wakePortFlow.first(),
    )

    suspend fun setBaseUrl(url: String) {
        val normalized = url.trim().trimEnd('/')
        context.dataStore.edit { it[SERVER_URL_KEY] = normalized }
    }

    suspend fun setWakeSecret(secret: String) {
        context.dataStore.edit { it[WAKE_SECRET_KEY] = secret.trim() }
    }

    suspend fun setWakePort(port: Int) {
        context.dataStore.edit { it[WAKE_PORT_KEY] = port }
    }
}
