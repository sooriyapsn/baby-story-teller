package com.storyteller.phone.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

/**
 * Talks to wake-listener/wake_listener.py — a separate stdlib process
 * running directly on the host (not inside Docker, not behind Caddy), so
 * this deliberately uses its own short-timeout plain-HTTP client rather
 * than reusing ApiClient's.
 */
class WakeClient(private val wakeUrl: String) {
    private val client = OkHttpClient.Builder()
        .connectTimeout(3, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build()

    suspend fun isReachable(): Boolean = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder().url("$wakeUrl/health").get().build()
            client.newCall(request).execute().use { it.isSuccessful }
        } catch (_: Exception) {
            false
        }
    }

    suspend fun wake(secret: String): Boolean = withContext(Dispatchers.IO) {
        try {
            val request = Request.Builder()
                .url("$wakeUrl/wake")
                .header("X-Wake-Secret", secret)
                .post(ByteArray(0).toRequestBody(null))
                .build()
            client.newCall(request).execute().use { it.isSuccessful }
        } catch (_: Exception) {
            false
        }
    }
}
