package com.storyteller.phone.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

@Serializable
data class StatusResponse(
    val ready: Boolean,
    val languages: List<String> = listOf("en"),
    @SerialName("wake_word") val wakeWord: Boolean = false,
    @SerialName("time_limit_minutes") val timeLimitMinutes: Int = 30,
)

@Serializable
data class ConnectionDetails(
    val serverUrl: String,
    val roomName: String,
    val participantName: String,
    val participantToken: String,
)

@Serializable
data class ParentSettings(
    @SerialName("time_limit_minutes") val timeLimitMinutes: Int = 30,
    @SerialName("story_title") val storyTitle: String = "",
    @SerialName("story_text") val storyText: String = "",
)

@Serializable
private data class VerifyPinResponse(val ok: Boolean)

@Serializable
private data class ConnectionDetailsRequest(val character: String, val language: String)

@Serializable
private data class PinRequest(val pin: String)

@Serializable
private data class SaveSettingsRequest(
    val pin: String,
    @SerialName("time_limit_minutes") val timeLimitMinutes: Int,
    @SerialName("story_title") val storyTitle: String,
    @SerialName("story_text") val storyText: String,
)

class ApiException(message: String, val statusCode: Int? = null) : Exception(message)

/**
 * Thin wrapper around the same REST surface local_voice_ai/api.py exposes to
 * the web frontend — see that file for the source of truth on request/
 * response shapes. Trusts the network security config's CA policy (system +
 * user-installed, i.e. Caddy's local CA once the parent has trusted it) —
 * no certificate pinning here, deliberately, so it survives the CA being
 * regenerated if the caddy_data volume is ever recreated.
 */
class ApiClient(private val baseUrl: String) {
    private val json = Json { ignoreUnknownKeys = true }
    private val client = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .build()

    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    private fun url(path: String) = "$baseUrl$path"

    suspend fun status(): StatusResponse = withContext(Dispatchers.IO) {
        val request = Request.Builder().url(url("/api/status")).get().build()
        client.newCall(request).execute().use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw ApiException("status ${resp.code}", resp.code)
            json.decodeFromString(body)
        }
    }

    suspend fun connectionDetails(character: String, language: String): ConnectionDetails =
        withContext(Dispatchers.IO) {
            val payload = json.encodeToString(ConnectionDetailsRequest(character, language))
            val request = Request.Builder()
                .url(url("/api/connection-details"))
                .post(payload.toRequestBody(jsonMediaType))
                .build()
            client.newCall(request).execute().use { resp ->
                val body = resp.body?.string().orEmpty()
                if (!resp.isSuccessful) throw ApiException("connection-details ${resp.code}", resp.code)
                json.decodeFromString(body)
            }
        }

    suspend fun previewVoice(character: String, language: String): ByteArray =
        withContext(Dispatchers.IO) {
            val payload = json.encodeToString(ConnectionDetailsRequest(character, language))
            val request = Request.Builder()
                .url(url("/api/preview-voice"))
                .post(payload.toRequestBody(jsonMediaType))
                .build()
            client.newCall(request).execute().use { resp ->
                if (!resp.isSuccessful) throw ApiException("preview-voice ${resp.code}", resp.code)
                resp.body?.bytes() ?: ByteArray(0)
            }
        }

    suspend fun verifyPin(pin: String): Boolean = withContext(Dispatchers.IO) {
        val payload = json.encodeToString(PinRequest(pin))
        val request = Request.Builder()
            .url(url("/api/parent/verify-pin"))
            .post(payload.toRequestBody(jsonMediaType))
            .build()
        client.newCall(request).execute().use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) return@use false
            json.decodeFromString<VerifyPinResponse>(body).ok
        }
    }

    suspend fun getParentSettings(pin: String): ParentSettings = withContext(Dispatchers.IO) {
        val request = Request.Builder()
            .url(url("/api/parent/settings"))
            .header("X-Parent-Pin", pin)
            .get()
            .build()
        client.newCall(request).execute().use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw ApiException("invalid pin", resp.code)
            json.decodeFromString(body)
        }
    }

    suspend fun saveParentSettings(
        pin: String,
        timeLimitMinutes: Int,
        storyTitle: String,
        storyText: String,
    ): ParentSettings = withContext(Dispatchers.IO) {
        val payload = json.encodeToString(
            SaveSettingsRequest(pin, timeLimitMinutes, storyTitle, storyText)
        )
        val request = Request.Builder()
            .url(url("/api/parent/settings"))
            .post(payload.toRequestBody(jsonMediaType))
            .build()
        client.newCall(request).execute().use { resp ->
            val body = resp.body?.string().orEmpty()
            if (!resp.isSuccessful) throw ApiException("save failed", resp.code)
            json.decodeFromString(body)
        }
    }

    suspend fun uploadPdf(pin: String, fileName: String, bytes: ByteArray): ParentSettings =
        withContext(Dispatchers.IO) {
            val multipart = MultipartBody.Builder()
                .setType(MultipartBody.FORM)
                .addFormDataPart("pin", pin)
                .addFormDataPart(
                    "file",
                    fileName,
                    bytes.toRequestBody("application/pdf".toMediaType()),
                )
                .build()
            val request = Request.Builder()
                .url(url("/api/parent/upload-pdf"))
                .post(multipart)
                .build()
            client.newCall(request).execute().use { resp ->
                val body = resp.body?.string().orEmpty()
                if (!resp.isSuccessful) throw ApiException("upload failed", resp.code)
                json.decodeFromString(body)
            }
        }
}
