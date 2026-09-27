import java.io.File
import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

android {
    namespace = "com.jaljeev.marine"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.jaljeev.marine"
        minSdk = 24
        targetSdk = 35
        versionCode = 2
        versionName = "1.0.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"

        // Default backend base URL. 10.0.2.2 is the Android emulator's alias
        // for the host machine's 127.0.0.1, where `uvicorn app.main:app
        // --port 8000` runs (see the repo root CLAUDE.md). On a physical
        // device this is wrong by definition — override it at runtime in
        // Settings, no rebuild needed (SettingsRepository).
        buildConfigField("String", "DEFAULT_API_BASE", "\"http://10.0.2.2:8000\"")

        val localProps = Properties()
        val localPropsFile = rootProject.file("local.properties")
        if (localPropsFile.exists()) {
            localProps.load(localPropsFile.inputStream())
        }
        val sarvamApiKey = localProps.getProperty("SARVAM_API_KEY", "")
        buildConfigField("String", "SARVAM_API_KEY", "\"$sarvamApiKey\"")
    }

    signingConfigs {
        // For SIH demo submission, use debug signing. For Play Store release,
        // replace with a proper keystore (see README).
        getByName("debug") {
            // Uses default debug keystore at ~/.android/debug.keystore
        }
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            signingConfig = signingConfigs.getByName("debug") // demo: debug-signed release
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
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
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.fragment.ktx)
    implementation(libs.material)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.material.icons.extended)
    implementation(libs.androidx.navigation.compose)

    implementation(libs.androidx.datastore.preferences)

    implementation(libs.retrofit)
    implementation(libs.retrofit.converter.gson)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.gson)
    implementation(libs.kotlinx.serialization.json)

    implementation(libs.play.services.location)
    implementation(libs.maplibre.android)
    androidTestImplementation(libs.androidx.compose.ui.test.junit4)
    debugImplementation(libs.androidx.compose.ui.test.manifest)

    debugImplementation(libs.androidx.ui.tooling)

    testImplementation(libs.junit)
    testImplementation(libs.okhttp.mockwebserver)
    androidTestImplementation(libs.androidx.junit)
    androidTestImplementation(libs.androidx.espresso.core)
    androidTestImplementation(platform(libs.androidx.compose.bom))
}

tasks.register("listAvds") {
    group = "emulator"
    description = "Lists available Android Virtual Devices (AVDs)"
    doLast {
        val sdkDir = android.sdkDirectory
        val isWindows = System.getProperty("os.name").lowercase().contains("windows")
        val emulatorExe = File(sdkDir, "emulator/emulator" + if (isWindows) ".exe" else "")
        if (!emulatorExe.exists()) {
            throw GradleException("Emulator executable not found at: ${emulatorExe.absolutePath}")
        }
        val process = ProcessBuilder(emulatorExe.absolutePath, "-list-avds")
            .redirectErrorStream(true)
            .start()
        val output = process.inputStream.bufferedReader().readText()
        process.waitFor()
        logger.lifecycle("Available AVDs:\n$output")
    }
}

tasks.register("launchEmulator") {
    group = "emulator"
    description = "Launches an Android emulator AVD with GUI window (default: medium_phone, or pass -Pavd=<name>)"
    doLast {
        val avdName = project.findProperty("avd") as String? ?: "medium_phone"
        val sdkDir = android.sdkDirectory
        val isWindows = System.getProperty("os.name").lowercase().contains("windows")
        val emulatorExe = File(sdkDir, "emulator/emulator" + if (isWindows) ".exe" else "")
        if (!emulatorExe.exists()) {
            throw GradleException("Emulator executable not found at: ${emulatorExe.absolutePath}")
        }
        logger.lifecycle("Starting Android emulator AVD '$avdName'...")
        if (isWindows) {
            ProcessBuilder("cmd.exe", "/c", "start", "\"\"", emulatorExe.absolutePath, "-avd", avdName)
                .start()
        } else {
            ProcessBuilder(emulatorExe.absolutePath, "-avd", avdName)
                .redirectOutput(ProcessBuilder.Redirect.DISCARD)
                .redirectError(ProcessBuilder.Redirect.DISCARD)
                .start()
        }
        logger.lifecycle("Android emulator '$avdName' launched!")
    }
}
