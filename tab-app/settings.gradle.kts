pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        // LiveKit's Android SDK depends on a JitPack-hosted AudioSwitch fork
        // (com.github.davidliu:audioswitch) — not on Maven Central/Google.
        maven(url = "https://jitpack.io")
    }
}

rootProject.name = "StoryTeller"
include(":app")
