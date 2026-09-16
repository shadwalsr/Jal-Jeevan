# kotlinx.serialization keeps generated serializers on the classes it annotates.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers class com.jaljeev.marine.data.remote.** {
    *** Companion;
}
-keepclasseswithmembers class com.jaljeev.marine.data.remote.** {
    kotlinx.serialization.KSerializer serializer(...);
}
