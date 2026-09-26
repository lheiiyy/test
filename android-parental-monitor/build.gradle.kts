// Intentionally empty: each module declares its own plugins with explicit versions
// (see core/build.gradle.kts and app/build.gradle.kts) so that `:core` — a plain-JVM
// module with no Android dependency — can be built and tested without the Android
// Gradle plugin or an Android SDK on the machine.
