plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("org.jetbrains.kotlin.plugin.serialization")
}

android {
    namespace = "com.storyteller.app"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.storyteller.app"
        // Samsung tablets in the field are comfortably above this; 26 keeps
        // the manifest/permission model simple (no need for the pre-Oreo
        // notification-channel-less code paths).
        minSdk = 26
        targetSdk = 34
        versionCode = 3
        versionName = "1.0-dbg2"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
    }

    packaging {
        // LiveKit's WebRTC dependency and okhttp both ship META-INF license
        // files under the same names; without this the merge step fails.
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
            excludes += "/META-INF/DEPENDENCIES"
        }
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.10.01"))

    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.datastore:datastore-preferences:1.1.1")

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")

    // Real-time voice — WebRTC over LiveKit, native Android audio pipeline
    // (hardware AEC/NS/AGC where the device supports it) instead of
    // whatever a mobile browser's WebView happens to negotiate.
    implementation("io.livekit:livekit-android:2.27.0")

    // Pinned to the 4.x line deliberately: okhttp 5.x requires compileSdk 36+,
    // which would cascade into bumping compileSdk/build-tools for no benefit
    // here. 4.12.0 is the long-established stable release.
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    // 1.7.x, not the latest 1.11.x: that one's built against a newer Kotlin
    // metadata version than this project's Kotlin 2.0.21 compiler can read
    // (hit a hard "internal compiler error" pulling it in) — 1.7.x is
    // contemporaneous with Kotlin 2.0 and compiles cleanly.
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.7.3")

    debugImplementation("androidx.compose.ui:ui-tooling")
}
