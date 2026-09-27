# ── JalJeev ProGuard / R8 Rules ───────────────────────────────────
# These rules ensure the release APK works correctly with R8 minification.

# ── kotlinx.serialization ─────────────────────────────────────────
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**

# Keep serializer companion objects and generated serializers
-keepclassmembers class com.jaljeev.marine.data.remote.** {
    *** Companion;
}
-keepclasseswithmembers class com.jaljeev.marine.data.remote.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Keep all @Serializable model classes (prevents field stripping)
-keep class com.jaljeev.marine.data.remote.ApiModels$* { *; }
-keep @kotlinx.serialization.Serializable class * { *; }

# ── Retrofit ──────────────────────────────────────────────────────
# Retrofit does reflection on API interface methods at runtime
-keepattributes Signature, Exceptions
-keepclassmembers,allowshrinking,allowobfuscation interface * {
    @retrofit2.http.* <methods>;
}
-dontwarn retrofit2.**
-keep class retrofit2.** { *; }
-dontwarn org.codehaus.mojo.**
-dontwarn javax.annotation.**

# ── OkHttp ────────────────────────────────────────────────────────
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }
-keep interface okhttp3.** { *; }
-keepnames class okhttp3.internal.publicsuffix.PublicSuffixDatabase

# ── Gson ──────────────────────────────────────────────────────────
-keepattributes Signature
-keepattributes *Annotation*
-dontwarn sun.misc.**
-keep class com.google.gson.** { *; }
-keep class * extends com.google.gson.TypeAdapter { *; }
-keep class * implements com.google.gson.TypeAdapterFactory { *; }
-keep class * implements com.google.gson.JsonSerializer { *; }
-keep class * implements com.google.gson.JsonDeserializer { *; }

# ── MapLibre ──────────────────────────────────────────────────────
-keep class org.maplibre.android.** { *; }
-dontwarn org.maplibre.android.**

# ── Google Play Services Location ─────────────────────────────────
-keep class com.google.android.gms.** { *; }
-dontwarn com.google.android.gms.**

# ── Coroutines ────────────────────────────────────────────────────
-dontwarn kotlinx.coroutines.**
-keepnames class kotlinx.coroutines.internal.MainDispatcherFactory {}
-keepnames class kotlinx.coroutines.CoroutineExceptionHandler {}

# ── Compose ───────────────────────────────────────────────────────
# Compose handles its own keep rules via the plugin, but these prevent
# edge cases with state restoration and navigation args
-keep class * extends androidx.compose.runtime.Composable { *; }

# ── General Android ───────────────────────────────────────────────
-keepclassmembers class * implements android.os.Parcelable {
    public static final android.os.Parcelable$Creator CREATOR;
}

# Keep JalJeev's own domain models that may be serialized
-keep class com.jaljeev.marine.domain.** { *; }
